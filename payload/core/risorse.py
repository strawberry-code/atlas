"""I template viaggiano dentro il pacchetto, non dentro il progetto.

Prima stavano dentro il progetto e si leggevano con Path: erano file
che nessuno modificava mai, e che a ogni aggiornamento del motore andavano riscritti.
Ora sono risorse del package, quindi importlib.resources e non open(): dentro un
zipapp i file dati non si aprono con Path, e quel percorso e' proprio quello che il
CLI usa in produzione.

Dai sorgenti (sviluppo e test) core/templates/ puo' non esistere ancora, perche' e'
build.py a copiarcelo da payload/templates/: in quel caso si legge da li'.
"""
from __future__ import annotations

from importlib.resources import files
from pathlib import Path

PACCHETTO = "core.templates"
# payload/core/risorse.py -> payload/templates/
SORGENTI = Path(__file__).resolve().parent.parent / "templates"


def leggi_template(nome: str) -> str:
    try:
        return (files(PACCHETTO) / nome).read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError):
        return (SORGENTI / nome).read_text(encoding="utf-8")


def elenco_template() -> list[str]:
    """I nomi disponibili, per chi deve controllare che una lingua sia completa."""
    try:
        return sorted(r.name for r in files(PACCHETTO).iterdir() if r.is_file())
    except ModuleNotFoundError:
        return sorted(p.name for p in SORGENTI.iterdir() if p.is_file())
