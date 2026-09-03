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

from . import adapters, autopilot, claims, docs, doctor, drift, gitscan, howto, merge, mutate, peer_notify, providers, render as dash, report, scripts, serve, strings, topology
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
    ws.pin(ref.slug)
    refresh(ref, load(ref.json_path))
    print(t("new.creato", slug=ref.slug, dir=ref.dir))
    print(t("new.suggerimento"))
    return 0


def cmd_new_script(ws: Workspace, args) -> int:
    ws.scripts_dir.mkdir(parents=True, exist_ok=True)
    numero = scripts.prossimo(ws.scripts_dir)
    nome = f"{numero:03d}-{args.nome}.py"
    path = ws.scripts_dir / nome
    path.write_text(ws.template("migration.py.tmpl").format(
        descrizione=args.nome.replace("-", " ").capitalize(), filename=nome), encoding="utf-8")
    print(f"  {path}")
    return 0


def cmd_exec(ws: Workspace, args) -> int:
    ref = ws.graph(args.graph)
    for nome in args.scripts:
        script = Path(nome).resolve()
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
        except Exception as errore:                   # lo script e' codice altrui
            raise StateError(t("exec.morto", nome=script.name,
                                tipo=type(errore).__name__, errore=errore)) from errore
        print(t("exec.applicato", nome=script.name, slug=ref.slug, n=len(g.data["nodes"])))
    # Gli artefatti derivati si rigenerano una volta sola, alla fine: sono lo specchio
    # dello stato finale, e rifarli fra uno script e l'altro mostrerebbe stati di
    # passaggio che non interessano a nessuno. Sotto lock come ogni altro percorso che
    # rigenera: due script lanciati insieme, o uno script mentre un altro agente chiude
    # un nodo, facevano atterrare artefatti costruiti su una lettura vecchia sopra
    # quelli appena scritti.
    with read_transaction(ref.json_path) as data:
        refresh(ref, data)
    report.show_status(ref, data)
    return 0


def cmd_renumber(ws: Workspace, args) -> int:
    bersagli = None
    if args.file:
        bersagli = [_nei_scripts(ws.scripts_dir, nome) for nome in args.file]
    da_fare = scripts.rinomine(ws.scripts_dir, bersagli)
    if not da_fare:
        print(t("renumber.niente"))
        return 0
    if args.dry_run:
        for da, a in da_fare:
            print(t("renumber.riga", da=da.name, a=a.name))
        return 0
    _rinomina(ws, da_fare)
    for da, a in da_fare:
        print(t("renumber.riga", da=da.name, a=a.name))
    print(t("renumber.fatto", n=len(da_fare)))
    return 0


def _nei_scripts(scripts_dir: Path, nome: str) -> Path:
    """Un argomento del renumber: un path, o un solo nome da cercare in .atlas/scripts/."""
    candidato = Path(nome)
    if not candidato.is_absolute() and candidato.parent == Path("."):
        return scripts_dir / candidato
    return candidato


def _rinomina(ws: Workspace, da_fare: list[tuple[Path, Path]]) -> None:
    """Applica le rinomine in due fasi, per non perdere un file per strada.

    Rinominare un file sul nome di un altro che deve ancora muoversi lo
    sovrascriverebbe. Passare tutti da un nome temporaneo e solo dopo posarli sul
    nome definitivo evita di dover distinguere i casi: due script che si scambiano
    il numero funzionano come tutti gli altri.
    """
    ponte = [(da, _nome_temporaneo(da), a) for da, a in da_fare]
    for da, temp, _ in ponte:
        _movi(ws, da, temp)
    for _, temp, a in ponte:
        _movi(ws, temp, a)


def _artefatti_cli(valori: list[str | None] | None) -> list[str] | None:
    """Converte la grammatica CLI di ``--artefatti`` nella lista del motore.

    Ogni flag raccoglie al massimo un path, quindi il flag puo' essere ripetuto
    senza perdere i valori precedenti. L'unica occorrenza senza path e' la
    dichiarazione esplicita della lista vuota.
    """
    if valori is None:
        return None
    if any(valore is None for valore in valori):
        if len(valori) == 1:
            return []
        raise StateError("--artefatti senza path non puo' essere combinato con altri path")
    percorsi = [valore for valore in valori if valore is not None]
    ambigui = [percorso for percorso in percorsi
               if any(c.isspace() for c in percorso) or "," in percorso]
    if ambigui:
        raise StateError(t("close.artifacts_ambiguous", elenco=", ".join(ambigui)))
    return percorsi


def _movi(ws: Workspace, da: Path, a: Path) -> None:
    """Un rename: git mv se il file e' tracciato, rename normale altrimenti."""
    if not gitscan.move(ws.project_root, da, a):
        da.rename(a)


def _nome_temporaneo(a: Path) -> Path:
    """Un nome libero accanto a 'a', che la numerazione non vede (inizia col punto)."""
    n = 0
    while True:
        corpo = f".{a.stem}.atlas-tmp{n}" if n else f".{a.stem}.atlas-tmp"
        candidato = a.with_name(f"{corpo}{a.suffix}")
        if not candidato.exists():
            return candidato
        n += 1


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
    print(t("attrito.issue"))
    return 0


def cmd_conflicts(ws: Workspace, ref, args) -> int:
    """I conflitti di merge irrisolti: li mostra, o li dichiara risolti.

    'atlas conflicts' stampa il campo conflicts lasciato dal merge driver (A02):
    git ha gia' dichiarato il conflitto, e qui si vede su quali nodi e campi.
    'atlas conflicts --resolve' toglie il campo passando da mutate: chi lo lancia
    dichiara di aver corretto graph.json a mano, non chiede al motore di decidere
    al suo posto.
    """
    data = load(ref.json_path)
    conflitti = [s for s in data.get("conflicts") or [] if isinstance(s, dict)]
    if not conflitti:
        print(t("conflicts.nessuno"))
        return 0
    if args.resolve:
        with mutate.editing(ref) as g:
            mutate.conflicts_clear(g)
        for s in conflitti:
            print(t("conflicts.risolta_riga", nodo=s.get("node") or "-",
                    campo=s.get("field") or "-", tipo=s.get("type") or "-"))
        print(t("conflicts.risolti"))
        with read_transaction(ref.json_path) as data:
            refresh(ref, data)
        return 0
    print(t("conflicts.intestazione", slug=ref.slug))
    for s in conflitti:
        print(t("conflicts.riga", nodo=s.get("node") or "-",
                campo=s.get("field") or "-", tipo=s.get("type") or "-"))
    print(t("conflicts.rimedio"))
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
    modo = "set"
    if args.cmd == "assign":
        modo = "add" if args.add else ("remove" if args.remove else "set")
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
        cambiati = (mutate.assign(g, nome, args.nodi, args.branch, modo) if nome
                    else mutate.unassign(g, args.nodi, args.branch))
    # Il messaggio nomina le persone come il grafo le ha scritte, non come sono state
    # digitate: chi legge 'cristiano,pedro' non saprebbe se il comando ha capito uno o due.
    if nome:
        nome = ", ".join(mutate.persone(nome))
    if not cambiati:
        if nome and modo == "remove":
            print(t("assign.gia_fuori", nome=nome))
        else:
            print(t("assign.gia_cosi", nome=nome) if nome else t("unassign.gia_liberi"))
        return
    elenco = ", ".join(cambiati)
    if nome and modo == "remove":
        print(t("assign.tolti", nome=nome, elenco=elenco))
    else:
        print(t("assign.fatto", nome=nome, elenco=elenco) if nome
              else t("unassign.fatto", elenco=elenco))


def default_adapter_registry() -> adapters.AdapterRegistry:
    """Gli unici provider presenti di default in un run locale di Autopilot."""
    return adapters.AdapterRegistry((providers.codex_adapter(), providers.claude_adapter()))


def cmd_run(ref, args) -> int:
    """Avvia il ciclo Autopilot con i provider locali di default."""
    run = autopilot.start(ref, args.parallelism)
    modalita = t("autopilot.serial") if run.serial else t("autopilot.limited")
    print(t("autopilot.configured", parallelism=run.parallelism, mode=modalita))
    run.execute(autopilot.launcher_from_registry(default_adapter_registry()))
    return 0


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


# I comandi su cui scatta il rinnovo-su-lettura (L06): quelli che caricano il grafo
# mentre la sessione lavora. Ci sono i comandi del ciclo di vita (claim, close, ...)
# e i comandi di lettura con cui il holder guarda il lavoro (status, brief, ...).
# Restano fuori quelli che non sono 'la sessione che lavora': setup e manutenzione
# (new, exec, doctor, how-to, ...), serve (osserva ma non lavora), merge-graph
# (driver git) e conflicts (lettura diagnostica del merge).
_RINNOVA_BATTITO = frozenset((
    "status", "next", "show", "brief",
    "claim", "take", "release", "give-up", "ask-human", "close", "amend", "progress",
    "ask", "asks", "answer", "fog", "assign", "unassign", "render",
))

COMANDI = ("status", "next", "graphs", "use", "show", "brief", "claim", "take", "release",
           "give-up", "ask-human", "close", "ask", "asks", "answer", "drift", "fog", "assign", "unassign", "whoami", "render", "serve", "run", "run-status", "run-log", "merge-graph",
           "conflicts", "new", "new-script", "exec", "renumber", "validate", "doctor", "how-to")


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
        if "unrecognized arguments" in message and "--artefatti" in getattr(self, "_token", []):
            message += f"\n{t('close.artifacts_cli_usage')}"
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
    p = sub.add_parser("give-up", help=t("help.give_up"))
    p.add_argument("node")
    p.add_argument("--motivo", required=True, choices=list(claims.MOTIVI_RESA),
                   help=t("help.give_up_motivo"))
    p.add_argument("-d", "--dettaglio", required=True, help=t("help.give_up_dettaglio"))
    _identity(p); _grafo(p)
    p = sub.add_parser("ask-human", help=t("help.ask_human"))
    p.add_argument("node")
    p.add_argument("-q", "--domanda", required=True, help=t("help.ask_human_domanda"))
    _identity(p); _grafo(p)
    p = sub.add_parser("close", help=t("help.close"))
    p.add_argument("node"); p.add_argument("-s", "--sintesi", required=True)
    p.add_argument("-t", "--tipo", default=None); p.add_argument("--force", action="store_true")
    p.add_argument("-c", "--costo", default=None)
    p.add_argument("--artefatti", action="append", nargs="?", default=None); _identity(p); _grafo(p)
    p = sub.add_parser("amend", help=t("help.amend"))
    p.add_argument("node"); p.add_argument("--artefatti", action="append", nargs="?", default=None)
    p.add_argument("-c", "--costo", default=None); p.add_argument("-s", "--sintesi", default=None)
    _identity(p); _grafo(p)
    p = sub.add_parser("progress", help=t("help.progress"))
    p.add_argument("node")
    p.add_argument("step", choices=list(claims.PASSI), help=t("help.progress_step"))
    p.add_argument("nota", nargs="?", default=None, help=t("help.progress_nota"))
    _grafo(p)
    p = sub.add_parser("ask", help=t("help.ask")); p.add_argument("node")
    p.add_argument("-q", "--question", required=True); p.add_argument("-a", "--assumption", required=True)
    _identity(p); _grafo(p)
    _grafo(sub.add_parser("asks", help=t("help.asks")))
    p = sub.add_parser("answer", help=t("help.answer")); p.add_argument("question")
    p.add_argument("-r", "--response", required=True); _identity(p); _grafo(p)
    _grafo(sub.add_parser("drift", help=t("help.drift")))
    p = sub.add_parser("fog", help=t("help.fog"))
    p.add_argument("riga", nargs="?", default=None)
    p.add_argument("--for", dest="destinatario", default=None)
    p.add_argument("--list", dest="elenca", action="store_true"); _grafo(p)
    p = sub.add_parser("assign", help=t("help.assign"))
    p.add_argument("nome", nargs="?", default=None, help=t("help.assign_nome"))
    p.add_argument("nodi", nargs="*", default=[], help=t("help.assign_nodi"))
    p.add_argument("-b", "--branch", default=None, help=t("help.assign_branch"))
    modo = p.add_mutually_exclusive_group()
    modo.add_argument("--add", action="store_true", help=t("help.assign_add"))
    modo.add_argument("--remove", dest="remove", action="store_true", help=t("help.assign_remove"))
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

    p = sub.add_parser("serve", help=t("help.serve"))
    p.add_argument("--port", type=int, default=0, help=t("help.serve_port"))
    p.add_argument("--no-open", dest="apri", action="store_false", help=t("help.serve_no_open")); _grafo(p)

    _grafo(sub.add_parser("run-status", help=t("help.run_status")))
    p = sub.add_parser("run-log", help=t("help.run_log")); p.add_argument("--tail", type=int, default=None)
    _grafo(p)
    p = sub.add_parser("run", help=t("help.run"))
    p.add_argument("--parallelism", required=True, type=autopilot.parse_parallelism,
                   help=t("help.run_parallelism")); _grafo(p)

    p = sub.add_parser("merge-graph", help=t("help.merge_graph"))
    p.add_argument("base", help=t("help.merge_base"))
    p.add_argument("ours", help=t("help.merge_ours"))
    p.add_argument("theirs", help=t("help.merge_theirs"))

    p = sub.add_parser("conflicts", help=t("help.conflicts"))
    p.add_argument("--resolve", action="store_true", help=t("help.conflicts_resolve"))
    _grafo(p)

    p = sub.add_parser("new", help=t("help.new"))
    p.add_argument("slug", help=t("help.new_slug")); p.add_argument("-t", "--title", required=True)
    p.add_argument("-d", "--destination", default=t("default.destination"))
    p = sub.add_parser("new-script", help=t("help.new_script"))
    p.add_argument("nome")
    p = sub.add_parser("exec", help=t("help.exec")); p.add_argument("scripts", nargs="+")
    p = sub.add_parser("renumber", help=t("help.renumber"))
    p.add_argument("file", nargs="*", default=None, help=t("help.renumber_file"))
    p.add_argument("--dry-run", action="store_true", help=t("help.renumber_dry"))
    sub.add_parser("validate", help=t("help.validate"))
    sub.add_parser("doctor", help=t("help.doctor"))
    sub.add_parser("how-to", help=t("help.how_to"))


def dispatch(ws: Workspace, args) -> int:
    if args.cmd in ("new", "new-script", "exec", "renumber", "validate", "doctor", "graphs",
                    "use", "how-to", "whoami"):
        if args.cmd == "graphs":
            report.show_graphs(ws); return 0
        if args.cmd == "whoami":
            return cmd_whoami(ws, args)
        if args.cmd == "how-to":
            howto.show(ws, build_parser().format_help()); return 0
        if args.cmd == "use":
            ws.graph(args.slug); ws.pin(args.slug); print(t("use.attivo", slug=args.slug)); return 0
        return {"new": cmd_new, "new-script": cmd_new_script, "exec": cmd_exec,
                "renumber": cmd_renumber, "validate": cmd_validate,
                "doctor": cmd_doctor}[args.cmd](ws, args)

    if args.cmd == "merge-graph":
        # Il driver per git: opera sui tre path, non ha bisogno del workspace.
        return merge.merge_files(args.base, args.ours, args.theirs)

    if args.cmd == "render" and getattr(args, "tutti", False):
        # Il giro che faceva l'hook di fine sessione quando era uno script nel progetto.
        for slug in ws.slugs():
            ref = ws.graph(slug)
            with read_transaction(ref.json_path) as data:
                refresh(ref, data)
        print(t("render.tutti", n=len(ws.slugs())))
        return 0

    ref = ws.graph(args.graph)
    if args.cmd in _RINNOVA_BATTITO:
        # L06: il battito di chi tiene. Un comando che carica il grafo mentre la
        # sessione lavora e' il segnale di vita: il lease dei claim nostri si
        # rinnova se e' vicino alla scadenza (meta' del TTL), cosi' un comando ogni
        # TTL tiene la lock e una raffica non produce churn. Scrive solo se serve.
        claims.rinnova_se_necessario(ref)
    if args.cmd == "conflicts":
        return cmd_conflicts(ws, ref, args)
    if args.cmd == "serve":
        return serve.cmd_serve(ref, args)
    if args.cmd == "run":
        return cmd_run(ref, args)
    if args.cmd == "run-status":
        report.show_run_status(ref)
        return 0
    if args.cmd == "run-log":
        if args.tail is not None and args.tail < 0:
            raise StateError("--tail must be non-negative")
        report.show_run_log(ref, args.tail)
        return 0

    if args.cmd == "close":
        artefatti = _artefatti_cli(args.artefatti)
        node, avviso = claims.close(ref, args.node, args.sintesi, args.force, cost=args.costo, artifacts=artefatti)
        print(t("close.fatto", id=node["id"]))
        if avviso:
            print(f"  {avviso}")
        # Solo quando li ha dedotti il motore: chi passa --artefatti sa gia' cosa ha
        # scritto, chi non lo passa scopre l'attribuzione qui invece che rileggendo
        # il grafo giorni dopo.
        if artefatti is None and node.get("artifacts"):
            print(t("close.artefatti_dedotti", n=len(node["artifacts"]),
                    elenco=", ".join(node["artifacts"])))
        with read_transaction(ref.json_path) as data:
            refresh(ref, data)
        report.show_status(ref, data)      # stampare non vuole il lock: data e' gia' in memoria
        commit(ws, ref, node, args.tipo or ws.config["git"]["commit_type"])
        peer_notify.avvisa(ws)   # E01: best-effort, muto se il relay non e' configurato
        print(t("attrito.issue"))
        return 0

    if args.cmd == "progress":
        # H01/4: costa poco e non fa mai fallire il lavoro. Niente refresh degli
        # artefatti derivati (e' il costo vero di ogni altro comando), e qualunque
        # guasto del segnale stesso (lock conteso, nodo non piu' nostro, grafo
        # illeggibile) si stampa e si assorbe: chi chiama non deve trattarlo come un
        # fallimento del proprio lavoro sul nodo.
        try:
            node = claims.progress(ref, args.node, args.step, args.nota)
        except Exception as errore:
            print(t("progress.fallito", errore=errore))
            return 0
        riga = t("progress.fatto", id=node["id"], step=node["claim"]["progress"]["step"])
        if node["claim"]["progress"]["note"]:
            riga += t("progress.con_nota", nota=node["claim"]["progress"]["note"])
        print(riga)
        return 0

    if args.cmd == "amend":
        artefatti = _artefatti_cli(args.artefatti)
        with mutate.editing(ref) as g:
            node = mutate.amend(g, args.node, artifacts=artefatti,
                                cost=args.costo, summary=args.sintesi)
            corretti = node["amendments"][-1]["fields"]
        with read_transaction(ref.json_path) as data:
            refresh(ref, data)
        print(t("amend.fatto", id=args.node, campi=", ".join(corretti)))
        return 0

    if args.cmd == "ask":
        with mutate.editing(ref) as g:
            domanda = mutate.ask(g, args.node, args.question, args.assumption)
        print(t("ask.fatto", id=domanda["id"], origin=domanda["origin"], author=domanda["author"]))
        return 0

    if args.cmd == "asks":
        report.show_questions(ref, load(ref.json_path))
        return 0

    if args.cmd == "answer":
        with mutate.editing(ref) as g:
            domanda = mutate.answer(g, args.question, args.response)
        print(t("answer.fatto", id=domanda["id"], author=domanda["author"]))
        if domanda["answer"] != domanda["assumption"]:
            data = load(ref.json_path)
            riesame = topology.closed_downstream_after(data, domanda["origin"], domanda["askedAt"])
            if riesame:
                print(t("answer.divergente"))
                for node in riesame:
                    print(t("answer.riesame_riga", id=node["id"], title=node["title"]))
        return 0

    if args.cmd == "drift":
        report.show_drift(ref, load(ref.json_path))
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
    elif args.cmd == "give-up":
        node = claims.give_up(ref, args.node, args.motivo, args.dettaglio)
        print(t("give_up.fatto", id=node["id"], motivo=args.motivo))
    elif args.cmd == "ask-human":
        interazione = claims.ask_human(ref, args.node, args.domanda)
        print(t("ask_human.fatto", id=args.node, interazione=interazione["id"],
               scadenza=interazione["expiresAt"]))
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

    # Comandi di sola lettura: non rigenerano gli artefatti, escono prima. Il
    # rinnovo-su-lettura (sopra) puo' aver aggiornato il battito del lease scrivendo
    # il grafo, ma qui non si toccano i file derivati.
    if args.cmd == "status":
        report.show_status(ref, load(ref.json_path))
        return 0
    if args.cmd == "next":
        report.show_next(ref, load(ref.json_path))
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
