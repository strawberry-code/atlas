"""'atlas <slug> update [path]': aggiorna l'harness di un progetto registrato.

Ri-estrae solo le cartelle sostituibili (core/bin/hooks/skills/templates/VERSION),
esattamente come rilanciare oggi l'installer: config.json, graphs/, scripts/ restano
intatti. Se [path] e' dato, ripunta lo slug su quel path prima di aggiornare.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

from . import registry
from .install_cmd import Installer


def build_parser(slug: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"atlas {slug}")
    sub = parser.add_subparsers(dest="verbo", required=True)
    p = sub.add_parser("update", help="aggiorna il motore di questo progetto")
    p.add_argument("path", nargs="?", help="ripunta lo slug su questo path prima di aggiornare")
    p.add_argument("--yes", action="store_true", help="niente domande, usa i default")
    p.add_argument("--no-hooks", action="store_true", help="non toccare .claude/settings.json")
    p.add_argument("--no-claude-md", action="store_true", help="non toccare CLAUDE.md")
    p.add_argument("--dry-run", action="store_true", help="dice cosa farebbe, senza farlo")
    return parser


def cmd_slug_update(slug: str, argv: list[str]) -> int:
    args = build_parser(slug).parse_args(argv)

    if args.path:
        registry.repoint(slug, Path(args.path))

    path = registry.resolve(slug)
    if path is None:
        print(f"\n  '{slug}' non è registrato. Registralo con "
              f"'atlas install <path> --slug {slug}'.\n", file=sys.stderr)
        return 1

    stato = registry.status_of(path)
    if stato != registry.STATO_OK:
        print(f"\n  '{slug}' punta a {path} ({stato}). "
              f"Reinstalla con 'atlas install {path} --slug {slug}'.\n", file=sys.stderr)
        return 1

    installer_args = SimpleNamespace(
        yes=args.yes, no_hooks=args.no_hooks, no_claude_md=args.no_claude_md,
        dry_run=args.dry_run, graph=None, slug=None, no_registry=False,
    )
    return Installer(path, installer_args).run()
