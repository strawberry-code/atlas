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
