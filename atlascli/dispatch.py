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
from .strings import set_language, t
from .version import current_version

RESERVED = {"install", "update", "uninstall", "list", "lang"}

def cmd_lang(args) -> int:
    """'atlas lang [it|en]': senza valore stampa il default globale, con valore lo cambia.

    Non tocca alcun progetto gia' installato: solo i default per install futuri e
    per chi non ha un override esplicito al prossimo update/lang che lo tocca.
    """
    if args.valore is None:
        print(registry.language_for(None))
        return 0
    registry.set_language(args.valore)
    return 0


COMANDI = {"install": install_cmd.cmd_install, "uninstall": install_cmd.cmd_uninstall,
           "update": self_update.cmd_update, "list": list_cmd.cmd_list, "lang": cmd_lang}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atlas", description=t("parser.description"),
                                     epilog=t("parser.epilog"),
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("install", help=t("help.install"))
    p.add_argument("path", nargs="?", default=".", help=t("opt.path"))
    p.add_argument("--slug", help=t("opt.slug"))
    p.add_argument("--no-registry", action="store_true", help=t("opt.no_registry"))
    p.add_argument("--yes", action="store_true", help=t("opt.yes"))
    p.add_argument("--graph", help=t("opt.graph"))
    p.add_argument("--no-hooks", action="store_true", help=t("opt.no_hooks"))
    p.add_argument("--no-claude-md", action="store_true", help=t("opt.no_claude_md"))
    p.add_argument("--dry-run", action="store_true", help=t("opt.dry_run"))
    p.add_argument("--lang", choices=("it", "en"), help=t("opt.lang"))

    p = sub.add_parser("uninstall", help=t("help.uninstall"))
    p.add_argument("path", nargs="?", default=".", help=t("opt.path"))

    sub.add_parser("update", help=t("help.update"))

    p = sub.add_parser("list", help=t("help.list"))
    p.add_argument("--prune", action="store_true", help=t("opt.prune"))

    p = sub.add_parser("lang", help=t("help.lang"))
    p.add_argument("valore", nargs="?", choices=("it", "en"), help=t("opt.lang_valore"))

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
    slug_noti = ", ".join(sorted(registry.load()["projects"])) or t("dispatch.nessuno")
    print(t("dispatch.sconosciuto", token=token, slug_noti=slug_noti,
            comandi=", ".join(sorted(RESERVED))), file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    set_language(registry.language_for(argv[0] if argv and argv[0] not in RESERVED else None))

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
        if resto and resto[0] == "update":
            from .harness_update import cmd_slug_update
            return cmd_slug_update(primo, resto)
        if resto and resto[0] == "redraw":
            from .harness_update import cmd_slug_redraw
            return cmd_slug_redraw(primo, resto)
        if resto and resto[0] == "lang":
            from .harness_update import cmd_slug_lang
            return cmd_slug_lang(primo, resto)
        return list_cmd.scheda_progetto(primo)

    radice = _radice_locale(Path.cwd())
    if radice is not None:
        _passthrough(radice, argv)  # non ritorna: os.execv sostituisce il processo

    return _errore_sconosciuto(primo)
