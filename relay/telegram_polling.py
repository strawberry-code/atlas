"""Long polling verso Telegram (G01): alternativa al webhook per ricevere
gli update, decisa dal disegno (docs/atlas-relay-design.md SS7/3, grilling 5)
per non pretendere hostname, certificato e porta pubblica. Il traduttore
dell'update in evento minimo resta relay/telegram_webhook.py
(GestoreWebhook.processa_update): questo modulo cambia solo da dove l'update
arriva, mai cosa se ne fa.

L'offset dell'ultimo update consegnato e' persistito su disco (stessa forma
di pairing.py/peers.py: scrittura atomica via file temporaneo + os.replace),
cosi' un riavvio del servizio non fa richiedere a Telegram update gia'
processati (Telegram tiene la coda finche' nessuno la conferma con un
offset piu' alto). La deduplica per update_id di GestoreWebhook resta un
secondo presidio, in memoria: protegge dentro la finestra di un processo
vivo, l'offset protegge attraverso un riavvio.

Il ciclo vive dentro il servizio, non e' un secondo processo: un thread
demone di atlas_relay.main(), fermato dallo stesso threading.Event che il
server HTTP gia' usa per il proprio shutdown.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path

TIMEOUT_LONG_POLL_SECONDI = 30       # quanto Telegram tiene aperta la getUpdates
ATTESA_DOPO_ERRORE_SECONDI = 5       # backoff fisso su un errore di rete o risposta malformata
ALLOWED_UPDATES = ["message", "callback_query"]  # gli unici due tipi che _estrai_evento riconosce

PREREQUISITI = ["TELEGRAM_BOT_TOKEN_REF"]
ENV_STATE_DIR = "ATLAS_RELAY_STATE_DIR"

ProcessaUpdate = Callable[[Mapping[str, object]], None]


def _percorso_stato_default() -> Path:
    return Path(__file__).resolve().parent / "state" / "polling-offset.json"


class OffsetStore:
    """L'update_id + 1 del prossimo update da chiedere a getUpdates."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def leggi(self) -> int:
        try:
            dati = json.loads(self._path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return 0
        offset = dati.get("offset")
        return offset if isinstance(offset, int) else 0

    def avanza(self, offset: int) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"offset": offset}), encoding="utf-8")
            os.replace(tmp, self._path)


def _get_updates(bot_token: str, offset: int, opener, timeout: int) -> list[dict]:
    query = urllib.parse.urlencode({
        "offset": offset,
        "timeout": timeout,
        "allowed_updates": json.dumps(ALLOWED_UPDATES),
    })
    richiesta = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/getUpdates?{query}", method="GET")
    with opener(richiesta, timeout=timeout + 10) as risposta:
        corpo = json.loads(risposta.read().decode("utf-8"))
    if not corpo.get("ok"):
        raise ValueError(corpo.get("description", "getUpdates non ok"))
    risultato = corpo.get("result")
    return risultato if isinstance(risultato, list) else []


def ciclo_polling(bot_token: str, processa_update: ProcessaUpdate, offset_store: OffsetStore,
                   fermo: threading.Event, opener=urllib.request.urlopen,
                   timeout: int = TIMEOUT_LONG_POLL_SECONDI,
                   attesa_errore: int = ATTESA_DOPO_ERRORE_SECONDI) -> None:
    """Interroga getUpdates finche' 'fermo' non e' impostato. Ogni update va
    al traduttore e l'offset avanza subito dopo, uno alla volta: un crash a
    meta' lotto non fa riconsegnare a Telegram quel che ha gia' processato
    prima del crash. Un errore di rete o una risposta malformata (Telegram
    giu', o ancora configurato a webhook: getUpdates rifiuta con 409 finche'
    G02 non lo smonta) non ferma il ciclo, aspetta e ritenta."""
    while not fermo.is_set():
        try:
            updates = _get_updates(bot_token, offset_store.leggi(), opener, timeout)
        except (OSError, urllib.error.URLError, ValueError, TimeoutError):
            fermo.wait(attesa_errore)
            continue
        for update in updates:
            # Un update non deve poter uccidere il servizio. Il traduttore
            # solleva UnpairedUser per ogni messaggio da una chat che il relay
            # non conosce, ed e' un caso ordinario, non un guasto: chiunque
            # trovi il bot puo' scrivergli. Senza questa cattura il thread
            # moriva al primo estraneo e il bot restava muto per tutti, con il
            # servizio che continuava a dirsi 'active'. Vale per qualunque
            # eccezione del traduttore, per la stessa ragione: si perde
            # l'update, non il servizio.
            try:
                processa_update(update)
            except Exception as errore:   # noqa: BLE001 - vedi sopra
                print(f"update {update.get('update_id')} scartato: "
                      f"{type(errore).__name__}: {errore}", file=sys.stderr, flush=True)
            # L'offset avanza comunque: un update che ha fatto sollevare
            # un'eccezione una volta la fara' sollevare identica per sempre, e
            # riconsegnarlo in eterno terrebbe fermo tutto quel che viene dopo.
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                offset_store.avanza(update_id + 1)


def avvia_poller_da_ambiente(env: Mapping[str, str], processa_update: ProcessaUpdate,
                              fermo: threading.Event, state_path: Path | None = None,
                              opener=urllib.request.urlopen) -> threading.Thread | None:
    """None se manca TELEGRAM_BOT_TOKEN_REF: senza token non c'e' niente da
    interrogare. Il thread parte gia' demone (muore col processo, nessun
    join da fare a mano) e usa 'fermo' per fermarsi in modo pulito: e' lo
    stesso threading.Event che main() gia' imposta nel finally dello
    shutdown del server HTTP. 'opener' e' iniettabile per gli stessi motivi
    delle costruisci_* di telegram_webhook.py: i test non devono chiamare
    api.telegram.org davvero."""
    if any(not env.get(nome) for nome in PREREQUISITI):
        return None
    if state_path is not None:
        percorso = state_path
    elif env.get(ENV_STATE_DIR):
        percorso = Path(env[ENV_STATE_DIR]) / "polling-offset.json"
    else:
        percorso = _percorso_stato_default()
    offset_store = OffsetStore(percorso)
    thread = threading.Thread(
        target=ciclo_polling,
        args=(env["TELEGRAM_BOT_TOKEN_REF"], processa_update, offset_store, fermo),
        kwargs={"opener": opener},
        daemon=True, name="telegram-polling")
    thread.start()
    return thread
