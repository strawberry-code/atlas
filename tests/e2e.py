#!/usr/bin/env python3
"""Prova end-to-end: installa dist/atlas-install.py in un progetto finto e lo usa.

Verifica quel che i test unitari non toccano, cioe' l'installer e la CLI viste da
fuori: merge degli hook, symlink delle skill, blocco in CLAUDE.md, idempotenza, e
il ciclo di un nodo dal claim alla chiusura.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "dist" / "atlas-install.py"
FIXTURE = ROOT / "tests" / "fixtures" / "grafo-di-prova.py"

esiti: list[tuple[bool, str]] = []


def verifica(condizione: bool, cosa: str) -> None:
    esiti.append((bool(condizione), cosa))
    print(f"  {'ok  ' if condizione else 'ROTTO'} {cosa}")


def atlas(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(cwd / ".atlas" / "bin" / "atlas"), *args],
                          cwd=cwd, capture_output=True, text=True)


def prepara(target: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=target, check=True)
    (target / "CLAUDE.md").write_text("# Progetto finto\n\nRegole preesistenti.\n", encoding="utf-8")
    (target / ".claude").mkdir()
    (target / ".claude" / "settings.json").write_text(json.dumps(
        {"hooks": {"SessionEnd": [{"hooks": [{"type": "command", "command": "echo preesistente"}]}]}}
    ), encoding="utf-8")


def main() -> int:
    if not INSTALLER.is_file():
        print("  Manca dist/atlas-install.py: lancia prima 'python3 build.py'.", file=sys.stderr)
        return 1
    target = Path(tempfile.mkdtemp())
    try:
        prepara(target)
        print(f"\n  progetto finto in {target}\n")

        subprocess.run([sys.executable, str(INSTALLER), "--yes", "--graph", "epic-test"],
                       cwd=target, capture_output=True, text=True, check=True)
        radice = target / ".atlas"
        verifica((radice / "core" / "cli.py").is_file(), "motore scompattato")
        verifica((radice / "bin" / "atlas").stat().st_mode & 0o111, "entrypoint eseguibile")
        verifica((target / ".claude" / "skills" / "atlas-work").is_symlink(), "skill collegate con symlink")

        impostazioni = json.loads((target / ".claude" / "settings.json").read_text(encoding="utf-8"))
        gruppi = impostazioni["hooks"]["SessionEnd"]
        verifica(len(gruppi) == 2, "hook aggiunto senza cancellare i preesistenti")
        verifica("preesistente" in json.dumps(gruppi[0]), "hook preesistente intatto")

        contratto = (target / "CLAUDE.md").read_text(encoding="utf-8")
        verifica("Regole preesistenti." in contratto, "CLAUDE.md preesistente conservato")
        verifica(contratto.count("<!-- atlas:begin -->") == 1, "contratto appeso una volta sola")

        shutil.copyfile(FIXTURE, radice / "scripts" / "001-grafo-di-prova.py")
        atlas(target, "exec", ".atlas/scripts/001-grafo-di-prova.py")
        grafo = json.loads((radice / "graphs" / "epic-test" / "graph.json").read_text(encoding="utf-8"))
        verifica(len(grafo["nodes"]) == 12, "script di mutazione applicato")

        uscita = atlas(target, "status").stdout
        verifica("F01" in uscita and "D03" not in uscita, "la frontiera mostra solo i nodi sbloccati")

        verifica(atlas(target, "claim", "D03").returncode == 1, "claim di un nodo bloccato rifiutato")
        verifica(atlas(target, "claim", "F01").returncode == 0, "claim di un nodo libero accettato")
        verifica(atlas(target, "claim", "F02").returncode == 1, "un nodo per sessione")
        verifica(atlas(target, "close", "F01", "-s", "x").returncode == 1, "close senza Risposta rifiutato")

        ticket = radice / "graphs" / "epic-test" / "tickets" / "F01.md"
        ticket.write_text(ticket.read_text(encoding="utf-8") + "\nLa risposta, scritta.\n", encoding="utf-8")
        verifica(atlas(target, "close", "F01", "-s", "così si è deciso").returncode == 0, "close accettato")
        mappa = (radice / "graphs" / "epic-test" / "map.md").read_text(encoding="utf-8")
        verifica("così si è deciso" in mappa, "decisione registrata in map.md")
        verifica("F03" in atlas(target, "status").stdout, "la frontiera è avanzata")

        atlas(target, "new", "epic-secondo", "-t", "Secondo stream")
        verifica((radice / "graphs" / "epic-secondo" / "graph.json").is_file(), "secondo grafo creato")
        verifica("epic-test" in atlas(target, "-g", "epic-test", "status").stdout, "override con --graph")
        verifica(len(json.loads((radice / "graphs" / "epic-secondo" / "graph.json")
                                .read_text(encoding="utf-8"))["nodes"]) == 0, "i due grafi restano isolati")

        html = (radice / "graphs" / "epic-test" / "dashboard.html").read_text(encoding="utf-8")
        verifica("<script" not in html and "cdn" not in html, "dashboard senza script né risorse remote")
        verifica("è" in html and "Ã" not in html, "accenti resi bene nella dashboard")

        prima = (radice / "config.json").read_text(encoding="utf-8")
        subprocess.run([sys.executable, str(INSTALLER), "--yes"], cwd=target,
                       capture_output=True, text=True, check=True)
        verifica((radice / "config.json").read_text(encoding="utf-8") == prima, "reinstallazione: config intatta")
        verifica(len(json.loads((radice / "graphs" / "epic-test" / "graph.json")
                                .read_text(encoding="utf-8"))["nodes"]) == 12, "reinstallazione: grafi intatti")
        verifica((target / "CLAUDE.md").read_text(encoding="utf-8").count("atlas:begin") == 1,
                 "reinstallazione: contratto non duplicato")

        rotti = [cosa for ok, cosa in esiti if not ok]
        print(f"\n  {len(esiti) - len(rotti)}/{len(esiti)} verifiche passate\n")
        return 1 if rotti else 0
    finally:
        shutil.rmtree(target, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
