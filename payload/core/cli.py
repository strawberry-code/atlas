"""La CLI di Atlas: contabilita' del lavoro, mai ridisegno della mappa.

I gesti che spostano un nodo lungo il suo ciclo di vita stanno qui. I gesti che
cambiano la forma del grafo stanno negli script di .atlas/scripts/, e passano da
mutate: e' la ragione per cui qui non esiste nessun comando che crea un nodo.
"""
from __future__ import annotations

import argparse
import runpy
import subprocess
import sys
from pathlib import Path

from . import claims, docs, mutate, render as dash, report
from .config import ConfigError, Workspace, workspace
from .model import node_of
from .mutate import editing, validate
from .store import StateError, load, transaction


def refresh(ref, data: dict, aprila: bool = False) -> None:
    """Ticket mancanti, liste della mappa e dashboard: i tre artefatti derivati."""
    docs.ensure_map(ref, data)
    if creati := docs.write_stubs(ref, data):
        print(f"  {creati} ticket creati in {ref.tickets_dir}")
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
    subprocess.run(["git", "commit", "-m", messaggio], cwd=radice, check=False)
    print(f"  commit: {messaggio}")


def cmd_new(ws: Workspace, args) -> int:
    ref = mutate.create_graph(ws, args.slug, args.title, args.destination)
    ws.pin(args.slug)
    refresh(ref, load(ref.json_path))
    print(f"  grafo '{args.slug}' creato in {ref.dir} e reso attivo.")
    print("  Ora popolalo con uno script: 'atlas new-script primo-disegno'.")
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
        raise ConfigError(f"{script} non esiste")
    sys.path.insert(0, str(ws.root))
    modulo = runpy.run_path(str(script))
    if "run" not in modulo:
        raise StateError(f"{script.name} non definisce run(g)")
    try:
        with editing(ref) as g:
            modulo["run"](g)
    except StateError:
        raise
    except Exception as errore:                       # lo script e' codice altrui
        raise StateError(f"{script.name} è morto durante l'esecuzione: "
                         f"{type(errore).__name__}: {errore}\n"
                         f"  Il grafo non è stato toccato.") from errore
    data = load(ref.json_path)
    refresh(ref, data)
    print(f"  {script.name} applicato a '{ref.slug}' · {len(data['nodes'])} nodi")
    report.show_status(ref, data)
    return 0


def cmd_validate(ws: Workspace, args) -> int:
    for slug in ([args.graph] if args.graph else ws.slugs()):
        ref = ws.graph(slug)
        validate(load(ref.json_path), ws.config["vocab"])
        print(f"  {slug}: forma valida")
    return 0


def cmd_doctor(ws: Workspace, args) -> int:
    print(f"\n  radice   {ws.root}")
    print(f"  progetto {ws.config['project']} · {ws.project_root}")
    print(f"  versione {(ws.root / 'VERSION').read_text().strip()}")
    print(f"  grafi    {', '.join(ws.slugs()) or 'nessuno'}")
    skills = ws.project_root / ".claude" / "skills"
    attese = [d.name for d in (ws.root / "skills").iterdir() if d.is_dir()]
    mancanti = [s for s in attese if not (skills / s).exists()]
    print(f"  skill    {'tutte collegate' if not mancanti else 'mancano ' + ', '.join(mancanti)}")
    hook = ws.project_root / ".claude" / "settings.json"
    print(f"  hook     {'registrato' if hook.is_file() and 'atlas' in hook.read_text() else 'assente'}")
    print(f"  git      {'sì' if (ws.project_root / '.git').exists() else 'no'} · "
          f"commit alla chiusura: {'sì' if ws.config['git']['commit_on_close'] else 'no'}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atlas", description="Harness di task a grafo.")
    parser.add_argument("-g", "--graph", help="slug del grafo, se non è quello attivo")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="frontiera, lucchetti, avanzamento")
    sub.add_parser("graphs", help="i grafi di questo progetto")
    p = sub.add_parser("use", help="rende attivo un grafo"); p.add_argument("slug")
    p = sub.add_parser("show", help="scheda di un nodo"); p.add_argument("node")

    p = sub.add_parser("claim", help="rivendica un nodo per questa sessione")
    p.add_argument("node"); p.add_argument("-a", "--assignee"); p.add_argument("--force", action="store_true")
    p = sub.add_parser("release", help="restituisce un nodo alla frontiera"); p.add_argument("node")
    p = sub.add_parser("close", help="chiude un nodo con la sua sintesi")
    p.add_argument("node"); p.add_argument("-s", "--sintesi", required=True)
    p.add_argument("-t", "--tipo", default=None); p.add_argument("--force", action="store_true")
    p = sub.add_parser("fog", help="appunta ciò che è emerso e non ha ancora un nodo")
    p.add_argument("riga")
    p = sub.add_parser("render", help="rigenera ticket, mappa e dashboard")
    p.add_argument("--open", dest="aprila", action="store_true")

    p = sub.add_parser("new", help="crea un grafo nuovo")
    p.add_argument("slug"); p.add_argument("-t", "--title", required=True)
    p.add_argument("-d", "--destination", default="Da scrivere: dove si arriva quando questo grafo è finito.")
    p = sub.add_parser("new-script", help="crea uno script di mutazione numerato")
    p.add_argument("nome")
    p = sub.add_parser("exec", help="esegue uno script di mutazione"); p.add_argument("script")
    sub.add_parser("validate", help="verifica la forma dei grafi")
    sub.add_parser("doctor", help="stato dell'installazione")
    return parser


def dispatch(ws: Workspace, args) -> int:
    if args.cmd in ("new", "new-script", "exec", "validate", "doctor", "graphs", "use"):
        if args.cmd == "graphs":
            report.show_graphs(ws); return 0
        if args.cmd == "use":
            ws.graph(args.slug); ws.pin(args.slug); print(f"  grafo attivo: {args.slug}"); return 0
        return {"new": cmd_new, "new-script": cmd_new_script, "exec": cmd_exec,
                "validate": cmd_validate, "doctor": cmd_doctor}[args.cmd](ws, args)

    ref = ws.graph(args.graph)
    if args.cmd == "close":
        node = claims.close(ref, args.node, args.sintesi, args.force)
        print(f"  {node['id']} chiuso · riga aggiunta in map.md")
        data = load(ref.json_path)
        refresh(ref, data)
        commit(ws, ref, node, args.tipo or ws.config["git"]["commit_type"])
        report.show_status(ref, data)
        return 0

    if args.cmd == "claim":
        node = claims.claim(ref, args.node, args.assignee, args.force)
        print(f"  {node['id']} rivendicato · ticket in {ref.ticket_path(node['id'])}")
    elif args.cmd == "release":
        print(f"  {claims.release(ref, args.node)['id']} tornato alla frontiera")
    elif args.cmd == "fog":
        with transaction(ref.json_path) as data:
            data["fog"].append(args.riga)
        print("  appuntato nella nebbia")
    elif args.cmd == "show":
        report.show_node(ref, load(ref.json_path), args.node)
        return 0

    data = load(ref.json_path)
    if args.cmd == "status":
        report.show_status(ref, data)  # sola lettura: non tocca gli artefatti
        return 0
    refresh(ref, data, getattr(args, "aprila", False))
    if args.cmd not in ("claim", "fog"):
        report.show_status(ref, data)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return dispatch(workspace(), args)
    except (StateError, ConfigError) as errore:
        print(f"\n  {errore}\n", file=sys.stderr)
        return 1
