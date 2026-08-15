#!/usr/bin/env python3
"""Prova end-to-end: installa dist/atlas in un progetto finto e lo usa.

Verifica quel che i test unitari non toccano, cioe' l'eseguibile visto da fuori:
merge degli hook, symlink delle skill, blocco in CLAUDE.md, idempotenza, il
registro globale, la migrazione da una versione precedente, l'uninstall, il
riallineamento dei progetti dopo un aggiornamento, e il ciclo di un nodo dal
claim alla chiusura.
"""
from __future__ import annotations

import hashlib
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
        verifica(" src=" not in html and "<link" not in html and "cdn" not in html,
                 "dashboard senza risorse remote: stile, script e ticket viaggiano inline")
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


def verifica_update_riallinea_i_progetti() -> None:
    """'atlas update' rimette in pari i progetti registrati, col binario vero.

    I test unitari coprono la stessa logica sui moduli sorgente; qui si prova
    l'eseguibile impacchettato, perche' e' quello che riallinea davvero: la
    versione nuova viene invocata come sottoprocesso, e se il pacchetto non
    contenesse il modulo, o l'invocazione sbagliasse strada, i test unitari non
    se ne accorgerebbero. Il 'binario nuovo' pubblicato dal fixture e' dist/atlas
    stesso, quindi l'aggiornamento e' vero dal download all'impronta.
    """
    from tests.httpfixture import Fixture

    sandbox = Path(tempfile.mkdtemp())
    binario = sandbox / "atlas"
    shutil.copyfile(CLI, binario)
    binario.chmod(0o755)
    blob = binario.read_bytes()
    fixture = Fixture({})
    fixture.start()
    try:
        release = {"tag_name": "v9.9.9", "assets": [
            {"name": "atlas", "browser_download_url": f"{fixture.base_url}/asset/atlas"},
            {"name": "atlas.sha256", "browser_download_url": f"{fixture.base_url}/asset/atlas.sha256"}]}
        fixture.routes["/repos/strawberry-code/atlas/releases/latest"] = (
            200, json.dumps(release).encode("utf-8"), "application/json")
        fixture.routes["/asset/atlas"] = (200, blob, "application/octet-stream")
        fixture.routes["/asset/atlas.sha256"] = (
            200, f"{hashlib.sha256(blob).hexdigest()}  atlas\n".encode("utf-8"), "text/plain")
        env = dict(os.environ, ATLAS_CONFIG=str(sandbox / "registro.json"),
                   ATLAS_UPDATE_BASE_URL=fixture.base_url)

        def atlas(*args):
            return subprocess.run([sys.executable, str(binario), *args], env=env,
                                  capture_output=True, text=True)

        for nome in ("alfa", "beta"):
            (sandbox / nome).mkdir()
            atlas("install", str(sandbox / nome), "--yes")
        (sandbox / "sparito").mkdir()
        atlas("install", str(sandbox / "sparito"), "--yes")
        shutil.rmtree(sandbox / "sparito")          # registrato, ma non piu' sul disco
        for nome in ("alfa", "beta"):
            (sandbox / nome / ".atlas" / "CONTRACT.md").write_text("MANOMESSO\n", encoding="utf-8")
        (sandbox / "beta" / "CLAUDE.md").unlink()   # beta senza blocco: non deve tornare

        esito = atlas("update")
        verifica(esito.returncode == 0, "update: riesce anche con un progetto sparito nel registro")
        verifica((sandbox / "alfa" / ".atlas" / "CONTRACT.md").read_text(encoding="utf-8") != "MANOMESSO\n",
                 "update: il contratto dei progetti torna quello della versione nuova")
        verifica("sparito" in esito.stdout, "update: il progetto sparito viene nominato, non taciuto")
        verifica(not (sandbox / "beta" / "CLAUDE.md").exists(),
                 "update: non rimette il blocco a chi non lo aveva")

        # Il caso di chi ha aggiornato da una versione che ancora non riallineava:
        # l'eseguibile e' all'ultima, i progetti no, e non c'e' nessun download da
        # cui accorgersene. Senza questo passaggio resterebbero indietro per sempre.
        versione = (ROOT / "payload" / "VERSION").read_text(encoding="utf-8").strip()
        release["tag_name"] = f"v{versione}"
        fixture.routes["/repos/strawberry-code/atlas/releases/latest"] = (
            200, json.dumps(release).encode("utf-8"), "application/json")
        registro = json.loads((sandbox / "registro.json").read_text(encoding="utf-8"))
        registro["projects"]["alfa"].pop("version", None)     # registrato da una versione precedente
        (sandbox / "registro.json").write_text(json.dumps(registro), encoding="utf-8")
        (sandbox / "alfa" / ".atlas" / "CONTRACT.md").write_text("MANOMESSO\n", encoding="utf-8")
        (sandbox / "beta" / ".atlas" / "CONTRACT.md").write_text("MANOMESSO\n", encoding="utf-8")
        esito = atlas("update")
        verifica((sandbox / "alfa" / ".atlas" / "CONTRACT.md").read_text(encoding="utf-8") != "MANOMESSO\n",
                 "update: senza niente da scaricare rimette in pari chi era indietro")
        verifica((sandbox / "beta" / ".atlas" / "CONTRACT.md").read_text(encoding="utf-8") == "MANOMESSO\n",
                 "update: chi e' gia' in pari non viene reinstallato a ogni giro")
    finally:
        fixture.stop()
        shutil.rmtree(sandbox, ignore_errors=True)


def verifica_file_rotti() -> None:
    """Un JSON malformato deve diventare un messaggio, e non deve murare il progetto.

    Prima di questa prova un carattere di troppo in config.json faceva uscire un
    traceback da ogni comando, compresi 'list' e 'uninstall', cioe' i due con cui si
    esce dal guasto.
    """
    target = Path(tempfile.mkdtemp())
    atlas_home = Path(tempfile.mkdtemp())
    env = dict(os.environ, ATLAS_CONFIG=str(atlas_home / "atlas.json"))
    try:
        subprocess.run(["git", "init", "-q"], cwd=target, check=True)
        globale(target, "install", str(target), "--yes", "--graph", "epic-test", env=env)

        grafo = target / ".atlas" / "graphs" / "epic-test" / "graph.json"
        grafo.write_text('{"nodes": [', encoding="utf-8")
        esito = globale(target, "validate", env=env)
        verifica("Traceback" not in esito.stderr and "graph.json" in esito.stderr,
                 "grafo rotto: validate lo dice invece di morire")
        esito = globale(target, "doctor", env=env)
        verifica("Traceback" not in esito.stderr and "graph.json" in esito.stdout,
                 "grafo rotto: doctor lo diagnostica")
        grafo.write_text('{"meta": {"slug": "epic-test"}, "nodes": []}', encoding="utf-8")

        (target / ".atlas" / "config.json").write_text("{ rotto", encoding="utf-8")
        esito = globale(target, "status", env=env)
        verifica("Traceback" not in esito.stderr and "config.json" in esito.stderr,
                 "config rotto: il messaggio dice quale file aprire")
        esito = globale(target, "list", env=env)
        verifica(esito.returncode == 0, "config rotto: i comandi globali funzionano lo stesso")
        esito = globale(target, "uninstall", str(target), env=env)
        verifica(esito.returncode == 0 and "Traceback" not in esito.stderr,
                 "config rotto: uninstall resta una via d'uscita")

        registro = atlas_home / "atlas.json"
        registro.write_text("{ rotto", encoding="utf-8")
        esito = globale(target, "list", env=env)
        verifica("Traceback" not in esito.stderr and "atlas.json" in esito.stderr,
                 "registro rotto: lo dice invece di morire")
        esito = globale(target, "--version", env=env)
        verifica(esito.returncode == 0, "registro rotto: --version funziona lo stesso")
    finally:
        shutil.rmtree(target, ignore_errors=True)
        shutil.rmtree(atlas_home, ignore_errors=True)


def verifica_hook_una_volta_sola() -> None:
    """Install e' idempotente sull'hook, uninstall lo toglie, quelli di altri restano."""
    target = Path(tempfile.mkdtemp())
    atlas_home = Path(tempfile.mkdtemp())
    env = dict(os.environ, ATLAS_CONFIG=str(atlas_home / "atlas.json"))
    impostazioni = target / ".claude" / "settings.json"

    def gruppi() -> list:
        return json.loads(impostazioni.read_text(encoding="utf-8"))["hooks"]["SessionEnd"]

    try:
        subprocess.run(["git", "init", "-q"], cwd=target, check=True)
        (target / ".claude").mkdir()
        # Un hook della 0.6, morto dalla 0.7, piu' uno di qualcun altro.
        impostazioni.write_text(json.dumps({"hooks": {"SessionEnd": [
            {"hooks": [{"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/.atlas/hooks/session_end.py"'}]},
            {"hooks": [{"type": "command", "command": "echo preesistente"}]},
        ]}}), encoding="utf-8")

        globale(target, "install", str(target), "--yes", env=env)
        testo = json.dumps(gruppi())
        verifica("session_end.py" not in testo, "hook: quello morto della 0.6 viene sostituito")
        verifica("echo preesistente" in testo, "hook: quelli di altri restano")
        verifica(testo.count("atlas render --all") == 1, "hook: uno solo dopo la prima install")

        globale(target, "install", str(target), "--yes", env=env)
        globale(target, "install", str(target), "--yes", env=env)
        verifica(json.dumps(gruppi()).count("atlas render --all") == 1,
                 "hook: tre install ne lasciano sempre uno solo")

        globale(target, "uninstall", str(target), env=env)
        testo = json.dumps(gruppi())
        verifica("atlas render" not in testo, "hook: uninstall lo toglie")
        verifica("echo preesistente" in testo, "hook: uninstall non tocca quelli di altri")

        # settings.json senza la chiave 'hooks': l'uninstall ci moriva sopra a meta' lavoro.
        secondo = Path(tempfile.mkdtemp())
        try:
            subprocess.run(["git", "init", "-q"], cwd=secondo, check=True)
            globale(secondo, "install", str(secondo), "--yes", "--no-hooks", env=env)
            (secondo / ".claude").mkdir(exist_ok=True)
            (secondo / ".claude" / "settings.json").write_text('{"permissions": {}}', encoding="utf-8")
            esito = globale(secondo, "uninstall", str(secondo), env=env)
            verifica(esito.returncode == 0 and "Traceback" not in esito.stderr,
                     "hook: uninstall regge un settings.json senza 'hooks'")
        finally:
            shutil.rmtree(secondo, ignore_errors=True)
    finally:
        shutil.rmtree(target, ignore_errors=True)
        shutil.rmtree(atlas_home, ignore_errors=True)


def verifica_uscita_non_utf8() -> None:
    """Output rediretto e codifica di sistema non UTF-8: e' il caso di Windows quando
    si scrive su file o in pipe, dove cp1252 non sa rappresentare i nostri caratteri."""
    target = Path(tempfile.mkdtemp())
    atlas_home = Path(tempfile.mkdtemp())
    env = dict(os.environ, ATLAS_CONFIG=str(atlas_home / "atlas.json"), PYTHONIOENCODING="ascii")
    try:
        subprocess.run(["git", "init", "-q"], cwd=target, check=True)
        globale(target, "install", str(target), "--yes", "--graph", "epic-test", env=env)
        for comando in ("how-to", "status", "doctor"):
            esito = globale(target, comando, env=env)
            verifica(esito.returncode == 0 and "UnicodeEncodeError" not in esito.stderr,
                     f"stdout non UTF-8: '{comando}' non ci muore sopra")
        esito = globale(target, "how-to", env=env)
        verifica("─" in esito.stdout and "Ã" not in esito.stdout,
                 "stdout non UTF-8: i caratteri escono interi, non in mojibake")
    finally:
        shutil.rmtree(target, ignore_errors=True)
        shutil.rmtree(atlas_home, ignore_errors=True)


MUTAZIONE_ESTERNA = '''"""Un altro attore che cambia il nodo mentre qualcuno ci lavora."""


def run(g):
    g.node("F01")["question"] = "la domanda e' cambiata sotto le mani di chi lavora"
'''


def verifica_scrittura_e_conflitti() -> None:
    """La scrittura atomica vista da fuori, e il rifiuto quando la premessa e' scaduta."""
    target = Path(tempfile.mkdtemp())
    atlas_home = Path(tempfile.mkdtemp())
    env = dict(os.environ, ATLAS_CONFIG=str(atlas_home / "atlas.json"))
    global _config_sandbox
    _config_sandbox = atlas_home / "atlas.json"
    try:
        subprocess.run(["git", "init", "-q"], cwd=target, check=True)
        globale(target, "install", str(target), "--yes", "--graph", "epic-test", env=env)
        radice = target / ".atlas"
        shutil.copyfile(FIXTURE, radice / "scripts" / "001-grafo-di-prova.py")
        locale(target, "exec", ".atlas/scripts/001-grafo-di-prova.py")
        grafo = radice / "graphs" / "epic-test" / "graph.json"

        verifica(grafo.with_name("graph.json.lock").is_file(),
                 "il lock vive su un file dedicato accanto al grafo")
        verifica(list(grafo.parent.glob("*.tmp")) == [],
                 "nessun temporaneo resta dopo una scrittura riuscita")
        for nome in ("graph.json.lock", ".graph.json.tmp"):
            ignorato = subprocess.run(["git", "check-ignore", "-q", str(grafo.with_name(nome))],
                                      cwd=target).returncode == 0
            verifica(ignorato, f"{nome} non finisce versionato nel progetto ospite")
        tracciato = subprocess.run(["git", "check-ignore", "-q", str(grafo)], cwd=target)
        verifica(tracciato.returncode != 0, "il grafo invece resta versionato")

        locale(target, "claim", "F01")
        ticket = radice / "graphs" / "epic-test" / "tickets" / "F01.md"
        ticket.write_text(ticket.read_text(encoding="utf-8").replace(
            "## Risposta", "## Risposta\n\nUna risposta scritta guardando la domanda di prima."),
            encoding="utf-8")

        (radice / "scripts" / "002-altro-attore.py").write_text(MUTAZIONE_ESTERNA, encoding="utf-8")
        locale(target, "exec", ".atlas/scripts/002-altro-attore.py")

        rifiuto = locale(target, "close", "F01", "-s", "sintesi")
        verifica(rifiuto.returncode == 1 and "F01" in (rifiuto.stdout + rifiuto.stderr),
                 "close rifiutato: il nodo e' cambiato dopo la presa")
        forzato = locale(target, "close", "F01", "-s", "sintesi", "--force")
        verifica(forzato.returncode == 0, "--force chiude comunque")
        stato = json.loads(grafo.read_text(encoding="utf-8"))
        chiuso = [n for n in stato["nodes"] if n["id"] == "F01"][0]
        verifica(chiuso["status"] == "closed", "il nodo forzato risulta chiuso nel grafo")
    finally:
        shutil.rmtree(target, ignore_errors=True)
        shutil.rmtree(atlas_home, ignore_errors=True)


if __name__ == "__main__":
    esito = main()
    verifica_install_in_inglese()
    verifica_migrazione_dal_motore_a_sorgenti()
    verifica_uninstall()
    verifica_update_riallinea_i_progetti()
    verifica_file_rotti()
    verifica_hook_una_volta_sola()
    verifica_uscita_non_utf8()
    verifica_scrittura_e_conflitti()
    rotti = [cosa for ok, cosa in esiti if not ok]
    print(f"\n  totale: {len(esiti) - len(rotti)}/{len(esiti)} verifiche passate\n")
    raise SystemExit(1 if rotti else esito)
