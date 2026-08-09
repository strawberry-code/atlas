"""La CLI di Atlas: contabilita' del lavoro, mai ridisegno della mappa.

I gesti che spostano un nodo lungo il suo ciclo di vita stanno qui. I gesti che
cambiano la forma del grafo stanno negli script di .atlas/scripts/, e passano da
mutate: e' la ragione per cui qui non esiste nessun comando che crea un nodo.
"""
from __future__ import annotations

import argparse
import os
import runpy
import subprocess
import sys
from pathlib import Path

from . import claims, docs, doctor, howto, mutate, render as dash, report, strings
from .config import ENV_IDENTITY, ConfigError, Workspace, workspace
from .model import node_of
from .mutate import editing, validate
from .store import StateError, load, transaction
from .strings import t


def refresh(ref, data: dict, aprila: bool = False) -> None:
    """Ticket mancanti, liste della mappa e dashboard: i tre artefatti derivati."""
    docs.ensure_map(ref, data)
    if creati := docs.write_stubs(ref, data):
        print(t("refresh.ticket_creati", n=creati, dir=ref.tickets_dir))
    if riallineati := docs.rewrite_heads(ref, data):
        print(t("refresh.ticket_riallineati", n=riallineati))
    docs.rewrite_lists(ref, data)
    dash.write(ref, data)
    if aprila:
        apri = {"darwin": "open", "win32": "start"}.get(sys.platform, "xdg-open")
        subprocess.run([apri, str(ref.dashboard_path)], check=False)


def commit(ws: Workspace, ref, node: dict, tipo: str) -> None:
    cfg = ws.config["git"]
    if not cfg["commit_on_close"]:
        return
    radice = ws.project_root
    if not (radice / ".git").exists():
        return
    percorsi = ([str(ref.json_path), str(ref.map_path), str(ref.ticket_path(node["id"]))]
                if cfg["stage"] == "node-paths" else ["-A"])
    subprocess.run(["git", "add", *percorsi], cwd=radice, check=False)
    messaggio = f"{tipo}({node['id']}): {node['title'].lower()}"
    if cfg["stage"] == "node-paths":
        subprocess.run(["git", "commit", "-m", messaggio, "--", *percorsi], cwd=radice, check=False)
    else:
        subprocess.run(["git", "commit", "-m", messaggio], cwd=radice, check=False)
    print(t("commit.fatto", messaggio=messaggio))


def cmd_new(ws: Workspace, args) -> int:
    ref = mutate.create_graph(ws, args.slug, args.title, args.destination)
    ws.pin(args.slug)
    refresh(ref, load(ref.json_path))
    print(t("new.creato", slug=args.slug, dir=ref.dir))
    print(t("new.suggerimento"))
    return 0


def cmd_new_script(ws: Workspace, args) -> int:
    ws.scripts_dir.mkdir(parents=True, exist_ok=True)
    esistenti = sorted(ws.scripts_dir.glob("[0-9][0-9][0-9]-*.py"))
    numero = int(esistenti[-1].name[:3]) + 1 if esistenti else 1
    nome = f"{numero:03d}-{args.nome}.py"
    path = ws.scripts_dir / nome
    path.write_text(ws.template("migration.py.tmpl").format(
        descrizione=args.nome.replace("-", " ").capitalize(), filename=nome), encoding="utf-8")
    print(f"  {path}")
    return 0


def cmd_exec(ws: Workspace, args) -> int:
    ref = ws.graph(args.graph)
    script = Path(args.script).resolve()
    if not script.is_file():
        raise ConfigError(t("exec.script_assente", script=script))
    sys.path.insert(0, str(ws.root))
    modulo = runpy.run_path(str(script))
    if "run" not in modulo:
        raise StateError(t("exec.senza_run", nome=script.name))
    try:
        with editing(ref) as g:
            modulo["run"](g)
    except StateError:
        raise
    except Exception as errore:                       # lo script e' codice altrui
        raise StateError(t("exec.morto", nome=script.name,
                            tipo=type(errore).__name__, errore=errore)) from errore
    data = load(ref.json_path)
    refresh(ref, data)
    print(t("exec.applicato", nome=script.name, slug=ref.slug, n=len(data["nodes"])))
    report.show_status(ref, data)
    return 0


def cmd_validate(ws: Workspace, args) -> int:
    for slug in ([args.graph] if args.graph else ws.slugs()):
        ref = ws.graph(slug)
        validate(load(ref.json_path), ws.config["vocab"])
        print(t("validate.ok", slug=slug))
    return 0


def cmd_doctor(ws: Workspace, args) -> int:
    print()
    print(t("doctor.radice", root=ws.root))
    print(t("doctor.progetto", progetto=ws.config["project"], root=ws.project_root))
    print(t("doctor.versione", versione=(ws.root / "VERSION").read_text().strip()))
    print(t("doctor.grafi", grafi=", ".join(ws.slugs()) or t("doctor.nessuno")))
    skills = ws.project_root / ".claude" / "skills"
    attese = [d.name for d in (ws.root / "skills").iterdir() if d.is_dir()]
    mancanti = [s for s in attese if not (skills / s).exists()]
    stato_skill = t("doctor.skill_ok") if not mancanti else t("doctor.skill_mancanti", elenco=", ".join(mancanti))
    print(t("doctor.skill", stato=stato_skill))
    hook = ws.project_root / ".claude" / "settings.json"
    stato_hook = t("doctor.hook_ok") if hook.is_file() and "atlas" in hook.read_text() else t("doctor.hook_assente")
    print(t("doctor.hook", stato=stato_hook))
    presente = t("si") if (ws.project_root / ".git").exists() else t("no")
    commit_ = t("si") if ws.config["git"]["commit_on_close"] else t("no")
    print(t("doctor.git", presente=presente, commit=commit_))
    doctor.show_doctor(ws)
    return 0


def _identity(p: argparse.ArgumentParser) -> None:
    """Il flag comune ai comandi che prendono o mollano il lucchetto.

    Vive qui e non nel parser radice perche' un flag globale andrebbe scritto prima
    del sottocomando, cioe' nel punto dove nessuno lo cerca.
    """
    p.add_argument("--identity", default=None, help=t("help.identity"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atlas", description=t("parser.description"))
    parser.add_argument("-g", "--graph", help=t("opt.graph"))
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help=t("help.status"))
    sub.add_parser("next", help=t("help.next"))
    sub.add_parser("graphs", help=t("help.graphs"))
    p = sub.add_parser("use", help=t("help.use")); p.add_argument("slug")
    p = sub.add_parser("show", help=t("help.show")); p.add_argument("node")
    p = sub.add_parser("brief", help=t("help.brief")); p.add_argument("node")

    p = sub.add_parser("claim", help=t("help.claim"))
    p.add_argument("node"); p.add_argument("-a", "--assignee"); p.add_argument("--force", action="store_true")
    _identity(p)
    p = sub.add_parser("take", help=t("help.take"))
    p.add_argument("node"); p.add_argument("-a", "--assignee"); p.add_argument("--force", action="store_true")
    _identity(p)
    p = sub.add_parser("release", help=t("help.release")); p.add_argument("node")
    p.add_argument("-r", "--ragione", default=None); _identity(p)
    p = sub.add_parser("close", help=t("help.close"))
    p.add_argument("node"); p.add_argument("-s", "--sintesi", required=True)
    p.add_argument("-t", "--tipo", default=None); p.add_argument("--force", action="store_true")
    p.add_argument("-c", "--costo", default=None)
    p.add_argument("--artefatti", nargs="*", default=None); _identity(p)
    p = sub.add_parser("fog", help=t("help.fog"))
    p.add_argument("riga", nargs="?", default=None)
    p.add_argument("--for", dest="destinatario", default=None)
    p.add_argument("--list", dest="elenca", action="store_true")
    p = sub.add_parser("render", help=t("help.render"))
    p.add_argument("--open", dest="aprila", action="store_true")

    p = sub.add_parser("new", help=t("help.new"))
    p.add_argument("slug"); p.add_argument("-t", "--title", required=True)
    p.add_argument("-d", "--destination", default=t("default.destination"))
    p = sub.add_parser("new-script", help=t("help.new_script"))
    p.add_argument("nome")
    p = sub.add_parser("exec", help=t("help.exec")); p.add_argument("script")
    sub.add_parser("validate", help=t("help.validate"))
    sub.add_parser("doctor", help=t("help.doctor"))
    sub.add_parser("how-to", help=t("help.how_to"))
    return parser


def dispatch(ws: Workspace, args) -> int:
    if args.cmd in ("new", "new-script", "exec", "validate", "doctor", "graphs", "use", "how-to"):
        if args.cmd == "graphs":
            report.show_graphs(ws); return 0
        if args.cmd == "how-to":
            howto.show(ws, build_parser().format_help()); return 0
        if args.cmd == "use":
            ws.graph(args.slug); ws.pin(args.slug); print(t("use.attivo", slug=args.slug)); return 0
        return {"new": cmd_new, "new-script": cmd_new_script, "exec": cmd_exec,
                "validate": cmd_validate, "doctor": cmd_doctor}[args.cmd](ws, args)

    ref = ws.graph(args.graph)
    if args.cmd == "close":
        node, avviso = claims.close(ref, args.node, args.sintesi, args.force, cost=args.costo, artifacts=args.artefatti)
        print(t("close.fatto", id=node["id"]))
        if avviso:
            print(f"  {avviso}")
        data = load(ref.json_path)
        refresh(ref, data)
        commit(ws, ref, node, args.tipo or ws.config["git"]["commit_type"])
        report.show_status(ref, data)
        return 0

    if args.cmd == "take":
        node = claims.claim(ref, args.node, args.assignee, args.force)
        data = load(ref.json_path)
        refresh(ref, data)
        report.show_brief(ref, data, node["id"])
        return 0

    if args.cmd == "claim":
        node = claims.claim(ref, args.node, args.assignee, args.force)
        print(t("claim.fatto", id=node["id"], path=ref.ticket_path(node["id"])))
    elif args.cmd == "release":
        print(t("release.fatto", id=claims.release(ref, args.node, args.ragione)["id"]))
    elif args.cmd == "fog":
        if args.elenca:
            report.show_fog(ref, load(ref.json_path))
            return 0
        if not args.riga:
            raise StateError(t("fog.riga_mancante"))
        riga = t("fog.per", id=args.destinatario, riga=args.riga) if args.destinatario else args.riga
        with transaction(ref.json_path) as data:
            data["fog"].append(riga)
        print(t("fog.fatto"))
    elif args.cmd == "show":
        report.show_node(ref, load(ref.json_path), args.node)
        return 0
    elif args.cmd == "brief":
        report.show_brief(ref, load(ref.json_path), args.node)
        return 0

    data = load(ref.json_path)
    if args.cmd == "status":
        report.show_status(ref, data)  # sola lettura: non tocca gli artefatti
        return 0
    if args.cmd == "next":
        report.show_next(ref, data)  # sola lettura: non tocca gli artefatti
        return 0
    refresh(ref, data, getattr(args, "aprila", False))
    if args.cmd not in ("claim", "fog"):
        report.show_status(ref, data)
    return 0


def main(argv: list[str] | None = None) -> int:
    ws = None
    try:
        ws = workspace()
        strings.set_language(ws.config.get("language", "it"))
    except ConfigError:
        pass  # nessun progetto da qui: build_parser() mostra comunque --help, in italiano di default
    args = build_parser().parse_args(argv)
    if getattr(args, "identity", None):
        os.environ[ENV_IDENTITY] = args.identity
    try:
        return dispatch(ws or workspace(), args)
    except (StateError, ConfigError) as errore:
        print(f"\n  {errore}\n", file=sys.stderr)
        return 1
