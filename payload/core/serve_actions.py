"""Applica un'azione di card del pannello Notifiche al lifecycle atomico.

Spezzato da serve.py, che sta gia' sopra le 200 righe convenzionali: qui c'e'
il solo POST /interactions/<id>/<action>, la' resta il resto del server (la
dashboard viva, il canale SSE, i lucchetti remoti).
"""
from __future__ import annotations

import re

from . import interactions, mutate
from .config import ConfigError, Graph
from .store import StateError

# /interactions/<id>/<action>: le sole due variabili di un'azione di card, la
# stessa forma di data-interaction/data-action nel markup di render_notifiche.
PERCORSO = re.compile(r"^/interactions/([^/]+)/([^/]+)$")


def applica(ref: Graph, interaction_id: str, action_id: str) -> tuple[int, dict]:
    """Applica l'azione dentro la stessa transazione di ogni altra mutazione
    Atlas: il commit e' cio' che risveglia Autopilot (mutate.editing pubblica
    il ResolutionEvent), niente scorciatoia qui.

    Un'azione non fra quelle dichiarate per questa Interaction, o una
    Interaction gia' risolta (doppio invio, o due schede aperte sulla stessa
    card), torna come 409: resolve_interaction alza StateError in entrambi i
    casi, e lo store serializza i due invii sullo stesso lock di scrittura
    del grafo, cosi' solo uno dei due vince davvero.
    """
    if action_id not in interactions.ACTION_IDS:
        return 400, {"ok": False}
    try:
        with mutate.editing(ref) as g:
            interactions.resolve_interaction(g, interaction_id, action_id)
    except StateError as errore:
        return 409, {"ok": False, "error": str(errore)}
    except ConfigError:
        return 503, {"ok": False}
    return 200, {"ok": True}
