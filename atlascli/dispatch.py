"""Il dispatcher del CLI globale: riservato -> slug registrato -> passthrough locale -> errore.

E' l'unico punto che decide se un comando e' del CLI globale (install/update/
uninstall/list) o di un progetto (status/claim/close/...): i comandi di progetto
non li conosce affatto, li esegue com'e' via os.execv sull'entrypoint del progetto
bersaglio (payload/bin/atlas, invariato). Sostituzione di processo e non
subprocess/import in-process apposta: evita che il pacchetto 'core' imbustato nel
CLI globale collida in sys.modules con quello del progetto bersaglio, ed eredita
cwd/env/stdio/segnali esattamente come fa git per i suoi comandi esterni.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import install_cmd, list_cmd, registry, self_update
from .version import current_version

RESERVED = {"install", "update", "uninstall", "list"}

COMANDI = {"install": install_cmd.cmd_install, "uninstall": install_cmd.cmd_uninstall,
           "update": self_update.cmd_update, "list": list_cmd.cmd_list}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atlas",
                                      description="Installa/aggiorna l'harness Atlas nei progetti.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("install", help="installa l'harness in un progetto")
    p.add_argument("path", nargs="?", default=".", help="cartella del progetto (default: quella corrente)")
    p.add_argument("--slug", help="nome nel registro globale (default: nome della cartella)")
    p.add_argument("--no-registry", action="store_true",
                   help="non registrare il progetto in ~/.atlas/registry.json")
    p.add_argument("--yes", action="store_true", help="niente domande, usa i default")
    p.add_argument("--graph", help="crea subito un grafo con questo slug")
    p.add_argument("--no-hooks", action="store_true", help="non toccare .claude/settings.json")
    p.add_argument("--no-claude-md", action="store_true", help="non toccare CLAUDE.md")
    p.add_argument("--dry-run", action="store_true", help="dice cosa farebbe, senza farlo")

    p = sub.add_parser("uninstall", help="rimuove il motore da un progetto, lascia i dati")
    p.add_argument("path", nargs="?", default=".", help="cartella del progetto (default: quella corrente)")

    sub.add_parser("update", help="aggiorna il CLI globale (mai i progetti)")

    p = sub.add_parser("list", help="progetti registrati e il loro stato")
    p.add_argument("--prune", action="store_true", help="rimuove dal registro le voci morte")

    return parser


def _radice_locale(partenza: Path) -> Path | None:
    for cartella in (partenza, *partenza.parents):
        if (cartella / ".atlas" / "core").is_dir():
            return cartella
    return None


def _passthrough(radice: Path, argv: list[str]) -> None:
    entrypoint = radice / ".atlas" / "bin" / "atlas"
    os.execv(sys.executable, [sys.executable, str(entrypoint), *argv])


def _errore_sconosciuto(token: str) -> int:
    slug_noti = ", ".join(sorted(registry.load()["projects"])) or "nessuno"
    print(f"\n  '{token}' non è un comando di atlas, né un progetto registrato "
          f"({slug_noti}), né siamo dentro un progetto con .atlas/ installato.\n"
          f"  Comandi globali: {', '.join(sorted(RESERVED))}\n", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)

    if not argv or argv[0] in ("-h", "--help"):
        build_parser().print_help()
        return 0
    if argv[0] == "--version":
        print(current_version())
        return 0

    primo = argv[0]
    if primo in RESERVED:
        args = build_parser().parse_args(argv)
        return COMANDI[args.cmd](args)

    if registry.resolve(primo) is not None:
        resto = argv[1:]
        if not resto or resto[0] != "update":
            return list_cmd.scheda_progetto(primo)
        from .harness_update import cmd_slug_update
        return cmd_slug_update(primo, resto)

    radice = _radice_locale(Path.cwd())
    if radice is not None:
        _passthrough(radice, argv)  # non ritorna: os.execv sostituisce il processo

    return _errore_sconosciuto(primo)
