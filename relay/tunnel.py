"""Lato relay del tunnel D03: chi puo' parlare (bearer) e dove va un evento
(le linee aperte in questo momento). Il relay instrada per
installazione (A05, docs/atlas-relay-design.md SS4-bis), mai per progetto: un
progetto non ha identita' qui, e' solo un'etichetta dentro un messaggio. Il
relay instrada soltanto: non apre ne' risolve un'Interaction, non vede il
ledger Atlas (D01).

Nessuna coda di rimessaggio fra una disconnessione e l'altra, per costruzione
(D01, grilling 8): un push verso un'installazione senza linea aperta in
questo momento si perde, esattamente come una consegna Telegram verso un
utente irraggiungibile, e chi ha premuto lo scopre subito (SS7-bis/13). Chi
spinge un evento (D06, quando esiste) tratta un 'push' che non trova nessuno
come un canale momentaneamente giu', non come un errore.
"""
from __future__ import annotations

import hmac
import threading
from collections.abc import Callable, Mapping
from queue import Queue


class TunnelRejected(ValueError):
    """Bearer del tunnel assente o non valido."""


def verifica_bearer(header_autorizzazione: str | None, atteso: str) -> None:
    """hmac.compare_digest per non aprire un confronto a tempo sul bearer."""
    prefisso = "Bearer "
    if not header_autorizzazione or not header_autorizzazione.startswith(prefisso):
        raise TunnelRejected("Authorization Bearer del tunnel assente")
    token = header_autorizzazione[len(prefisso):]
    if not hmac.compare_digest(token, atteso):
        raise TunnelRejected("bearer del tunnel non valido")


class RegistroTunnel:
    """Le code aperte per ogni installazione, in memoria di processo.

    Piu' connessioni per la stessa installazione sono ammesse (un riavvio del
    client puo' sovrapporsi per un istante alla connessione vecchia, o due
    lavori dello stesso computer possono girare insieme): un push arriva a
    tutte le linee aperte di quell'installazione, non solo alla piu' recente.
    Chi riceve un evento che non lo riguarda lo scarta per conto suo (la
    capability porta gia' graph e runId, D01): il relay non deve sapere quale
    linea e' quella giusta fra piu' linee della stessa installazione.
    """

    def __init__(self) -> None:
        self._installazioni: dict[str, set[Queue]] = {}
        self._lucchetto = threading.Lock()

    def connetti(self, installation_id: str) -> Queue:
        coda: Queue = Queue()
        with self._lucchetto:
            self._installazioni.setdefault(installation_id, set()).add(coda)
        return coda

    def disconnetti(self, installation_id: str, coda: Queue) -> None:
        with self._lucchetto:
            code = self._installazioni.get(installation_id)
            if code is None:
                return
            code.discard(coda)
            if not code:
                del self._installazioni[installation_id]

    def push(self, installation_id: str, evento: Mapping[str, object]) -> bool:
        """Vero se almeno una linea di questa installazione era aperta e ha
        ricevuto l'evento; falso se la linea non c'e' piu' (grilling 8): nessuna
        coda, chi ha premuto lo scopre subito (SS7-bis/13)."""
        with self._lucchetto:
            code = list(self._installazioni.get(installation_id, ()))
        for coda in code:
            coda.put(dict(evento))
        return bool(code)


def costruisci_instradamento(risolvi: Callable[[int], str | None],
                             registro: RegistroTunnel) -> Callable[[dict], None]:
    """Il sink che il webhook Telegram (D04) chiama per ogni evento
    verificato (D06): risolve l'installazione della chat gia' associata
    (pairing.GestorePairing, A02) e spinge l'evento sulla sola linea aperta
    di quella installazione, a nessun'altra (A05). Un'installazione senza
    tunnel aperto (nessun Autopilot in ascolto) perde l'evento, per
    costruzione (D01): non e' compito del relay tenerlo in coda."""
    def _sink(evento: dict) -> None:
        chat_id = evento.get("chat_id")
        if not isinstance(chat_id, int):
            return
        installation_id = risolvi(chat_id)
        if installation_id is None:
            return
        registro.push(installation_id, evento)
    return _sink
