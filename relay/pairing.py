"""Pairing Telegram one-tap (D05/A02) e cancello d'ingresso (A03): un bottone
chiede al relay un codice monouso, l'utente lo consegna al bot con
'/start <codice>' (il deep link t.me lo scrive gia' nell'URL, non lo digita a
mano), e da li' la richiesta resta 'in attesa di via libera' finche' il
gestore non la approva o la rifiuta con un tap (S11/3).

Il modello e' quello di docs/atlas-relay-design.md SS4-bis: l'identita' che
conta e' quella dell'installazione (A01), non del progetto. Un'installazione
ha una chat sola (un nuovo pairing sposta dove arriva la notifica, senza
dover disassociare il vecchio), una chat puo' seguire piu' installazioni
della stessa persona (grilling 9: piu' computer, un solo telefono). Il relay
non conserva nomi di progetti (grilling 3) ne' stato dei grafi (grilling 7):
tutto cio' che sa e' quale chat risponde per quale installazione, e chi e'
il gestore.

Il gestore non e' un valore indovinabile ne' un segreto scritto nel codice
(A03): nasce da un unico tap su un deep link di bootstrap, monouso e generato
da 'emetti_bootstrap_gestore' (invocato una sola volta, a mano, da chi
distribuisce il relay - vedi 'bootstrap_gestore.py'), esattamente con lo
stesso primitivo del pairing di un'installazione. Una volta reclamato, il
ruolo non ruota piu' da qui: rifarlo e' un'operazione dichiarata, non
un'azione di questo modulo.

Persistito su disco (JSON), non solo in memoria di processo: un riavvio del
servizio (systemd Restart=on-failure, o un deploy) non deve scollegare tutti
gli utenti gia' associati ne' dimenticare chi e' il gestore. Il lock e'
comunque quello di processo (thread di ThreadingHTTPServer): il file su disco
serve a sopravvivere a un restart, non a coordinare piu' processi concorrenti,
che qui non esistono.
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

PREFISSO_APPROVA = "gestore:approva:"
PREFISSO_RIFIUTA = "gestore:rifiuta:"

InviaMessaggio = Callable[[int, str], None]
InviaBottoni = Callable[[int, str, list], None]
ModificaMessaggio = Callable[[int, int, str], None]
PairingStart = Callable[[str, int, "str | None"], None]
AdminDecision = Callable[[str, int, int], bool]


def _percorso_stato_default() -> Path:
    return Path(__file__).resolve().parent / "state" / "pairing.json"


class GestorePairing:
    """Store persistente: richieste in sospeso (codice -> installazione, con
    lo stato del cancello d'ingresso), associazioni confermate (installazione
    -> chat_id) e il gestore (chat_id di chi approva). Soddisfa anche il
    protocollo 'PairingStore' fissato da D04 (is_paired): non e' un'altra
    implementazione parallela, e' quella vera che D04 aveva lasciato da
    costruire."""

    def __init__(self, path: Path, ttl_seconds: int = TTL_CODICE_SECONDI) -> None:
        self._path = path
        self._ttl = ttl_seconds
        self._lock = threading.Lock()

    def _leggi(self) -> dict:
        try:
            dati = json.loads(self._path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            dati = {}
        dati.setdefault("richieste", {})
        dati.setdefault("associazioni", {})
        dati.setdefault("gestore", {"chatId": None, "bootstrapCode": None, "bootstrapExpiresAt": None})
        return dati

    def _scrivi(self, dati: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(dati), encoding="utf-8")
        os.replace(tmp, self._path)

    def richiedi(self, installation_id: str) -> tuple[str, float]:
        """Un codice monouso fresco per questa installazione. Non invalida i
        codici gia' emessi per la stessa installazione: due tentativi di
        collegamento aperti in parallelo non si rompono a vicenda."""
        codice = secrets.token_urlsafe(9)
        adesso = time.time()
        scadenza = adesso + self._ttl
        with self._lock:
            dati = self._leggi()
            dati["richieste"][codice] = {
                "installation": installation_id, "createdAt": adesso,
                "expiresAt": scadenza, "chatId": None, "nome": None, "stato": None,
            }
            self._scrivi(dati)
        return codice, scadenza

    def richiedi_ingresso(self, codice: str, chat_id: int, nome: str | None) -> str | None:
        """Il tap sul deep link (A03): se il codice esiste, non e' scaduto e
        non e' gia' stato consumato, registra chi ha chiesto di entrare e
        torna l'installazione per cui l'ha chiesto; altrimenti None. Non
        associa nulla: l'ingresso resta sospeso finche' 'approva' non lo
        conferma, coerente con S11/3 (il servizio e' chiuso, si entra su
        approvazione)."""
        with self._lock:
            dati = self._leggi()
            richiesta = dati["richieste"].get(codice)
            if richiesta is None or richiesta["chatId"] is not None:
                return None
            if time.time() > richiesta["expiresAt"]:
                return None
            richiesta["chatId"] = chat_id
            richiesta["nome"] = nome
            richiesta["stato"] = "in_attesa_gestore"
            self._scrivi(dati)
            return richiesta["installation"]

    def approva(self, codice: str) -> tuple[str, int, str | None] | None:
        """Il tap del gestore su 'Approva': se la richiesta esiste ed e'
        ancora in attesa, la finalizza in 'associazioni' e torna
        (installazione, chat del richiedente, nome). None se il codice e'
        sconosciuto o gia' risolto (un secondo tap sullo stesso messaggio non
        produce un secondo effetto)."""
        with self._lock:
            dati = self._leggi()
            richiesta = dati["richieste"].get(codice)
            if richiesta is None or richiesta.get("stato") != "in_attesa_gestore":
                return None
            richiesta["stato"] = "associato"
            adesso = time.time()
            dati["associazioni"][richiesta["installation"]] = {
                "chatId": richiesta["chatId"], "pairedAt": adesso, "lastSeenAt": adesso}
            self._scrivi(dati)
            return richiesta["installation"], richiesta["chatId"], richiesta.get("nome")

    def rifiuta(self, codice: str) -> tuple[str, int, str | None] | None:
        """Il tap del gestore su 'Rifiuta' (grilling 26: chi viene rifiutato
        lo sa): stessa forma di 'approva', ma non scrive mai in
        'associazioni'."""
        with self._lock:
            dati = self._leggi()
            richiesta = dati["richieste"].get(codice)
            if richiesta is None or richiesta.get("stato") != "in_attesa_gestore":
                return None
            richiesta["stato"] = "rifiutato"
            self._scrivi(dati)
            return richiesta["installation"], richiesta["chatId"], richiesta.get("nome")

    def segna_senza_gestore(self, codice: str) -> None:
        """Nessuno puo' ancora approvare (il relay non ha un gestore
        bootstrappato): la richiesta non resta sospesa per sempre, si marca
        come tale cosi' 'stato()' puo' dirlo con precisione a chi interroga."""
        with self._lock:
            dati = self._leggi()
            richiesta = dati["richieste"].get(codice)
            if richiesta is not None:
                richiesta["stato"] = "senza_gestore"
                self._scrivi(dati)

    def stato(self, codice: str) -> str:
        """'in_attesa' | 'in_attesa_gestore' | 'associato' | 'rifiutato' |
        'senza_gestore' | 'scaduto' | 'sconosciuto': quanto basta al pannello
        Notifiche per sapere quando smettere di aspettare e cosa dire."""
        with self._lock:
            richiesta = self._leggi()["richieste"].get(codice)
        if richiesta is None:
            return "sconosciuto"
        marcato = richiesta.get("stato")
        if marcato in ("associato", "rifiutato", "senza_gestore"):
            return marcato
        if richiesta["chatId"] is None:
            return "scaduto" if time.time() > richiesta["expiresAt"] else "in_attesa"
        return "in_attesa_gestore"

    def is_paired(self, chat_id: int) -> bool:
        """Vero se questa chat segue almeno un'installazione."""
        with self._lock:
            associazioni = self._leggi()["associazioni"]
        return any(record["chatId"] == chat_id for record in associazioni.values())

    def chat_id_di(self, installation_id: str) -> int | None:
        """A quale chat spingere il deliver di un'Interazione lanciata da
        questa installazione (D07): un'installazione ha una chat sola, quindi
        e' una lettura diretta, non una scelta fra piu' candidati."""
        with self._lock:
            record = self._leggi()["associazioni"].get(installation_id)
        return record["chatId"] if record else None

    def installazioni_di(self, chat_id: int) -> list[str]:
        """L'inverso di chat_id_di: le installazioni che questa chat segue in
        questo momento, la piu' di recente appaiata prima. Una chat puo'
        seguire piu' installazioni della stessa persona (grilling 9): due
        computer, un solo telefono."""
        with self._lock:
            associazioni = self._leggi()["associazioni"]
        candidati = [(installation_id, record["pairedAt"])
                    for installation_id, record in associazioni.items()
                    if record["chatId"] == chat_id]
        candidati.sort(key=lambda coppia: coppia[1], reverse=True)
        return [installation_id for installation_id, _ in candidati]

    def segna_vista(self, installation_id: str) -> None:
        """Il segnale di attivita' che sostituisce un battito dedicato (C02,
        S7-ter/5): il relay non ne apre uno apposta, ma ogni linea di tunnel
        che un'installazione apre (D03) e' gia' la prova che e' viva in
        questo momento. Nessun effetto se l'installazione non e' (piu')
        associata a nessuna chat: non c'e' 'ultima vista' da aggiornare per
        un'identita' che il pairing non conosce."""
        with self._lock:
            dati = self._leggi()
            record = dati["associazioni"].get(installation_id)
            if record is None:
                return
            record["lastSeenAt"] = time.time()
            self._scrivi(dati)

    def ultima_vista(self, installation_id: str) -> float | None:
        """None se l'installazione non e' associata, o se e' un'associazione
        anteriore a questo campo (mai vista dopo l'approvazione)."""
        with self._lock:
            record = self._leggi()["associazioni"].get(installation_id)
        return record.get("lastSeenAt") if record else None

    def stacca(self, installation_id: str) -> None:
        """Il gesto inverso del pairing (C02, S7-ter/5): dimentica
        un'installazione, cosi' una chat puo' liberarsi di un Mac cambiato o
        reinstallato senza aspettare che nessuno se ne accorga da solo.
        Nessun effetto se non era gia' associata a nulla."""
        with self._lock:
            dati = self._leggi()
            if dati["associazioni"].pop(installation_id, None) is not None:
                self._scrivi(dati)

    def emetti_bootstrap_gestore(self) -> str | None:
        """Un codice monouso per reclamare il ruolo di gestore, valido
        'self._ttl' secondi: None se il relay ha gia' un gestore (il ruolo
        non si riemette ne' ruota da qui). Idempotente finche' il codice
        emesso resta valido, cosi' rilanciare lo script di bootstrap non
        stampa un link diverso ogni volta."""
        with self._lock:
            dati = self._leggi()
            gestore = dati["gestore"]
            if gestore["chatId"] is not None:
                return None
            adesso = time.time()
            if (gestore.get("bootstrapCode")
                    and adesso <= (gestore.get("bootstrapExpiresAt") or 0)):
                return gestore["bootstrapCode"]
            codice = secrets.token_urlsafe(9)
            gestore["bootstrapCode"] = codice
            gestore["bootstrapExpiresAt"] = adesso + self._ttl
            self._scrivi(dati)
            return codice

    def gestore_chat_id(self) -> int | None:
        with self._lock:
            return self._leggi()["gestore"]["chatId"]

    def conferma_gestore(self, codice: str, chat_id: int) -> bool:
        """Il tap sul deep link di bootstrap: vero e reclama il ruolo solo se
        un gestore non e' gia' registrato e il codice combacia con quello
        pendente e non scaduto. Monouso per costruzione: il bootstrap viene
        cancellato appena consumato."""
        with self._lock:
            dati = self._leggi()
            gestore = dati["gestore"]
            if gestore["chatId"] is not None:
                return False
            if not gestore.get("bootstrapCode") or gestore["bootstrapCode"] != codice:
                return False
            if time.time() > (gestore.get("bootstrapExpiresAt") or 0):
                return False
            gestore["chatId"] = chat_id
            gestore["bootstrapCode"] = None
            gestore["bootstrapExpiresAt"] = None
            self._scrivi(dati)
            return True


def costruisci_pairing_start(store: GestorePairing, invia_messaggio: InviaMessaggio,
                             invia_bottoni: InviaBottoni) -> PairingStart:
    """La chiusura che GestoreWebhook (D04) chiama su un '/start <codice>':
    prova prima il bootstrap del gestore, poi una richiesta d'ingresso
    normale (A03). Testo fisso in italiano: il relay non serve la dashboard
    multilingua di 'payload/', e' infrastruttura a parte con un solo
    pubblico (chi risponde al bot). Nessun nome di progetto nel messaggio
    (grilling 3): il pairing e' per macchina, non per progetto, e a questo
    punto nessun progetto e' ancora entrato in scena."""
    def _on_start(codice: str, chat_id: int, nome: str | None = None) -> None:
        if store.conferma_gestore(codice, chat_id):
            invia_messaggio(chat_id, "Sei ora il gestore di questo relay. Le richieste "
                                       "di accesso arrivano qui, un tap per approvare o rifiutare.")
            return
        installation_id = store.richiedi_ingresso(codice, chat_id, nome)
        if installation_id is None:
            invia_messaggio(chat_id, "Codice di pairing non valido o scaduto. "
                                       "Riapri il pannello Notifiche di Atlas e riprova.")
            return
        gestore_chat = store.gestore_chat_id()
        if gestore_chat is None:
            store.segna_senza_gestore(codice)
            invia_messaggio(chat_id, "Il servizio non ha ancora un gestore configurato. "
                                       "Riprova piu' tardi.")
            return
        invia_messaggio(chat_id, "Richiesta inviata. Il servizio e' chiuso: ricevi qui la "
                                   "conferma appena il gestore da' il via libera.")
        invia_bottoni(gestore_chat, f"Richiesta di accesso da {nome or 'un utente Telegram'}.",
                      [("Approva", f"{PREFISSO_APPROVA}{codice}"),
                       ("Rifiuta", f"{PREFISSO_RIFIUTA}{codice}")])
    return _on_start


def costruisci_admin_decision(store: GestorePairing, invia_messaggio: InviaMessaggio,
                              modifica_messaggio: ModificaMessaggio) -> AdminDecision:
    """Il tap del gestore su 'Approva'/'Rifiuta' (A03). Torna True se il
    callback_data era per questo cancello (gestito, indipendentemente
    dall'esito) cosi' GestoreWebhook sa fermarsi qui invece di instradarlo
    come un tap di grafo; False se il prefisso non e' il suo, cosi' il
    normale instradamento verso il capability_resolver resta intatto.
    Un tap da una chat che non e' il gestore, o su un codice gia' risolto, e'
    assorbito qui senza traccia ne' effetto: stesso principio di
    'capability_resolver' per un identificativo sconosciuto."""
    def _decidi(dato: str, chat_id: int, message_id: int) -> bool:
        if dato.startswith(PREFISSO_APPROVA):
            azione, codice = "approva", dato[len(PREFISSO_APPROVA):]
        elif dato.startswith(PREFISSO_RIFIUTA):
            azione, codice = "rifiuta", dato[len(PREFISSO_RIFIUTA):]
        else:
            return False
        if chat_id != store.gestore_chat_id():
            return True
        esito = store.approva(codice) if azione == "approva" else store.rifiuta(codice)
        if esito is None:
            return True
        _installation_id, chat_richiedente, nome = esito
        chi = nome or "utente Telegram"
        if azione == "approva":
            modifica_messaggio(chat_id, message_id, f"Approvato: {chi}.")
            invia_messaggio(chat_richiedente, "Connesso ad Atlas. Da qui in poi ricevi qui "
                                                "le notifiche di questa macchina.")
        else:
            modifica_messaggio(chat_id, message_id, f"Rifiutato: {chi}.")
            invia_messaggio(chat_richiedente, "Richiesta di accesso rifiutata.")
        return True
    return _decidi


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
