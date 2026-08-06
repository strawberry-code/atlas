"""Che cosa ha toccato una sessione di lavoro, secondo git.

Serve a popolare artifacts alla chiusura di un nodo senza chiedere niente a chi chiude:
un campo che si riempie solo passando un flag resta vuoto, e il controllo di
sconfinamento di doctor resta inerte.
"""
from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

ESCLUSI = (".atlas/",)


def _git(root: Path, *argomenti: str) -> list[str]:
    esito = subprocess.run(["git", *argomenti], cwd=root, capture_output=True, text=True)
    return esito.stdout.splitlines() if esito.returncode == 0 else []


def touched(root: Path, since: str | None = None) -> list[str]:
    """I file del progetto modificati o creati e non ancora committati, esclusi quelli
    dell'harness. Con since (timestamp ISO) tiene solo quelli toccati da allora in poi.

    Il commit di chiusura arriva dopo close, quindi qui il lavoro del nodo e' ancora
    tutto nel working tree: e' il momento giusto per fotografarlo.
    """
    if not (root / ".git").exists():
        return []
    candidati = (set(_git(root, "diff", "--name-only", "HEAD"))
                 | set(_git(root, "ls-files", "--others", "--exclude-standard")))
    soglia = datetime.fromisoformat(since) if since else None
    tenuti = []
    for percorso in candidati:
        if not percorso or percorso.startswith(ESCLUSI):
            continue
        file = root / percorso
        if not file.is_file():
            continue
        if soglia and datetime.fromtimestamp(file.stat().st_mtime).astimezone() < soglia:
            continue
        tenuti.append(percorso)
    return sorted(tenuti)
