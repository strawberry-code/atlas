#!/usr/bin/env python3
"""Prova end-to-end: installa dist/atlas in un progetto finto e lo usa.

Verifica quel che i test unitari non toccano, cioe' il CLI globale e il motore
per-progetto visti da fuori: merge degli hook, symlink delle skill, blocco in
CLAUDE.md, idempotenza, il registro globale, il passthrough dei comandi di
progetto, e il ciclo di un nodo dal claim alla chiusura.
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


def verifica(condizione: bool, cosa: str) -> None:
    esiti.append((bool(condizione), cosa))
    print(f"  {'ok  ' if condizione else 'ROTTO'} {cosa}")


def locale(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    """Il motore per-progetto, invocato direttamente: .atlas/bin/atlas <cmd>."""
    return subprocess.run([str(cwd / ".atlas" / "bin" / "atlas"), *args],
                          cwd=cwd, capture_output=True, text=True)


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
    target = Path(tempfile.mkdtemp())
    atlas_home = Path(tempfile.mkdtemp())
    atlas_config = atlas_home / "atlas.json"
    env = dict(os.environ, ATLAS_CONFIG=str(atlas_config))
    try:
        prepara(target)
        print(f"\n  progetto finto in {target} · ATLAS_CONFIG in {atlas_config}\n")

        esito = globale(target, "install", str(target), "--yes", "--graph", "epic-test", env=env)
        verifica(esito.returncode == 0, "atlas install va a buon fine")
        radice = target / ".atlas"
        verifica((radice / "core" / "cli.py").is_file(), "motore scompattato")
        verifica((radice / "bin" / "atlas").stat().st_mode & 0o111, "entrypoint eseguibile")
        verifica((target / ".claude" / "skills" / "atlas-work").is_symlink(), "skill collegate con symlink")

        registro = json.loads(atlas_config.read_text(encoding="utf-8"))
        slug = slugify(target.resolve().name)  # register() slugifica il nome cartella, non lo usa nudo
        verifica(slug in registro["projects"], "progetto registrato nel registro globale")
        verifica(registro["projects"][slug]["path"] == str(target.resolve()),
                 "il registro punta al path giusto")

        impostazioni = json.loads((target / ".claude" / "settings.json").read_text(encoding="utf-8"))
        gruppi = impostazioni["hooks"]["SessionEnd"]
        verifica(len(gruppi) == 2, "hook aggiunto senza cancellare i preesistenti")
        verifica("preesistente" in json.dumps(gruppi[0]), "hook preesistente intatto")

        contratto = (target / "CLAUDE.md").read_text(encoding="utf-8")
        verifica("Regole preesistenti." in contratto, "CLAUDE.md preesistente conservato")
        verifica(contratto.count("<!-- atlas:begin -->") == 1, "contratto appeso una volta sola")

        shutil.copyfile(FIXTURE, radice / "scripts" / "001-grafo-di-prova.py")
        locale(target, "exec", ".atlas/scripts/001-grafo-di-prova.py")
        grafo = json.loads((radice / "graphs" / "epic-test" / "graph.json").read_text(encoding="utf-8"))
        verifica(len(grafo["nodes"]) == 12, "script di mutazione applicato")

        uscita = locale(target, "status").stdout
        verifica("F01" in uscita and "D03" not in uscita, "la frontiera mostra solo i nodi sbloccati")

        passthrough = globale(target, "status", env=env)
        verifica(passthrough.stdout == uscita, "il passthrough del CLI globale == il motore locale")

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

        verifica(locale(target, "fog", "manca il suono dei passi", "--for", "F03").returncode == 0,
                 "fog con --for accettato")
        nebbia = locale(target, "fog", "--list").stdout
        verifica("manca il suono dei passi" in nebbia and "F03" in nebbia,
                 "fog --list mostra la voce col destinatario")

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
        esito = globale(target, slug, "update", env=env)
        verifica(esito.returncode == 0, "'atlas <slug> update' va a buon fine")
        verifica((radice / "config.json").read_text(encoding="utf-8") == prima,
                 "slug update: config intatta")
        verifica(len(json.loads((radice / "graphs" / "epic-test" / "graph.json")
                                .read_text(encoding="utf-8"))["nodes"]) == 12,
                 "slug update: grafi intatti")
        verifica((target / "CLAUDE.md").read_text(encoding="utf-8").count("atlas:begin") == 1,
                 "slug update: contratto non duplicato")
        verifica("ridisegnati 2/2" in esito.stdout, "slug update: redraw automatico riportato nel riepilogo")

        dashboard = radice / "graphs" / "epic-test" / "dashboard.html"
        dashboard.unlink()
        esito = globale(target, slug, "redraw", env=env)
        verifica(esito.returncode == 0 and dashboard.is_file(), "'atlas <slug> redraw' rigenera la dashboard")
        verifica("ridisegnati 2/2" in esito.stdout, "redraw: riepilogo corretto")

        mappa_it_prima = (radice / "graphs" / "epic-test" / "map.md").read_text(encoding="utf-8")
        esito = globale(target, slug, "lang", "en", env=env)
        verifica("regenerated" in esito.stdout, "'atlas <slug> lang en' produce un riepilogo")
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

        esito = globale(target, slug, "lang", "it", env=env)
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
        script = sorted((radice / "scripts").glob("*.py"))[0]
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


if __name__ == "__main__":
    esito = main()
    verifica_install_in_inglese()
    rotti = [cosa for ok, cosa in esiti if not ok]
    print(f"\n  totale: {len(esiti) - len(rotti)}/{len(esiti)} verifiche passate\n")
    raise SystemExit(1 if rotti else esito)
