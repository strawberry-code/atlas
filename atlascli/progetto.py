"""Gesti su un progetto gia' installato: la sua lingua, e il ridisegno dei suoi grafi.

Fuori da install_cmd.py perche' non installano niente: lavorano su un progetto che
esiste gia'. Vivono qui anche i template, che dalla 0.7 non stanno piu' nel progetto
ma nel pacchetto, insieme al motore.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from . import registry
from .errori import leggi_json
from .strings import set_language, t

DIRNAME = ".atlas"


def template(nome: str) -> str:
    """I template stanno nel pacchetto insieme al motore: unica copia, unica fonte."""
    from core.risorse import leggi_template
    return leggi_template(nome)


def cmd_lang_progetto(progetto: Path, valore: str | None) -> int:
    """Cambia la lingua dei contenuti di un progetto e rigenera quel che ne dipende."""
    root = progetto / DIRNAME
    dati = leggi_json(root / "config.json")
    if valore is None:
        print(dati.get("language", "it"))
        return 0
    dati["language"] = valore
    (root / "config.json").write_text(json.dumps(dati, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
    set_language(valore)
    args = SimpleNamespace(yes=True, no_hooks=True, no_claude_md=False, dry_run=False,
                           graph=None, slug=None, no_registry=True)
    from .install_cmd import Installer
    installer = Installer(progetto, args, valore)
    installer.scrive_documenti()
    installer.contratto()
    # Solo se il progetto e' nel registro: con slug None, set_language cambierebbe
    # il default di ogni installazione futura sulla macchina. Capita clonando un
    # repo Atlas altrui, dove .atlas/config.json c'e' ma il registro e' per utente,
    # e la lingua della propria macchina non c'entra con quella di quel progetto.
    if noto := registry.find_by_path(progetto):
        registry.set_language(valore, slug=noto)
    print(t("install.lingua_progetto", lingua=valore))
    return ridisegna(progetto)


def ridisegna(progetto: Path) -> int:
    """Rigenera ticket, mappa e dashboard di ogni grafo, in questo stesso processo.

    Prima serviva un sottoprocesso per grafo, perche' il motore del progetto era un
    altro programma. Adesso e' questo, quindi basta chiamarlo.
    """
    from core.cli import refresh
    from core.config import workspace
    from core.store import load
    ws = workspace(progetto)
    for slug in ws.slugs():
        ref = ws.graph(slug)
        refresh(ref, load(ref.json_path))
    return 0
