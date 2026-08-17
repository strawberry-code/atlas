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
from .model import fog_line, node_of
from .mutate import editing, validate
from .store import StateError, load, read_transaction, transaction
from .strings import t


def refresh(ref, data: dict) -> None:
    """Ticket mancanti, liste della mappa e dashboard: i tre artefatti derivati."""
    docs.ensure_map(ref, data)
    if creati := docs.write_stubs(ref, data):
        print(t("refresh.ticket_creati", n=creati, dir=ref.tickets_dir))
    if riallineati := docs.rewrite_heads(ref, data):
        print(t("refresh.ticket_riallineati", n=riallineati))
    docs.rewrite_lists(ref, data)
    dash.write(ref, data)


def _apri_browser(ref) -> None:
    """Apre la dashboard nel browser. Fuori dal lock perche' lancia un processo esterno."""
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
    # Niente da mettere in sys.path: lo script fa 'from core import mutate' e 'core'
    # e' gia' importato in questo processo, perche' il motore e' il programma stesso.
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
    # Sotto lock come ogni altro percorso che rigenera: due script lanciati insieme,
    # o uno script mentre un altro agente chiude un nodo, facevano atterrare artefatti
    # costruiti su una lettura vecchia sopra quelli appena scritti.
    with read_transaction(ref.json_path) as data:
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
    print(t("doctor.versione", versione=howto.versione_motore()))
    print(t("doctor.grafi", grafi=", ".join(ws.slugs()) or t("doctor.nessuno")))
    skills = ws.project_root / ".claude" / "skills"
    # .atlas/skills sparisce con un'installazione interrotta o una cancellazione a
    # mano, ed e' esattamente quando si lancia doctor: iterdir() su una cartella che
    # non c'e' faceva morire la diagnosi prima di stamparla.
    sorgente = ws.root / "skills"
    attese = [d.name for d in sorgente.iterdir() if d.is_dir()] if sorgente.is_dir() else []
    mancanti = [s for s in attese if not (skills / s).exists()]
    if not sorgente.is_dir():
        stato_skill = t("doctor.skill_sorgente_assente", dir=sorgente)
    elif mancanti:
        stato_skill = t("doctor.skill_mancanti", elenco=", ".join(mancanti))
    else:
        stato_skill = t("doctor.skill_ok")
    print(t("doctor.skill", stato=stato_skill))
    hook = ws.project_root / ".claude" / "settings.json"
    contenuto_hook = hook.read_text(encoding="utf-8") if hook.is_file() else ""
    stato_hook = t("doctor.hook_ok") if "atlas" in contenuto_hook else t("doctor.hook_assente")
    print(t("doctor.hook", stato=stato_hook))
    presente = t("si") if (ws.project_root / ".git").exists() else t("no")
    commit_ = t("si") if ws.config["git"]["commit_on_close"] else t("no")
    print(t("doctor.git", presente=presente, commit=commit_))
    doctor.show_doctor(ws)
    return 0


def cmd_whoami(ws: Workspace, args) -> int:
    """Legge o scrive il nome di chi lavora da questa copia del progetto."""
    if args.dimentica:
        ws.whoami_file.unlink(missing_ok=True)
        print(t("whoami.dimenticato"))
        return 0
    if args.nome:
        nome = mutate.nome_persona(args.nome)
        ws.whoami_file.write_text(f"{nome}\n", encoding="utf-8")
        print(t("whoami.scritto", nome=nome, path=ws.whoami_file))
        return 0
    chi = ws.whoami()
    print(t("whoami.sono", nome=chi) if chi else t("whoami.nessuno"))
    return 0


def cmd_assegna(ws: Workspace, ref, args) -> None:
    """assign e unassign: stessi bersagli, due versi.

    Con --me il primo posizionale non e' piu' un nome ma un nodo: senza questo
    spostamento 'assign --me F02' assegnerebbe zero nodi a una persona di nome F02.
    """
    nome = None
    if args.cmd == "assign":
        if args.me:
            if args.nome:
                args.nodi = [args.nome, *args.nodi]
            nome = ws.whoami()
            if not nome:
                raise StateError(t("assign.senza_whoami"))
        elif not args.nome:
            raise StateError(t("assign.senza_nome"))
        else:
            nome = args.nome
    with mutate.editing(ref) as g:
        cambiati = (mutate.assign(g, nome, args.nodi, args.branch) if nome
                    else mutate.unassign(g, args.nodi, args.branch))
    if not cambiati:
        print(t("assign.gia_cosi", nome=nome) if nome else t("unassign.gia_liberi"))
        return
    elenco = ", ".join(cambiati)
    print(t("assign.fatto", nome=nome, elenco=elenco) if nome
          else t("unassign.fatto", elenco=elenco))


def _identity(p: argparse.ArgumentParser) -> None:
    """Il flag comune ai comandi che prendono o mollano il lucchetto.

    Vive qui e non nel parser radice perche' un flag globale andrebbe scritto prima
    del sottocomando, cioe' nel punto dove nessuno lo cerca.
    """
    p.add_argument("--identity", default=None, help=t("help.identity"))


def _grafo(p: argparse.ArgumentParser) -> None:
    """-g/--graph accettato anche DOPO il sottocomando.

    Sul parser radice il flag esiste da sempre, ma li' va scritto prima del comando,
    cioe' nel punto in cui nessuno lo cerca: 'atlas render -g piano' rispondeva
    'unrecognized arguments: -g piano', che e' il modo peggiore di sbagliare, perche'
    il flag e' quello giusto e l'errore non dice dov'e' il problema. SUPPRESS e'
    obbligatorio: con un default normale il sottocomando riscriverebbe nel namespace
    il proprio None, cancellando il valore gia' letto dal parser radice.
    """
    p.add_argument("-g", "--graph", default=argparse.SUPPRESS, help=t("opt.graph"))


COMANDI = ("status", "next", "graphs", "use", "show", "brief", "claim", "take", "release",
           "close", "fog", "assign", "unassign", "whoami", "render", "new", "new-script",
           "exec", "validate", "doctor", "how-to")


class Parser(argparse.ArgumentParser):
    """Il parser radice, che su un comando sconosciuto guarda se era uno slug.

    'atlas <slug> render' e' il primo tentativo di chi conosce altri strumenti, e
    l'elenco dei comandi validi che argparse stampa non dice da nessuna parte come
    si sceglie un grafo: due persone davanti allo stesso schermo non ne sono uscite.
    Il suggerimento si aggiunge solo se quel token e' davvero un grafo di questo
    progetto, cosi' chi ha semplicemente sbagliato a digitare non legge un consiglio
    che non c'entra.
    """

    def parse_args(self, args=None, namespace=None):
        self._token = list(sys.argv[1:] if args is None else args)
        return super().parse_args(args, namespace)

    def error(self, message: str) -> None:
        primo = next((a for a in getattr(self, "_token", []) if not a.startswith("-")), None)
        if primo and primo in _slug_noti():
            message = f"{message}\n{t('parser.slug_al_posto_del_comando', slug=primo)}"
        super().error(message)


def _slug_noti() -> list[str]:
    """I grafi del progetto sotto la cwd, o niente se qui non c'e' un progetto."""
    try:
        return workspace().slugs()
    except ConfigError:
        return []


def build_parser() -> argparse.ArgumentParser:
    parser = Parser(prog="atlas", description=t("parser.description"))
    aggiungi_comandi(parser.add_subparsers(dest="cmd", required=True))
    parser.add_argument("-g", "--graph", help=t("opt.graph"))
    return parser


def aggiungi_comandi(sub) -> None:
    """Appende i comandi del grafo a un gruppo di sottocomandi gia' esistente.

    Separato da build_parser() perche' il CLI globale ne ha uno suo, con install e
    compagnia, e i due elenchi devono comparire in un help solo: un utente non deve
    sapere che dentro c'e' un motore e attorno c'e' un gestore.
    """
    _grafo(sub.add_parser("status", help=t("help.status")))
    _grafo(sub.add_parser("next", help=t("help.next")))
    sub.add_parser("graphs", help=t("help.graphs"))
    p = sub.add_parser("use", help=t("help.use")); p.add_argument("slug")
    p = sub.add_parser("show", help=t("help.show")); p.add_argument("node"); _grafo(p)
    p = sub.add_parser("brief", help=t("help.brief")); p.add_argument("node"); _grafo(p)

    p = sub.add_parser("claim", help=t("help.claim"))
    p.add_argument("node"); p.add_argument("-a", "--assignee"); p.add_argument("--force", action="store_true")
    _identity(p); _grafo(p)
    p = sub.add_parser("take", help=t("help.take"))
    p.add_argument("node"); p.add_argument("-a", "--assignee"); p.add_argument("--force", action="store_true")
    _identity(p); _grafo(p)
    p = sub.add_parser("release", help=t("help.release")); p.add_argument("node")
    p.add_argument("-r", "--ragione", default=None); _identity(p); _grafo(p)
    p = sub.add_parser("close", help=t("help.close"))
    p.add_argument("node"); p.add_argument("-s", "--sintesi", required=True)
    p.add_argument("-t", "--tipo", default=None); p.add_argument("--force", action="store_true")
    p.add_argument("-c", "--costo", default=None)
    p.add_argument("--artefatti", nargs="*", default=None); _identity(p); _grafo(p)
    p = sub.add_parser("amend", help=t("help.amend"))
    p.add_argument("node"); p.add_argument("--artefatti", nargs="*", default=None)
    p.add_argument("-c", "--costo", default=None); p.add_argument("-s", "--sintesi", default=None)
    _identity(p); _grafo(p)
    p = sub.add_parser("fog", help=t("help.fog"))
    p.add_argument("riga", nargs="?", default=None)
    p.add_argument("--for", dest="destinatario", default=None)
    p.add_argument("--list", dest="elenca", action="store_true"); _grafo(p)
    p = sub.add_parser("assign", help=t("help.assign"))
    p.add_argument("nome", nargs="?", default=None, help=t("help.assign_nome"))
    p.add_argument("nodi", nargs="*", default=[], help=t("help.assign_nodi"))
    p.add_argument("-b", "--branch", default=None, help=t("help.assign_branch"))
    p.add_argument("--me", action="store_true", help=t("help.assign_me")); _grafo(p)
    p = sub.add_parser("unassign", help=t("help.unassign"))
    p.add_argument("nodi", nargs="*", default=[], help=t("help.assign_nodi"))
    p.add_argument("-b", "--branch", default=None, help=t("help.assign_branch")); _grafo(p)
    p = sub.add_parser("whoami", help=t("help.whoami"))
    p.add_argument("nome", nargs="?", default=None, help=t("help.whoami_nome"))
    p.add_argument("--clear", dest="dimentica", action="store_true", help=t("help.whoami_clear"))
    p = sub.add_parser("render", help=t("help.render"))
    p.add_argument("--open", dest="aprila", action="store_true")
    p.add_argument("--all", dest="tutti", action="store_true", help=t("help.render_all")); _grafo(p)

    p = sub.add_parser("new", help=t("help.new"))
    p.add_argument("slug"); p.add_argument("-t", "--title", required=True)
    p.add_argument("-d", "--destination", default=t("default.destination"))
    p = sub.add_parser("new-script", help=t("help.new_script"))
    p.add_argument("nome")
    p = sub.add_parser("exec", help=t("help.exec")); p.add_argument("script")
    sub.add_parser("validate", help=t("help.validate"))
    sub.add_parser("doctor", help=t("help.doctor"))
    sub.add_parser("how-to", help=t("help.how_to"))


def dispatch(ws: Workspace, args) -> int:
    if args.cmd in ("new", "new-script", "exec", "validate", "doctor", "graphs", "use",
                    "how-to", "whoami"):
        if args.cmd == "graphs":
            report.show_graphs(ws); return 0
        if args.cmd == "whoami":
            return cmd_whoami(ws, args)
        if args.cmd == "how-to":
            howto.show(ws, build_parser().format_help()); return 0
        if args.cmd == "use":
            ws.graph(args.slug); ws.pin(args.slug); print(t("use.attivo", slug=args.slug)); return 0
        return {"new": cmd_new, "new-script": cmd_new_script, "exec": cmd_exec,
                "validate": cmd_validate, "doctor": cmd_doctor}[args.cmd](ws, args)

    if args.cmd == "render" and getattr(args, "tutti", False):
        # Il giro che faceva l'hook di fine sessione quando era uno script nel progetto.
        for slug in ws.slugs():
            ref = ws.graph(slug)
            with read_transaction(ref.json_path) as data:
                refresh(ref, data)
        print(t("render.tutti", n=len(ws.slugs())))
        return 0

    ref = ws.graph(args.graph)
    if args.cmd == "close":
        node, avviso = claims.close(ref, args.node, args.sintesi, args.force, cost=args.costo, artifacts=args.artefatti)
        print(t("close.fatto", id=node["id"]))
        if avviso:
            print(f"  {avviso}")
        # Solo quando li ha dedotti il motore: chi passa --artefatti sa gia' cosa ha
        # scritto, chi non lo passa scopre l'attribuzione qui invece che rileggendo
        # il grafo giorni dopo.
        if args.artefatti is None and node.get("artifacts"):
            print(t("close.artefatti_dedotti", n=len(node["artifacts"]),
                    elenco=", ".join(node["artifacts"])))
        with read_transaction(ref.json_path) as data:
            refresh(ref, data)
        report.show_status(ref, data)      # stampare non vuole il lock: data e' gia' in memoria
        commit(ws, ref, node, args.tipo or ws.config["git"]["commit_type"])
        return 0

    if args.cmd == "amend":
        with mutate.editing(ref) as g:
            node = mutate.amend(g, args.node, artifacts=args.artefatti,
                                cost=args.costo, summary=args.sintesi)
            corretti = node["amendments"][-1]["fields"]
        with read_transaction(ref.json_path) as data:
            refresh(ref, data)
        print(t("amend.fatto", id=args.node, campi=", ".join(corretti)))
        return 0

    if args.cmd == "take":
        node = claims.claim(ref, args.node, args.assignee, args.force)
        with read_transaction(ref.json_path) as data:
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
        riga, ripetuto = args.riga, False
        if args.destinatario:
            riga, ripetuto = fog_line(args.destinatario, args.riga)
        with transaction(ref.json_path) as data:
            data["fog"].append(riga)
        print(t("fog.fatto"))
        if ripetuto:
            print(t("fog.prefisso_ripetuto", id=args.destinatario))
    elif args.cmd in ("assign", "unassign"):
        cmd_assegna(ws, ref, args)
    elif args.cmd == "show":
        report.show_node(ref, load(ref.json_path), args.node)
        return 0
    elif args.cmd == "brief":
        report.show_brief(ref, load(ref.json_path), args.node)
        return 0

    # Comandi di sola lettura: non mutano, non rigenerano, escono prima
    if args.cmd == "status":
        report.show_status(ref, load(ref.json_path))  # sola lettura: non tocca gli artefatti
        return 0
    if args.cmd == "next":
        report.show_next(ref, load(ref.json_path))  # sola lettura: non tocca gli artefatti
        return 0

    # Comandi che mutano (claim, release, fog, render): rigenerano sotto lock
    aprila = getattr(args, "aprila", False)
    with read_transaction(ref.json_path) as data:
        refresh(ref, data)
    if aprila:
        _apri_browser(ref)
    if args.cmd not in ("claim", "fog", "assign", "unassign"):
        report.show_status(ref, data)
    return 0


def esegui(args) -> int:
    """Un comando del grafo gia' parsato: trova il progetto e lo manda in dispatch.

    E' il punto d'ingresso del CLI globale, che il parsing lo ha fatto per conto suo
    su un elenco di comandi unico.
    """
    ws = None
    try:
        ws = workspace()
        strings.set_language(ws.config.get("language", "it"))
    except ConfigError:
        pass  # senza progetto qui sotto, dispatch rilancia l'errore con il messaggio giusto
    if getattr(args, "identity", None):
        os.environ[ENV_IDENTITY] = args.identity
    try:
        return dispatch(ws or workspace(), args)
    except (StateError, ConfigError) as errore:
        print(f"\n  {errore}\n", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    """Il motore invocato da solo, senza il CLI globale attorno: serve ai test."""
    try:
        strings.set_language(workspace().config.get("language", "it"))
    except ConfigError:
        pass  # nessun progetto da qui: --help si vede lo stesso, in italiano di default
    return esegui(build_parser().parse_args(argv))
