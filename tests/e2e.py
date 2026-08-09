#!/usr/bin/env python3
"""Prova end-to-end: installa dist/atlas in un progetto finto e lo usa.

Verifica quel che i test unitari non toccano, cioe' l'eseguibile visto da fuori:
merge degli hook, symlink delle skill, blocco in CLAUDE.md, idempotenza, il
registro globale, la migrazione da una versione precedente, l'uninstall, e il
ciclo di un nodo dal claim alla chiusura.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from atlascli.registry import slugify  # noqa: E402

CLI = ROOT / "dist" / "atlas"
FIXTURE = ROOT / "tests" / "fixtures" / "grafo-di-prova.py"

esiti: list[tuple[bool, str]] = []
# Il registro globale della sandbox in corso: locale() ne ha bisogno, e passarlo a ogni
# chiamata riempirebbe di rumore le verifiche, che sono la parte da leggere.
_config_sandbox: Path | None = None


def verifica(condizione: bool, cosa: str) -> None:
    esiti.append((bool(condizione), cosa))
    print(f"  {'ok  ' if condizione else 'ROTTO'} {cosa}")


def payload_pyc() -> list[str]:
    """I .pyc dentro il tar imbustato in dist/atlas, che dovrebbero essere zero.

    Si guarda il pacchetto e non il progetto installato: appena il motore gira si
    compila il proprio bytecode, quindi sul filesystem i .pyc ci sono comunque e
    la prova non distinguerebbe niente.
    """
    import base64, io, re, tarfile, zipfile  # noqa: E401  (solo per questa prova)
    sorgente = zipfile.ZipFile(CLI).read("atlascli/_payload.py").decode()
    blob = re.search(r'PAYLOAD_B64 = "([^"]+)"', sorgente).group(1)
    with tarfile.open(fileobj=io.BytesIO(base64.b64decode(blob))) as tf:
        return [m.name for m in tf.getmembers() if m.name.endswith(".pyc")]


def locale(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    """I comandi del grafo: dalla 0.7 li fa lo stesso eseguibile, dentro il progetto."""
    return subprocess.run([sys.executable, str(CLI), *args], cwd=cwd,
                          env=dict(os.environ, ATLAS_CONFIG=str(_config_sandbox)),
                          capture_output=True, text=True)


def globale(cwd: Path, *args: str, env: dict) -> subprocess.CompletedProcess:
    """Il CLI globale: dist/atlas <cmd>, con ATLAS_HOME isolato in una sandbox."""
    return subprocess.run([sys.executable, str(CLI), *args], cwd=cwd, env=env,
                          capture_output=True, text=True)


def prepara(target: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    (target / "CLAUDE.md").write_text("# Progetto finto\n\nRegole preesistenti.\n", encoding="utf-8")
    (target / ".claude").mkdir()
    (target / ".claude" / "settings.json").write_text(json.dumps(
        {"hooks": {"SessionEnd": [{"hooks": [{"type": "command", "command": "echo preesistente"}]}]}}
    ), encoding="utf-8")


def main() -> int:
    if not CLI.is_file():
        print("  Manca dist/atlas: lancia prima 'python3 build.py'.", file=sys.stderr)
        return 1
    global _config_sandbox
    target = Path(tempfile.mkdtemp())
    atlas_home = Path(tempfile.mkdtemp())
    atlas_config = atlas_home / "atlas.json"
    _config_sandbox = atlas_config
    env = dict(os.environ, ATLAS_CONFIG=str(atlas_config))
    try:
        prepara(target)
        print(f"\n  progetto finto in {target} · ATLAS_CONFIG in {atlas_config}\n")

        esito = globale(target, "install", str(target), "--yes", "--graph", "epic-test", env=env)
        verifica(esito.returncode == 0, "atlas install va a buon fine")
        radice = target / ".atlas"
        verifica((radice / "config.json").is_file(), "il progetto nasce con i suoi dati")
        verifica((radice / "README.md").is_file(), "README che spiega come ottenere atlas")
        verifica(not any((radice / v).exists() for v in ("core", "bin", "atlas", "templates", "hooks")),
                 "nel progetto non finisce una riga di motore")
        verifica((target / ".claude" / "skills" / "atlas-work").is_symlink(), "skill collegate con symlink")
        verifica((radice / "scripts" / "000-promote-fog.py").is_file(), "esempio promote-fog installato")
        verifica(not payload_pyc(), "nessun bytecode dentro il payload impacchettato")

        registro = json.loads(atlas_config.read_text(encoding="utf-8"))
        slug = slugify(target.resolve().name)  # register() slugifica il nome cartella, non lo usa nudo
        verifica(slug in registro["projects"], "progetto registrato nel registro globale")
        verifica(registro["projects"][slug]["path"] == str(target.resolve()),
                 "il registro punta al path giusto")

        impostazioni = json.loads((target / ".claude" / "settings.json").read_text(encoding="utf-8"))
        gruppi = impostazioni["hooks"]["SessionEnd"]
        verifica(len(gruppi) == 2, "hook aggiunto senza cancellare i preesistenti")
        verifica("preesistente" in json.dumps(gruppi[0]), "hook preesistente intatto")
        comando_hook = json.dumps(gruppi[1])
        verifica("atlas render --all" in comando_hook and ".atlas/hooks" not in comando_hook,
                 "l'hook chiama il comando, non uno script copiato nel progetto")

        contratto = (target / "CLAUDE.md").read_text(encoding="utf-8")
        verifica("Regole preesistenti." in contratto, "CLAUDE.md preesistente conservato")
        verifica(contratto.count("<!-- atlas:begin -->") == 1, "contratto appeso una volta sola")

        shutil.copyfile(FIXTURE, radice / "scripts" / "001-grafo-di-prova.py")
        locale(target, "exec", ".atlas/scripts/001-grafo-di-prova.py")
        grafo = json.loads((radice / "graphs" / "epic-test" / "graph.json").read_text(encoding="utf-8"))
        verifica(len(grafo["nodes"]) == 12, "script di mutazione applicato")

        uscita = locale(target, "status").stdout
        verifica("F01" in uscita and "D03" not in uscita, "la frontiera mostra solo i nodi sbloccati")

        aiuto = globale(target, "help", env=env).stdout
        verifica("install" in aiuto and "close" in aiuto,
                 "'atlas help' elenca gestione e grafo insieme, in un elenco solo")

        verifica(locale(target, "claim", "D03").returncode == 1, "claim di un nodo bloccato rifiutato")
        verifica(locale(target, "claim", "F01").returncode == 0, "claim di un nodo libero accettato")
        verifica(locale(target, "claim", "F02").returncode == 1, "un nodo per sessione")
        verifica(locale(target, "close", "F01", "-s", "x").returncode == 1, "close senza Risposta rifiutato")

        ticket = radice / "graphs" / "epic-test" / "tickets" / "F01.md"
        ticket.write_text(ticket.read_text(encoding="utf-8") + "\nLa risposta, scritta.\n", encoding="utf-8")
        verifica(locale(target, "close", "F01", "-s", "così si è deciso").returncode == 0, "close accettato")
        mappa = (radice / "graphs" / "epic-test" / "map.md").read_text(encoding="utf-8")
        verifica("così si è deciso" in mappa, "decisione registrata in map.md")
        verifica("F03" in locale(target, "status").stdout, "la frontiera è avanzata")

        brief = locale(target, "brief", "F03").stdout
        verifica("così si è deciso" in brief, "atlas brief mostra la risposta del bloccante F01")

        prossimo = locale(target, "next").stdout
        verifica("F03" in prossimo, "'atlas next' mostra la frontiera")

        presa = locale(target, "take", "F03")
        verifica(presa.returncode == 0, "'atlas take' rivendica il nodo")
        verifica("così si è deciso" in presa.stdout, "'atlas take' stampa il contesto insieme al claim")

        verifica(locale(target, "fog", "manca il suono dei passi", "--for", "F03").returncode == 0,
                 "fog con --for accettato")
        nebbia = locale(target, "fog", "--list").stdout
        verifica("manca il suono dei passi" in nebbia and "F03" in nebbia,
                 "fog --list mostra la voce col destinatario")

        ticket_f03 = (radice / "graphs" / "epic-test" / "tickets" / "F03.md").read_text(encoding="utf-8-sig")
        verifica("<!-- /atlas:auto -->" in ticket_f03, "il ticket nasce col confine fra parte generata e prosa")

        briefing = locale(target, "how-to").stdout
        verifica("il grafo comanda il lavoro" in briefing, "how-to stampa il contratto installato")
        verifica("mutate.add_node(g," in briefing and "atlas-work:" in briefing,
                 "how-to elenca le mutazioni e le skill")
        verifica(all(f"─── {n}." in briefing for n in range(1, 7)), "how-to ha tutte e sei le sezioni")

        locale(target, "new", "epic-secondo", "-t", "Secondo stream")
        verifica((radice / "graphs" / "epic-secondo" / "graph.json").is_file(), "secondo grafo creato")
        verifica("epic-test" in locale(target, "-g", "epic-test", "status").stdout, "override con --graph")
        verifica(len(json.loads((radice / "graphs" / "epic-secondo" / "graph.json")
                                .read_text(encoding="utf-8"))["nodes"]) == 0, "i due grafi restano isolati")

        html = (radice / "graphs" / "epic-test" / "dashboard.html").read_text(encoding="utf-8")
        verifica("<script" not in html and "cdn" not in html, "dashboard senza script né risorse remote")
        verifica("è" in html and "Ã" not in html, "accenti resi bene nella dashboard")

        elenco = globale(target, "list", env=env).stdout
        verifica(slug in elenco and "ok" in elenco, "'atlas list' mostra il progetto con stato ok")

        prima = (radice / "config.json").read_text(encoding="utf-8")
        esito = globale(target, "install", str(target), "--yes", env=env)
        verifica(esito.returncode == 0, "reinstallare su un progetto vivo va a buon fine")
        verifica((radice / "config.json").read_text(encoding="utf-8") == prima,
                 "reinstall: config intatta")
        verifica(len(json.loads((radice / "graphs" / "epic-test" / "graph.json")
                                .read_text(encoding="utf-8"))["nodes"]) == 12,
                 "reinstall: grafi intatti")
        verifica((target / "CLAUDE.md").read_text(encoding="utf-8").count("atlas:begin") == 1,
                 "reinstall: contratto non duplicato")

        dashboard = radice / "graphs" / "epic-test" / "dashboard.html"
        dashboard.unlink()
        esito = locale(target, "render", "--all")
        verifica(esito.returncode == 0 and dashboard.is_file(), "'render --all' rigenera le dashboard")
        verifica("2" in esito.stdout, "render --all: dice quanti grafi ha rigenerato")

        mappa_it_prima = (radice / "graphs" / "epic-test" / "map.md").read_text(encoding="utf-8")
        esito = locale(target, "lang", "en")
        verifica(esito.returncode == 0, "'atlas lang en' dentro il progetto va a buon fine")
        verifica(json.loads((radice / "config.json").read_text(encoding="utf-8"))["language"] == "en",
                 "lang en: config.json aggiornato")
        verifica("Works a node" in (target / ".claude" / "skills" / "atlas-work" / "SKILL.md"
                                    ).resolve().read_text(encoding="utf-8"),
                 "lang en: SKILL.md rigenerato in inglese")
        verifica("the graph runs the work" in (radice / "CONTRACT.md").read_text(encoding="utf-8"),
                 "lang en: CONTRACT.md rigenerato in inglese")
        verifica((radice / "graphs" / "epic-test" / "map.md").read_text(encoding="utf-8") == mappa_it_prima,
                 "lang en: map.md di un grafo preesistente resta invariato (intestazioni italiane)")

        locale(target, "new", "epic-en", "-t", "English stream", "-d", "Ships in English.")
        ticket_nuovo = radice / "graphs" / "epic-en" / "tickets"
        locale(target, "-g", "epic-en", "render")
        verifica(ticket_nuovo.is_dir() and not any(ticket_nuovo.iterdir()),
                 "lang en: nuovo grafo senza nodi, nessun ticket da creare")

        esito = locale(target, "lang", "it")
        verifica(json.loads((radice / "config.json").read_text(encoding="utf-8"))["language"] == "it",
                 "lang it: torna in italiano")

        rotti = [cosa for ok, cosa in esiti if not ok]
        print(f"\n  {len(esiti) - len(rotti)}/{len(esiti)} verifiche passate\n")
        return 1 if rotti else 0
    finally:
        shutil.rmtree(target, ignore_errors=True)
        shutil.rmtree(atlas_home, ignore_errors=True)


def verifica_install_in_inglese() -> None:
    """Un progetto installato da zero con --lang en produce ticket in inglese dal primo grafo."""
    target = Path(tempfile.mkdtemp())
    atlas_home = Path(tempfile.mkdtemp())
    env = dict(os.environ, ATLAS_CONFIG=str(atlas_home / "atlas.json"))
    try:
        subprocess.run(["git", "init", "-q"], cwd=target, check=True)
        globale(target, "install", str(target), "--yes", "--lang", "en", "--graph", "demo", env=env)
        radice = target / ".atlas"
        locale(target, "new-script", "primo")
        script = sorted((radice / "scripts").glob("*.py"))[-1]
        script.write_text(
            "from core import mutate\n\n"
            "def run(g):\n"
            '    mutate.add_branch(g, "F", "Foundations", "#4f46e5")\n'
            '    mutate.add_node(g, id="F01", branch="F", title="First", question="?")\n',
            encoding="utf-8",
        )
        locale(target, "exec", f".atlas/scripts/{script.name}")
        ticket = (radice / "graphs" / "demo" / "tickets" / "F01.md").read_text(encoding="utf-8")
        verifica("## Question" in ticket and "## Domanda" not in ticket,
                 "install --lang en: il primo ticket usa le intestazioni inglesi")
    finally:
        shutil.rmtree(target, ignore_errors=True)
        shutil.rmtree(atlas_home, ignore_errors=True)


def verifica_migrazione_dal_motore_a_sorgenti() -> None:
    """Un progetto installato quando il motore era core/ + bin/ passa all'archivio unico.

    La migrazione la si fa una volta sola e deve funzionare al primo colpo, quindi
    il layout vecchio va ricostruito davvero invece che dato per buono: qui si
    fabbricano le due cartelle e si controlla che l'update se le porti via senza
    toccare i dati, che sono l'unica cosa che l'utente non puo' rigenerare.
    """
    target = Path(tempfile.mkdtemp())
    atlas_home = Path(tempfile.mkdtemp())
    env = dict(os.environ, ATLAS_CONFIG=str(atlas_home / "atlas.json"))
    try:
        subprocess.run(["git", "init", "-q"], cwd=target, check=True)
        globale(target, "install", str(target), "--yes", "--graph", "epic-test", env=env)
        radice = target / ".atlas"
        grafo = radice / "graphs" / "epic-test" / "graph.json"
        prima = grafo.read_text(encoding="utf-8")

        vecchio_core = radice / "core"
        vecchio_core.mkdir()
        (vecchio_core / "cli.py").write_text("# motore di una versione precedente\n", encoding="utf-8")
        (vecchio_core / "__pycache__").mkdir()
        (vecchio_core / "__pycache__" / "cli.pyc").write_bytes(b"\x00")
        (radice / "bin").mkdir()
        (radice / "bin" / "atlas").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        (radice / "atlas").write_text("archivio della 0.6\n", encoding="utf-8")
        (radice / "templates").mkdir()
        (radice / "hooks").mkdir()
        (radice / "VERSION").write_text("0.5.4\n", encoding="utf-8")

        esito = globale(target, "install", str(target), "--yes", env=env)
        verifica(esito.returncode == 0, "migrazione: reinstallare su un progetto vecchio va a buon fine")
        verifica(not any((radice / v).exists() for v in ("core", "bin", "atlas", "templates", "hooks")),
                 "migrazione: del motore vecchio non resta niente")
        verifica("rimossi dalla versione precedente" in esito.stdout,
                 "migrazione: l'installazione dice cosa ha portato via")
        verifica((radice / "README.md").is_file(), "migrazione: arriva il README che spiega la cartella")
        verifica(grafo.read_text(encoding="utf-8") == prima, "migrazione: i dati del grafo sono intatti")
    finally:
        shutil.rmtree(target, ignore_errors=True)
        shutil.rmtree(atlas_home, ignore_errors=True)


def verifica_uninstall() -> None:
    """uninstall toglie Atlas e lascia i dati: e' la promessa scritta nel messaggio."""
    target = Path(tempfile.mkdtemp())
    atlas_home = Path(tempfile.mkdtemp())
    env = dict(os.environ, ATLAS_CONFIG=str(atlas_home / "atlas.json"))
    try:
        subprocess.run(["git", "init", "-q"], cwd=target, check=True)
        globale(target, "install", str(target), "--yes", "--graph", "epic-test", env=env)
        radice = target / ".atlas"
        esito = globale(target, "uninstall", str(target), env=env)
        verifica(esito.returncode == 0, "uninstall va a buon fine")
        verifica(not (radice / "skills").exists() and not (radice / "CONTRACT.md").exists(),
                 "uninstall: quel che aveva scritto Atlas non c'e' piu'")
        verifica((radice / "graphs" / "epic-test" / "graph.json").is_file(),
                 "uninstall: i dati del progetto restano")
        verifica((radice / "config.json").is_file(), "uninstall: config.json resta")
        verifica(not (target / ".claude" / "skills" / "atlas-work").exists(),
                 "uninstall: le skill sono scollegate da .claude/")
    finally:
        shutil.rmtree(target, ignore_errors=True)
        shutil.rmtree(atlas_home, ignore_errors=True)


if __name__ == "__main__":
    esito = main()
    verifica_install_in_inglese()
    verifica_migrazione_dal_motore_a_sorgenti()
    verifica_uninstall()
    rotti = [cosa for ok, cosa in esiti if not ok]
    print(f"\n  totale: {len(esiti) - len(rotti)}/{len(esiti)} verifiche passate\n")
    raise SystemExit(1 if rotti else esito)
