"""'atlas <slug> update [path]', 'atlas <slug> redraw' e 'atlas <slug> lang [it|en]':
aggiornano l'harness, ridisegnano le dashboard, o cambiano la lingua di un progetto
registrato.

update ri-estrae solo le cartelle sostituibili (core/bin/hooks/skills/templates/VERSION),
esattamente come rilanciare oggi l'installer: config.json, graphs/, scripts/ restano
intatti. Poi ridisegna ogni grafo col motore appena aggiornato, altrimenti le dashboard
su disco restano generate dal motore vecchio finche' qualcuno non se ne accorge (e' il
motore che e' cambiato, mai il grafo: aggiornare senza ridisegnare lascia l'harness e la
sua stessa dashboard disallineati). redraw fa solo quell'ultimo passo, da solo: utile
quando serve rigenerare senza toccare il motore. lang in piu' rigenera ogni grafo nella
nuova lingua: la sincronia di skill/CONTRACT.md/config.json deve completarsi PRIMA di
quel loop, altrimenti si rigenera con i template vecchi.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from . import registry
from .install_cmd import Installer
from .strings import set_language, t


def _parser_update(slug: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"atlas {slug} update")
    parser.add_argument("path", nargs="?", help=t("harness.help_path"))
    parser.add_argument("--yes", action="store_true", help=t("opt.yes"))
    parser.add_argument("--no-hooks", action="store_true", help=t("opt.no_hooks"))
    parser.add_argument("--no-claude-md", action="store_true", help=t("opt.no_claude_md"))
    parser.add_argument("--dry-run", action="store_true", help=t("opt.dry_run"))
    return parser


def _parser_redraw(slug: str) -> argparse.ArgumentParser:
    return argparse.ArgumentParser(prog=f"atlas {slug} redraw", description=t("harness.help_redraw"))


def _parser_lang(slug: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"atlas {slug} lang")
    parser.add_argument("valore", nargs="?", choices=("it", "en"), help=t("harness.help_lang_valore"))
    return parser


def _risolvi_progetto(slug: str) -> Path | None:
    path = registry.resolve(slug)
    if path is None:
        print(t("harness.non_registrato", slug=slug), file=sys.stderr)
        return None
    stato = registry.status_of(path)
    if stato != registry.STATO_OK:
        print(t("harness.non_valido", slug=slug, path=path, stato=stato), file=sys.stderr)
        return None
    return path


def _redraw_all(path: Path) -> tuple[list[str], list[str]]:
    """Rilancia il render di ogni grafo del progetto. Ritorna (tutti, falliti).

    Un sottoprocesso per grafo, mai un import in-process: stesso motivo del
    passthrough in dispatch.py, il pacchetto 'core' del motore locale non deve
    mai collidere in sys.modules con quello imbustato nel CLI globale.
    """
    grafi_dir = path / ".atlas" / "graphs"
    grafi = sorted(p.name for p in grafi_dir.iterdir() if (p / "graph.json").is_file()) \
        if grafi_dir.is_dir() else []
    entrypoint = path / ".atlas" / "bin" / "atlas"
    falliti = [grafo for grafo in grafi
               if subprocess.run([sys.executable, str(entrypoint), "-g", grafo, "render"],
                                  cwd=path).returncode != 0]
    return grafi, falliti


def _riepilogo_redraw(grafi: list[str], falliti: list[str]) -> str:
    riepilogo = t("harness.redraw_riepilogo", n=len(grafi) - len(falliti), totale=len(grafi))
    if falliti:
        riepilogo += t("harness.falliti", elenco=", ".join(falliti))
    return riepilogo


def cmd_slug_update(slug: str, argv: list[str]) -> int:
    """argv include il verbo 'update' in testa: qui si scarta prima di fare parsing."""
    args = _parser_update(slug).parse_args(argv[1:])
    if args.path:
        registry.repoint(slug, Path(args.path))

    path = _risolvi_progetto(slug)
    if path is None:
        return 1

    lingua = registry.language_for(slug)
    set_language(lingua)
    installer_args = SimpleNamespace(
        yes=args.yes, no_hooks=args.no_hooks, no_claude_md=args.no_claude_md,
        dry_run=args.dry_run, graph=None, slug=None, no_registry=False,
    )
    esito = Installer(path, installer_args, lingua).run()
    if esito != 0 or args.dry_run:
        return esito

    grafi, falliti = _redraw_all(path)
    print(_riepilogo_redraw(grafi, falliti))
    return 1 if falliti else 0


def cmd_slug_redraw(slug: str, argv: list[str]) -> int:
    """argv include il verbo 'redraw' in testa: qui si scarta prima di fare parsing."""
    _parser_redraw(slug).parse_args(argv[1:])
    path = _risolvi_progetto(slug)
    if path is None:
        return 1

    set_language(registry.language_for(slug))
    grafi, falliti = _redraw_all(path)
    print(_riepilogo_redraw(grafi, falliti))
    return 1 if falliti else 0


def cmd_slug_lang(slug: str, argv: list[str]) -> int:
    """argv include il verbo 'lang' in testa: qui si scarta prima di fare parsing."""
    args = _parser_lang(slug).parse_args(argv[1:])

    if args.valore is None:
        print(registry.language_for(slug))
        return 0

    path = _risolvi_progetto(slug)
    if path is None:
        return 1

    registry.set_language(args.valore, slug=slug)
    set_language(args.valore)
    installer_args = SimpleNamespace(
        yes=True, no_hooks=False, no_claude_md=False, dry_run=False,
        graph=None, slug=None, no_registry=False,
    )
    esito = Installer(path, installer_args, args.valore).run()
    if esito != 0:
        return esito

    grafi, falliti = _redraw_all(path)
    riepilogo = t("harness.lang_riepilogo", n=len(grafi) - len(falliti), totale=len(grafi), lingua=args.valore)
    if falliti:
        riepilogo += t("harness.falliti", elenco=", ".join(falliti))
    print(riepilogo)
    return 1 if falliti else 0
