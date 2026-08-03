"""Dove vive lo stato globale del CLI: un solo file JSON, non piu' una home a se'.

Distinto da .atlas/ dentro un progetto (quello e' per-progetto, questo e' per-utente).
Funzione e non costante di modulo apposta: va poter cambiare a runtime (override via
env), i test lo fanno ad ogni chiamata senza dover ricaricare moduli.
"""
from __future__ import annotations

import os
from pathlib import Path


def config_path() -> Path:
    return Path(os.environ.get("ATLAS_CONFIG", str(Path.home() / ".config" / "atlas.json"))).expanduser()
