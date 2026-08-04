#!/usr/bin/env python3
"""Orchestratore di release: dalla modifica in working tree alla release GitHub.

Fa a macchina la parte meccanica che release.py lascia a mano (commit, tag, push,
gh release): resta solo da scegliere versione, cosa va nel commit di feature e cosa
dice la release.

    python3 ship.py X.Y.Z --add file1 file2 --commit-file msg.txt --notes-file notes.txt

--add e --commit-file riguardano il commit di feature che precede il bump di versione;
si possono omettere se il working tree e' gia' pulito (release-only, senza nulla di
nuovo da committare prima). --notes-file e' sempre richiesto: diventa il corpo della
release GitHub via 'gh release create --notes-file'. Messaggio del commit di release
e messaggio del tag restano fissi ("chore(release): X.Y.Z" / "Atlas X.Y.Z"): non sono
parametri perche' non cambiano mai forma.

I messaggi passano da file e non da argomenti per lo stesso motivo per cui i commit
italiani vanno scritti a mano e non con sed: un argomento da riga di comando rompe
gli accenti e gli apostrofi con la stessa facilita' con cui un file di testo non lo fa.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSIONE_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _run(argv: list[str]) -> int:
    print(f"  $ {' '.join(argv)}", flush=True)
    return subprocess.run(argv, cwd=ROOT).returncode


def commit_feature(add: list[str], commit_file: Path | None) -> int:
    """Aggiunge e committa solo se --add porta davvero qualcosa in stage."""
    if not add:
        return 0
    if (esito := _run(["git", "add", *add])) != 0:
        return esito
    niente_in_stage = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0
    if niente_in_stage:
        print("  niente in stage dopo --add: proseguo con la release")
        return 0
    return _run(["git", "commit", "-F", str(commit_file)])


def main() -> int:
    parser = argparse.ArgumentParser(description="Commit di feature (opzionale) + release.py + tag/push/gh release.")
    parser.add_argument("versione", help="X.Y.Z")
    parser.add_argument("--add", nargs="*", default=[], help="path da aggiungere al commit di feature")
    parser.add_argument("--commit-file", type=Path, help="file col messaggio del commit di feature")
    parser.add_argument("--notes-file", type=Path, required=True, help="file con le note della release")
    args = parser.parse_args()

    if not VERSIONE_RE.match(args.versione):
        print("  uso: python3 ship.py X.Y.Z --add <path...> --commit-file <file> --notes-file <file>",
              file=sys.stderr)
        return 1
    if args.add and not args.commit_file:
        print("  --commit-file è richiesto insieme a --add", file=sys.stderr)
        return 1
    if not args.notes_file.is_file():
        print(f"  --notes-file non trovato: {args.notes_file}", file=sys.stderr)
        return 1

    if commit_feature(args.add, args.commit_file) != 0:
        return 1

    if _run([sys.executable, "release.py", args.versione]) != 0:
        return 1

    tag = f"v{args.versione}"
    passi = [
        ["git", "add", "payload/VERSION", "dist/atlas", "dist/atlas.sha256"],
        ["git", "commit", "-m", f"chore(release): {args.versione}"],
        ["git", "tag", "-a", tag, "-m", f"Atlas {args.versione}"],
        ["git", "push", "origin", "main", "--tags"],
        ["gh", "release", "create", tag, "dist/atlas", "dist/atlas.sha256",
         "--title", f"Atlas {args.versione}", "--notes-file", str(args.notes_file)],
    ]
    for passo in passi:
        if _run(passo) != 0:
            print(f"\n  fallito: {' '.join(passo)}\n", file=sys.stderr)
            return 1

    print(f"\n  spedita {tag}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
