"""Pairing Telegram one-tap (D05): un bottone nel pannello Notifiche del
client chiede un codice monouso al relay, l'utente lo consegna al bot con
'/start <codice>' (il deep link t.me lo scrive gia' nell'URL, non lo digita a
mano), il relay lo verifica e associa il chat_id al progetto. Nessun token
bot, chat ID, hostname o file di configurazione da inserire: tutto cio' che
il client sa gia' (bearer del tunnel, D03) basta a chiedere il codice.

La granularita' dell'associazione e' il progetto (graph slug), non la
sessione (graph, runId) del tunnel D01/D03: un pairing va fatto una volta
sola, non ad ogni nuovo run di Automata. Sara' D06, quando inoltra un tap, a
risolvere a quale sessione (graph, runId) del momento appartiene un chat_id
gia' associato.

Persistito su disco (JSON), non solo in memoria di processo: un riavvio del
servizio (systemd Restart=on-failure, o un deploy) non deve scollegare tutti
gli utenti gia' associati. Il lock e' comunque quello di processo (thread di
ThreadingHTTPServer): il file su disco serve a sopravvivere a un restart, non
a coordinare piu' processi concorrenti, che qui non esistono.
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import time
from collections.abc import Callable
from pathlib import Path

TTL_CODICE_SECONDI = 600   # 10 minuti: quanto resta valido un codice non ancora usato

PREREQUISITI = ["TELEGRAM_BOT_TOKEN_REF", "TELEGRAM_BOT_USERNAME"]
ENV_STATE_DIR = "ATLAS_RELAY_STATE_DIR"

InviaMessaggio = Callable[[int, str], None]
PairingStart = Callable[[str, int], None]


def _percorso_stato_default() -> Path:
    return Path(__file__).resolve().parent / "state" / "pairing.json"


class GestorePairing:
    """Store persistente: richieste in sospeso (codice -> sessione) e
    associazioni confermate (chat_id -> progetto). Soddisfa anche il
    protocollo 'PairingStore' fissato da D04 (is_paired): non e' un'altra
    implementazione parallela, e' quella vera che D04 aveva lasciato da
    costruire."""

    def __init__(self, path: Path, ttl_seconds: int = TTL_CODICE_SECONDI) -> None:
        self._path = path
        self._ttl = ttl_seconds
        self._lock = threading.Lock()

    def _leggi(self) -> dict:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {"richieste": {}, "associazioni": {}}

    def _scrivi(self, dati: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(dati), encoding="utf-8")
        os.replace(tmp, self._path)

    def richiedi(self, graph: str) -> tuple[str, float]:
        """Un codice monouso fresco per questo progetto. Non invalida i
        codici gia' emessi per lo stesso graph: due schede della dashboard
        aperte sullo stesso progetto non si rompono a vicenda."""
        codice = secrets.token_urlsafe(9)
        adesso = time.time()
        scadenza = adesso + self._ttl
        with self._lock:
            dati = self._leggi()
            dati["richieste"][codice] = {
                "graph": graph, "createdAt": adesso, "expiresAt": scadenza, "chatId": None,
            }
            self._scrivi(dati)
        return codice, scadenza

    def conferma(self, codice: str, chat_id: int) -> str | None:
        """Se il codice esiste, non e' scaduto e non e' gia' stato usato,
        associa chat_id al progetto e torna il graph slug; altrimenti None.
        Monouso per costruzione: il secondo tentativo con lo stesso codice
        trova 'chatId' gia' valorizzato e si ferma qui, senza toccare il
        ledger di nessuno (questo modulo non ne ha nemmeno accesso)."""
        with self._lock:
            dati = self._leggi()
            richiesta = dati["richieste"].get(codice)
            if richiesta is None or richiesta["chatId"] is not None:
                return None
            if time.time() > richiesta["expiresAt"]:
                return None
            richiesta["chatId"] = chat_id
            dati["associazioni"][str(chat_id)] = {"graph": richiesta["graph"], "pairedAt": time.time()}
            self._scrivi(dati)
            return richiesta["graph"]

    def stato(self, codice: str) -> str:
        """'in_attesa' | 'associato' | 'scaduto' | 'sconosciuto': quanto
        basta al pannello Notifiche per sapere quando smettere di aspettare."""
        with self._lock:
            richiesta = self._leggi()["richieste"].get(codice)
        if richiesta is None:
            return "sconosciuto"
        if richiesta["chatId"] is not None:
            return "associato"
        if time.time() > richiesta["expiresAt"]:
            return "scaduto"
        return "in_attesa"

    def is_paired(self, chat_id: int) -> bool:
        with self._lock:
            return str(chat_id) in self._leggi()["associazioni"]

    def progetto_di(self, chat_id: int) -> str | None:
        """L'instradamento chat -> progetto: D06 lo usa per sapere a quale
        graph appartiene un tap in arrivo gia' associato."""
        with self._lock:
            record = self._leggi()["associazioni"].get(str(chat_id))
        return record["graph"] if record else None

    def chat_id_di(self, graph: str) -> int | None:
        """L'inverso di progetto_di (D07): a quale chat spingere il deliver
        iniziale di un'Interazione di questo progetto. Se piu' chat sono
        appaiate allo stesso progetto (due dispositivi, o un ripareamento
        senza aver disassociato il vecchio), vince la piu' recente: un nuovo
        pairing sposta dove arrivano le notifiche senza dover pulire nulla a
        mano."""
        with self._lock:
            associazioni = self._leggi()["associazioni"]
        candidati = [(int(chat_id), record["pairedAt"]) for chat_id, record in associazioni.items()
                    if record["graph"] == graph]
        if not candidati:
            return None
        return max(candidati, key=lambda coppia: coppia[1])[0]


def costruisci_pairing_start(store: GestorePairing, invia_messaggio: InviaMessaggio) -> PairingStart:
    """La chiusura che GestoreWebhook (D04) chiama su un '/start <codice>':
    prova la conferma, poi manda all'utente un messaggio di esito. Testo
    fisso in italiano: il relay non serve la dashboard multilingua di
    'payload/', e' infrastruttura a parte con un solo pubblico (chi risponde
    al bot)."""
    def _on_start(codice: str, chat_id: int) -> None:
        graph = store.conferma(codice, chat_id)
        if graph is None:
            invia_messaggio(chat_id, "Codice di pairing non valido o scaduto. "
                                       "Riapri il pannello Notifiche di Atlas e riprova.")
            return
        invia_messaggio(chat_id, f"Connesso ad Atlas ({graph}). Da qui in poi ricevi qui le richieste.")
    return _on_start


def costruisci_da_ambiente(env, state_path: Path | None = None) -> GestorePairing | None:
    """None se TELEGRAM_BOT_TOKEN_REF o TELEGRAM_BOT_USERNAME mancano: stesso
    gate del webhook (D04) piu' un riferimento in piu', perche' qui serve
    anche lo username pubblico del bot per costruire il deep link t.me, non
    solo il token per chiamare l'API."""
    if any(not env.get(nome) for nome in PREREQUISITI):
        return None
    if state_path is not None:
        percorso = state_path
    elif env.get(ENV_STATE_DIR):
        percorso = Path(env[ENV_STATE_DIR]) / "pairing.json"
    else:
        percorso = _percorso_stato_default()
    return GestorePairing(percorso)
