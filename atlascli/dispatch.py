"""Il dispatcher dell'unico atlas: gestione del parco progetti e lavoro sul grafo.

Dalla 0.7 e' un programma solo. I comandi di gestione (install, uninstall, update,
list, lang) stanno qui; quelli del grafo (status, take, close, ...) li mette nello
stesso elenco core.cli.aggiungi_comandi, e finiscono in core.cli.esegui. Un utente
vede un help solo e non deve sapere che dentro ci sono due strati.

Prima il motore stava dentro ogni progetto e questo file gli girava i comandi che
non conosceva. Quel passaggio non esiste piu': niente due binari con lo stesso nome,
niente blob nel git di chi usa Atlas, niente help che risponde da due programmi.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import install_cmd, list_cmd, progetto, registry, self_update
from .errori import ErroreAtlas
from .strings import set_language, t
from .version import current_version

RESERVED = {"install", "update", "uninstall", "list", "lang"}

def cmd_lang(args) -> int:
    """'atlas lang [it|en]': la lingua del progetto in cui ti trovi.

    Con --global si tocca invece il default dei progetti futuri. Sono due cose
    diverse e nessuna delle due deve dipendere da dove ti trovi per caso, quindi
    la distinzione la fa un flag e non la posizione.
    """
    if args.globale or progetto_qui() is None:
        if args.valore is None:
            print(registry.language_for(None))
            return 0
        registry.set_language(args.valore)
        return 0
    return progetto.cmd_lang_progetto(progetto_qui(), args.valore)


COMANDI = {"install": install_cmd.cmd_install, "uninstall": install_cmd.cmd_uninstall,
           "update": self_update.cmd_update, "list": list_cmd.cmd_list, "lang": cmd_lang}


def build_parser() -> argparse.ArgumentParser:
    # Il parser del motore, non quello nudo di argparse: e' quello che su 'atlas
    # <slug> render' spiega come si sceglie un grafo invece di elencare i comandi.
    from core.cli import Parser, aggiungi_comandi
    parser = Parser(prog="atlas", description=t("parser.description"),
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

    p = sub.add_parser("update", help=t("help.update"))
    p.add_argument("--no-projects", action="store_true", help=t("opt.no_projects"))

    p = sub.add_parser("list", help=t("help.list"))
    p.add_argument("slug", nargs="?", help=t("opt.list_slug"))
    p.add_argument("--prune", action="store_true", help=t("opt.prune"))

    p = sub.add_parser("lang", help=t("help.lang"))
    p.add_argument("valore", nargs="?", choices=("it", "en"), help=t("opt.lang_valore"))
    p.add_argument("--global", dest="globale", action="store_true", help=t("opt.lang_globale"))

    # I comandi del grafo nello stesso elenco: un help solo, nessun passthrough.
    aggiungi_comandi(sub)
    parser.add_argument("-g", "--graph", dest="graph", help=t("opt.graph_attivo"))
    return parser


def progetto_qui(partenza: Path | None = None) -> Path | None:
    """La cartella del progetto Atlas che contiene questa posizione, se c'e'."""
    partenza = (partenza or Path.cwd()).resolve()
    for cartella in (partenza, *partenza.parents):
        if (cartella / ".atlas" / "config.json").is_file():
            return cartella
    return None


def _lingua_scritta(radice: Path) -> str | None:
    """La lingua nel config del progetto, None se il file non si legge.

    Qui un config rotto si ingoia di proposito: la lingua e' una preferenza estetica,
    e farla decidere se il CLI parte o no significa spegnere anche 'uninstall' e
    'list', cioe' i due comandi con cui si esce dal guasto. A dirlo ci pensa dopo il
    comando che quel file lo apre per lavorarci.
    """
    try:
        dati = json.loads((radice / ".atlas" / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return dati.get("language") if isinstance(dati, dict) else None


def _allinea_lingua() -> None:
    """Una lingua sola per i due cataloghi, quello del gestore e quello del motore.

    L'help unico pesca da entrambi: se restassero indipendenti, dentro un progetto
    inglese meta' elenco uscirebbe in italiano.
    """
    from core import strings as strings_motore
    radice = progetto_qui()
    try:
        lingua = (_lingua_scritta(radice) if radice is not None else None) or registry.language_for(None)
    except ErroreAtlas:
        lingua = "it"     # registro illeggibile: lo dira' il comando che lo usa davvero
    set_language(lingua)
    strings_motore.set_language(lingua)


def _inietta_lucchetto(radice: Path | None) -> None:
    """Se il progetto dichiara lock.remote, costruisce il trasporto git-refs e lo
    inietta nell'holder del motore. Feature spenta di default: senza lock.remote il
    motore resta local-only e al boot non parte nessuna rete. Un config illeggibile
    si ingoia, come per la lingua: a dirlo pensa il comando che quel file lo apre."""
    if radice is None:
        return
    try:
        dati = json.loads((radice / ".atlas" / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if not isinstance(dati, dict):
        return
    remote = dati.get("lock", {}).get("remote")
    if not isinstance(remote, str) or not remote:
        return
    from core import remotelock as lucchetto
    from .remotelock import TrasportoRefsGit
    lucchetto.set_trasporto(TrasportoRefsGit(remote))


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    _allinea_lingua()
    _inietta_lucchetto(progetto_qui())

    if not argv or argv[0] in ("-h", "--help", "help"):
        build_parser().print_help()
        return 0
    if argv[0] == "--version":
        print(current_version())
        return 0

    args = build_parser().parse_args(argv)
    try:
        if args.cmd in RESERVED:
            exitcode = COMANDI[args.cmd](args)
        else:
            from core.cli import esegui
            exitcode = esegui(args)

        # Controlla aggiornamenti dopo il comando, ma non per i comandi di gestione
        if args.cmd not in {"update", "install", "uninstall"}:
            _avvisa_aggiornamento()

        return exitcode
    except ErroreAtlas as errore:
        print(f"\n  {errore}\n", file=sys.stderr)
        return 1


def _avvisa_aggiornamento() -> None:
    """Controlla se c'e' un aggiornamento disponibile e avvisa, senza interruzioni."""
    try:
        nuova = self_update.check_for_update()
        if nuova:
            print(t("update.disponibile", nuova=nuova, attuale=current_version()))
    except Exception:
        # Qualsiasi errore nel controllo: silenzio
        pass
