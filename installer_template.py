#!/usr/bin/env python3
"""Atlas __VERSION__ — harness di task a grafo. Installer autoconsistente.

Si copia dentro un progetto e si lancia:

    python3 atlas-install.py --yes --graph epic-primo

Scompatta l'harness in .atlas/, collega le skill sotto .claude/skills/, registra
l'hook di fine sessione senza toccare quelli gia' presenti e appende il contratto
operativo a CLAUDE.md dentro un blocco delimitato. Rilanciarlo aggiorna il motore
e lascia intatti configurazione, grafi e script di mutazione.

Non richiede rete, non installa dipendenze, non crea virtualenv.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import shutil
import sys
import tarfile
from pathlib import Path

VERSION = "__VERSION__"
DIRNAME = ".atlas"
BEGIN, END = "<!-- atlas:begin -->", "<!-- atlas:end -->"
SOSTITUIBILI = ("core", "bin", "hooks", "skills", "templates", "VERSION")
IGNORE = [f"{DIRNAME}/graphs/*/dashboard.html", f"{DIRNAME}/current", "__pycache__/"]

CONFIG = {
    "project": None,
    "agent": {"process_name": "claude", "default_assignee": "claude",
              "idle_hours": 4, "max_claims_per_session": 1},
    "git": {"commit_on_close": False, "commit_type": "feat", "stage": "node-paths"},
    "vocab": {"types": ["grilling", "research", "prototype", "task"],
              "modes": ["HITL", "AFK"],
              "statuses": ["open", "claimed", "closed", "out-of-scope"]},
}

PAYLOAD = """__PAYLOAD__"""


class Installer:
    def __init__(self, target: Path, args):
        self.target, self.args = target, args
        self.root = target / DIRNAME
        self.fatti: list[str] = []

    # --- utilita' ---------------------------------------------------------

    def dice(self, riga: str) -> None:
        self.fatti.append(riga)

    def scrive(self, path: Path, testo: str) -> None:
        if self.args.dry_run:
            self.dice(f"scriverebbe {path.relative_to(self.target)}")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(testo, encoding="utf-8")

    # --- passi ------------------------------------------------------------

    def scompatta(self) -> None:
        blob = base64.b64decode(PAYLOAD)
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
            if self.args.dry_run:
                self.dice(f"scompatterebbe {len(tf.getnames())} file in {DIRNAME}/")
                return
            for voce in SOSTITUIBILI:
                vecchio = self.root / voce
                if vecchio.is_dir():
                    shutil.rmtree(vecchio)
            self.root.mkdir(parents=True, exist_ok=True)
            kw = {"filter": "data"} if sys.version_info >= (3, 12) else {}
            tf.extractall(self.root, **kw)
        (self.root / "bin" / "atlas").chmod(0o755)
        for cartella in ("graphs", "scripts"):
            (self.root / cartella).mkdir(exist_ok=True)
        shutil.copyfile(self.root / "templates" / "contract.md", self.root / "CONTRACT.md")
        self.dice(f"motore in {DIRNAME}/ (versione {VERSION})")

    def configura(self) -> None:
        path = self.root / "config.json"
        if path.is_file():
            self.dice("config.json già presente, lasciato com'era")
            return
        nome = self.target.name if self.args.yes else (
            input(f"  nome del progetto [{self.target.name}]: ").strip() or self.target.name)
        cfg = dict(CONFIG, project=nome)
        self.scrive(path, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
        self.dice(f"config.json creato per '{nome}'")

    def collega_skill(self) -> None:
        dest = self.target / ".claude" / "skills"
        if self.args.dry_run:
            self.dice("collegherebbe le skill in .claude/skills/")
            return
        dest.mkdir(parents=True, exist_ok=True)
        for skill in sorted((self.root / "skills").iterdir()):
            if not skill.is_dir():
                continue
            link = dest / skill.name
            if link.is_symlink() or link.exists():
                if link.is_symlink():
                    link.unlink()
                else:
                    self.dice(f"{link.name} esiste e non è un symlink: lasciato com'è")
                    continue
            link.symlink_to(Path("..") / ".." / DIRNAME / "skills" / skill.name, target_is_directory=True)
        self.dice("skill collegate in .claude/skills/")

    def registra_hook(self) -> None:
        if self.args.no_hooks:
            return
        path = self.target / ".claude" / "settings.json"
        dati = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        comando = f'python3 "$CLAUDE_PROJECT_DIR/{DIRNAME}/hooks/session_end.py"'
        gruppi = dati.setdefault("hooks", {}).setdefault("SessionEnd", [])
        if any(DIRNAME in json.dumps(g) for g in gruppi):
            self.dice("hook SessionEnd già registrato")
            return
        gruppi.append({"hooks": [{"type": "command", "command": comando,
                                  "statusMessage": "Aggiornamento delle dashboard Atlas"}]})
        self.scrive(path, json.dumps(dati, ensure_ascii=False, indent=2) + "\n")
        self.dice("hook SessionEnd registrato, hook preesistenti intatti")

    def contratto(self) -> None:
        if self.args.no_claude_md:
            return
        path = self.target / "CLAUDE.md"
        blocco = f"{BEGIN}\n{(self.root / 'CONTRACT.md').read_text(encoding='utf-8').strip()}\n{END}"
        if path.is_file():
            testo = path.read_text(encoding="utf-8")
            if BEGIN in testo:
                nuovo = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), blocco, testo, flags=re.S)
                self.dice("blocco Atlas in CLAUDE.md aggiornato")
            else:
                nuovo = testo.rstrip() + f"\n\n{blocco}\n"
                self.dice("contratto appeso a CLAUDE.md")
        else:
            nuovo = f"# CLAUDE.md\n\n{blocco}\n"
            self.dice("CLAUDE.md creato col contratto")
        self.scrive(path, nuovo)

    def gitignore(self) -> None:
        path = self.target / ".gitignore"
        testo = path.read_text(encoding="utf-8") if path.is_file() else ""
        mancanti = [r for r in IGNORE if r not in testo]
        if not mancanti:
            return
        coda = "\n".join(mancanti)
        self.scrive(path, f"{testo.rstrip()}\n\n# Atlas: artefatti rigenerabili\n{coda}\n"
                    if testo.strip() else f"# Atlas: artefatti rigenerabili\n{coda}\n")
        self.dice(f".gitignore: aggiunte {len(mancanti)} righe")

    def primo_grafo(self) -> None:
        if not self.args.graph or self.args.dry_run:
            return
        sys.path.insert(0, str(self.root))
        os.environ["ATLAS_ROOT"] = str(self.root)
        from core.cli import main  # noqa: E402
        main(["new", self.args.graph, "-t", self.args.graph.replace("-", " ").capitalize()])

    def disinstalla(self) -> int:
        for voce in SOSTITUIBILI + ("CONTRACT.md",):
            path = self.root / voce
            shutil.rmtree(path) if path.is_dir() else path.unlink(missing_ok=True)
        skills = self.target / ".claude" / "skills"
        for link in skills.glob("atlas-*") if skills.is_dir() else []:
            if link.is_symlink():
                link.unlink()
        impostazioni = self.target / ".claude" / "settings.json"
        if impostazioni.is_file():
            dati = json.loads(impostazioni.read_text(encoding="utf-8"))
            gruppi = dati.get("hooks", {}).get("SessionEnd", [])
            dati["hooks"]["SessionEnd"] = [g for g in gruppi if DIRNAME not in json.dumps(g)]
            impostazioni.write_text(json.dumps(dati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        claude_md = self.target / "CLAUDE.md"
        if claude_md.is_file():
            testo = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", "",
                           claude_md.read_text(encoding="utf-8"), flags=re.S)
            claude_md.write_text(testo.rstrip() + "\n", encoding="utf-8")
        print(f"\n  Motore rimosso. Restano i tuoi dati in {DIRNAME}/: "
              f"graphs/, scripts/, config.json.\n  Cancellali a mano se non ti servono più.\n")
        return 0

    def run(self) -> int:
        if self.args.uninstall:
            return self.disinstalla()
        self.scompatta()
        self.configura()
        self.collega_skill()
        self.registra_hook()
        self.contratto()
        self.gitignore()
        self.primo_grafo()
        print(f"\n  Atlas {VERSION} in {self.target}\n")
        for riga in self.fatti:
            print(f"    · {riga}")
        print(f"\n  Prova con:  {DIRNAME}/bin/atlas doctor")
        if not self.args.graph:
            print(f"  Primo grafo: {DIRNAME}/bin/atlas new <slug> -t \"Titolo\"")
        print()
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"Installa Atlas {VERSION} nel progetto corrente.")
    parser.add_argument("--dir", default=".", help="cartella del progetto (default: quella corrente)")
    parser.add_argument("--yes", action="store_true", help="niente domande, usa i default")
    parser.add_argument("--graph", help="crea subito un grafo con questo slug")
    parser.add_argument("--no-hooks", action="store_true", help="non toccare .claude/settings.json")
    parser.add_argument("--no-claude-md", action="store_true", help="non toccare CLAUDE.md")
    parser.add_argument("--dry-run", action="store_true", help="dice cosa farebbe, senza farlo")
    parser.add_argument("--uninstall", action="store_true", help="rimuove il motore, lascia i dati")
    args = parser.parse_args(argv)

    if sys.version_info < (3, 10):
        print("  Atlas richiede Python 3.10 o superiore.", file=sys.stderr)
        return 1
    try:
        import fcntl  # noqa: F401
    except ImportError:
        print("  Atlas richiede un sistema POSIX: il lock del grafo usa fcntl.", file=sys.stderr)
        return 1

    return Installer(Path(args.dir).resolve(), args).run()


if __name__ == "__main__":
    raise SystemExit(main())
