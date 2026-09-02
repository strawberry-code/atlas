"""Lato relay del tunnel D03: chi puo' parlare (bearer di progetto) e dove va
un evento (le sessioni connesse in questo momento). Il relay instrada soltanto:
non apre ne' risolve un'Interaction, non vede il ledger Atlas (D01).

Nessuna coda di rimessaggio fra una disconnessione e l'altra, per costruzione
(D01): un push verso una sessione non connessa in questo momento si perde,
esattamente come una consegna Telegram verso un utente irraggiungibile. Chi
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
    """hmac.compare_digest per non aprire un confronto a tempo sul bearer,
    stessa disciplina di telegram_webhook.verifica_segreto (D04)."""
    prefisso = "Bearer "
    if not header_autorizzazione or not header_autorizzazione.startswith(prefisso):
        raise TunnelRejected("Authorization Bearer del tunnel assente")
    token = header_autorizzazione[len(prefisso):]
    if not hmac.compare_digest(token, atteso):
        raise TunnelRejected("bearer del tunnel non valido")


class RegistroTunnel:
    """Le code aperte per ogni sessione (graph, runId), in memoria di processo.

    Piu' connessioni per la stessa sessione sono ammesse (un riavvio del client
    puo' sovrapporsi per un istante alla connessione vecchia): un push arriva a
    tutte, non solo alla piu' recente.
    """

    def __init__(self) -> None:
        self._sessioni: dict[tuple[str, str], set[Queue]] = {}
        self._lucchetto = threading.Lock()

    def connetti(self, graph: str, run_id: str) -> Queue:
        coda: Queue = Queue()
        with self._lucchetto:
            self._sessioni.setdefault((graph, run_id), set()).add(coda)
        return coda

    def disconnetti(self, graph: str, run_id: str, coda: Queue) -> None:
        with self._lucchetto:
            code = self._sessioni.get((graph, run_id))
            if code is None:
                return
            code.discard(coda)
            if not code:
                del self._sessioni[(graph, run_id)]

    def push(self, graph: str, run_id: str, evento: Mapping[str, object]) -> bool:
        """Vero se almeno una connessione era aperta e ha ricevuto l'evento."""
        with self._lucchetto:
            code = list(self._sessioni.get((graph, run_id), ()))
        for coda in code:
            coda.put(dict(evento))
        return bool(code)

    def sessioni_di(self, graph: str) -> list[str]:
        """I runId con almeno una connessione aperta in questo momento per
        questo progetto (D06): il pairing e' per progetto, non per sessione
        (D05), quindi chi instrada un tap non conosce gia' il runId giusto e
        deve chiederlo qui."""
        with self._lucchetto:
            return [run_id for (g, run_id) in self._sessioni if g == graph]


def costruisci_instradamento(progetto_di: Callable[[int], str | None],
                             registro: RegistroTunnel) -> Callable[[dict], None]:
    """Il sink che il webhook Telegram (D04) chiama per ogni evento
    verificato (D06): risolve il progetto del chat_id gia' associato
    (pairing.GestorePairing.progetto_di) e spinge l'evento a ogni sessione
    (graph, runId) connessa in questo momento per quel progetto. Un progetto
    senza tunnel aperto (nessun Automata in ascolto) perde l'evento, per
    costruzione (D01): non e' compito del relay tenerlo in coda."""
    def _sink(evento: dict) -> None:
        chat_id = evento.get("chat_id")
        if not isinstance(chat_id, int):
            return
        graph = progetto_di(chat_id)
        if graph is None:
            return
        for run_id in registro.sessioni_di(graph):
            registro.push(graph, run_id, evento)
    return _sink
