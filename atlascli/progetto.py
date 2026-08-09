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
from .strings import set_language, t

DIRNAME = ".atlas"


def template(nome: str) -> str:
    """I template stanno nel pacchetto insieme al motore: unica copia, unica fonte."""
    from core.risorse import leggi_template
    return leggi_template(nome)


def cmd_lang_progetto(progetto: Path, valore: str | None) -> int:
    """Cambia la lingua dei contenuti di un progetto e rigenera quel che ne dipende."""
    root = progetto / DIRNAME
    dati = json.loads((root / "config.json").read_text(encoding="utf-8"))
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
    registry.set_language(valore, slug=registry.find_by_path(progetto))
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
