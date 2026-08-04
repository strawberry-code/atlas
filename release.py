#!/usr/bin/env python3
"""Runbook di release: python3 release.py X.Y.Z

Fa solo le parti meccaniche e reversibili (bump versione, build, test, sha256):
stampa senza eseguire i comandi che toccano git/GitHub. Nessuna riga di questo
script pusha o tagga da sola.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "payload" / "VERSION"
CLI_OUT = ROOT / "dist" / "atlas"
VERSIONE_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _git_pulito() -> bool:
    esito = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True)
    return esito.stdout.strip() == ""


def _ripristina() -> None:
    """Se build o test falliscono a meta', VERSION/dist restano sporchi: si parte da
    git pulito (vedi _git_pulito sopra), quindi un git checkout li riporta esattamente
    com'erano. Senza questo, un fallimento lascia una release a meta' nel working tree.
    """
    subprocess.run(["git", "checkout", "--", str(VERSION_FILE), str(CLI_OUT), str(CLI_OUT.with_suffix(".sha256"))],
                    cwd=ROOT)
    print("  ripristinati payload/VERSION, dist/atlas, dist/atlas.sha256", file=sys.stderr)


def main() -> int:
    if len(sys.argv) != 2 or not VERSIONE_RE.match(sys.argv[1]):
        print("  uso: python3 release.py X.Y.Z", file=sys.stderr)
        return 1
    versione = sys.argv[1]

    if not _git_pulito():
        print("  git status non pulito: committa o metti da parte prima di tagliare una release.",
              file=sys.stderr)
        return 1

    VERSION_FILE.write_text(f"{versione}\n", encoding="utf-8")
    print(f"  payload/VERSION -> {versione}")

    if subprocess.run([sys.executable, "build.py"], cwd=ROOT).returncode != 0:
        _ripristina()
        return 1

    unit = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=ROOT)
    e2e = subprocess.run([sys.executable, "tests/e2e.py"], cwd=ROOT)
    if unit.returncode != 0 or e2e.returncode != 0:
        print("\n  test falliti: la release non procede.\n", file=sys.stderr)
        _ripristina()
        return 1

    sha = hashlib.sha256(CLI_OUT.read_bytes()).hexdigest()
    print(f"\n  {versione} pronta · sha256 dist/atlas: {sha}\n")
    print("  Passi finali, a mano (nessuno eseguito da questo script):\n")
    print("    git add payload/VERSION dist/atlas dist/atlas.sha256")
    print(f'    git commit -m "chore(release): {versione}"')
    print(f'    git tag -a v{versione} -m "Atlas {versione}"')
    print("    git push origin main --tags")
    print(f'    gh release create v{versione} dist/atlas dist/atlas.sha256 '
          f'--title "Atlas {versione}" --notes "..."')
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
