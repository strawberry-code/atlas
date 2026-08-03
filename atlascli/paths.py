"""Dove vive lo stato globale del CLI: home dell'utente, registro dei progetti.

Distinto da .atlas/ dentro un progetto (quello e' per-progetto, questo e' per-utente):
stesso nome di cartella, path assoluti sempre diversi, mai in conflitto reale.
Funzioni e non costanti di modulo apposta: ATLAS_HOME va poter cambiare a runtime
(override via env), i test lo fanno ad ogni chiamata senza dover ricaricare moduli.
"""
from __future__ import annotations

import os
from pathlib import Path


def atlas_home() -> Path:
    return Path(os.environ.get("ATLAS_HOME", str(Path.home() / ".atlas"))).expanduser()


def registry_path() -> Path:
    return atlas_home() / "registry.json"
