"""Ambiente deterministico per la suite.

Atlas legge CLAUDE_PID e CLAUDE_CODE_SESSION_ID per sapere chi tiene un lucchetto
e se quel processo e' ancora vivo. Lanciando la suite da dentro una sessione
Claude Code quelle variabili ci sono e puntano a un processo davvero vivo,
quindi ogni claim scritto da un test nasce 'live': i test che si aspettano un
lucchetto orfano fallivano li' e passavano da un terminale nudo, cioe' la suite
diceva verde o rosso a seconda di chi la lanciava. La sessione ospite non e' un
dato del test: si toglie qui una volta, per tutti i moduli.
"""
from __future__ import annotations

import os

for _variabile in ("CLAUDE_PID", "CLAUDE_CODE_SESSION_ID"):
    os.environ.pop(_variabile, None)


def waiter_risolutore(ref, mutate, interactions):
    """Un interaction_waiter che risponde subito alla card aperta dal runner.

    Da A05 un run che non puo' proseguire apre un'Interazione e aspetta una
    persona: un test che non risponde resta appeso fino alla scadenza della card,
    cioe' un giorno. L'azione si prende fra quelle dichiarate nella card, perche'
    cambiano con l'evento e una scelta fissa varrebbe solo per uno.
    """
    def rispondi(graph, run_id, timeout=None):
        with mutate.editing(ref) as state:
            card = next(item for item in state.data["interactions"]
                        if item["graph"] == graph and item["runId"] == run_id
                        and item["status"] == "open")
            interactions.resolve_interaction(state, card["id"],
                                             card["allowedActions"][0]["id"])
        return interactions.wait_for_resolution(graph, run_id)

    return rispondi
