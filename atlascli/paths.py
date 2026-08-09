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


def motore_installato(progetto: Path) -> bool:
    """Vero se in questo progetto c'e' un motore Atlas, di questa forma o di quella prima.

    L'archivio unico ha preso il posto di core/ piu' bin/. La forma vecchia resta
    riconosciuta apposta: e' quella dei progetti che devono ancora migrare, e se il
    CLI globale li dichiarasse non validi rifiuterebbe di aggiornare proprio loro.
    """
    root = progetto / ".atlas"
    return (root / "atlas").is_file() or (root / "core").is_dir()
