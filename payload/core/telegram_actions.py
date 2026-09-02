"""D06: dal tap Telegram ricevuto sul tunnel (D03) alla risoluzione atomica
dell'Interaction (A04), con la capability (D01) come unico lasciapassare.

Il gestore costruito qui gira nel thread del tunnel dentro il processo di
Automata (automata.py lo avvia e lo ferma insieme al run): 'resolve_interaction'
pubblica il ResolutionEvent in-process, quindi una risposta valida sveglia
subito il runner in attesa (A05), senza aspettare la rilettura periodica del
grafo. Non solleva mai fuori da 'gestore': un tap che non supera un controllo
si scarta sul posto, coerente con relay_client.esegui() che assorbe comunque
ogni eccezione di on_event ma qui la scelta e' esplicita, non delegata.
"""
from __future__ import annotations

from collections.abc import Mapping

from . import capability, interactions, mutate, relay_client
from .config import Graph
from .store import StateError
from .strings import t


def gestore(graph: Graph, run_id: str, chiave_capability: str,
           config: relay_client.TunnelConfig, *, opener=None) -> relay_client.OnEvent:
    """Un on_event per la sessione (graph, run_id) di questo run. 'consumati'
    vive nella chiusura: un jti e' monouso per la durata di questo processo,
    la difesa in profondita' che D01 chiede oltre alla transizione atomica
    open->resolved del ledger."""
    consumati = capability.ConsumatiJti()

    def _on_event(evento: Mapping[str, object]) -> None:
        if evento.get("kind") != "callback":
            return  # solo un tap su un bottone porta una capability da verificare
        token = evento.get("callback_data")
        chat_id = evento.get("chat_id")
        message_id = evento.get("message_id")
        if not isinstance(token, str) or not isinstance(chat_id, int) or not isinstance(message_id, int):
            return
        try:
            payload = capability.verifica(chiave_capability, token, consumati=consumati)
        except capability.CapabilityRejected:
            return  # token non valido, scaduto o gia' consumato: nessuna traccia su Atlas
        if payload["graph"] != graph.slug or payload["runId"] != run_id:
            return  # capability di un'altra sessione: instradamento del relay o replay
        testo = _risolvi(graph, payload["interactionId"], payload["actionId"])
        kwargs = {} if opener is None else {"opener": opener}
        relay_client.aggiorna_messaggio(config, chat_id, message_id, testo, **kwargs)

    return _on_event


def _risolvi(graph: Graph, interaction_id: str, action_id: str) -> str:
    """Applica l'azione nella stessa transazione di ogni altra mutazione
    Atlas (mutate.editing pubblica il ResolutionEvent al commit riuscito,
    esattamente come B03/serve_actions.py). Un'Interaction gia' risolta,
    scaduta o un'azione non ammessa non e' un guasto di trasporto: e' un tap
    arrivato in ritardo o due volte, e si traduce in un messaggio per
    l'utente invece che in un'eccezione."""
    try:
        with mutate.editing(graph) as g:
            resolved = interactions.resolve_interaction(g, interaction_id, action_id)
    except StateError:
        return t("telegram_actions.rejected")
    label = next(azione["label"] for azione in resolved["allowedActions"]
                if azione["id"] == action_id)
    return t("telegram_actions.resolved", label=label)
