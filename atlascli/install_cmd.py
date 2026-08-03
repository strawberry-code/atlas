"""Installa/disinstalla l'harness Atlas in un progetto ospite.

La classe Installer viene da installer_template.py: stessa logica, un'unica
implementazione. Il payload (tar.gz+base64 di payload/) arriva da _payload.py,
generato da build.py e mai committato.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import shutil
import sys
import tarfile
from pathlib import Path

from . import registry
from .registry import RegistryError
from .strings import set_language, t

DIRNAME = ".atlas"
BEGIN, END = "<!-- atlas:begin -->", "<!-- atlas:end -->"
SOSTITUIBILI = ("core", "bin", "hooks", "skills", "templates", "VERSION")
IGNORE = [f"{DIRNAME}/graphs/*/dashboard.html", f"{DIRNAME}/current", "__pycache__/"]

CONFIG = {
    "project": None,
    "language": "it",
    "agent": {"process_name": "claude", "default_assignee": "claude",
              "idle_hours": 4, "max_claims_per_session": 1},
    "git": {"commit_on_close": False, "commit_type": "feat", "stage": "node-paths"},
    "vocab": {"types": ["grilling", "research", "prototype", "task"],
              "modes": ["HITL", "AFK"],
              "statuses": ["open", "claimed", "closed", "out-of-scope"]},
}


class Installer:
    def __init__(self, target: Path, args, lingua: str = "it"):
        self.target, self.args, self.lingua = target, args, lingua
        self.root = target / DIRNAME
        self.fatti: list[str] = []

    # --- utilita' ---------------------------------------------------------

    def dice(self, riga: str) -> None:
        self.fatti.append(riga)

    def scrive(self, path: Path, testo: str) -> None:
        if self.args.dry_run:
            self.dice(t("install.scriverebbe", path=path.relative_to(self.target)))
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(testo, encoding="utf-8")

    # --- passi ------------------------------------------------------------

    def scompatta(self) -> None:
        from . import _payload
        blob = base64.b64decode(_payload.PAYLOAD_B64)
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
            if self.args.dry_run:
                self.dice(t("install.scompatterebbe", n=len(tf.getnames()), dirname=DIRNAME))
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
        for skill in (self.root / "skills").iterdir():
            if skill.is_dir():
                shutil.copyfile(skill / f"SKILL.{self.lingua}.md", skill / "SKILL.md")
        shutil.copyfile(self.root / "templates" / f"contract.{self.lingua}.md", self.root / "CONTRACT.md")
        versione = (self.root / "VERSION").read_text(encoding="utf-8").strip()
        self.dice(t("install.motore_in", dirname=DIRNAME, versione=versione))

    def configura(self) -> None:
        path = self.root / "config.json"
        if path.is_file():
            self.dice(t("install.config_presente"))
            return
        nome = self.target.name if self.args.yes else (
            input(t("install.nome_progetto", default=self.target.name)).strip() or self.target.name)
        cfg = dict(CONFIG, project=nome, language=self.lingua)
        self.scrive(path, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
        self.dice(t("install.config_creato", nome=nome))

    def imposta_lingua(self) -> None:
        """Patch chirurgica della sola chiave 'language': gira sempre, config.json
        esista gia' o no, a differenza di configura() che si ferma se il file c'e'."""
        if self.args.dry_run:
            return
        path = self.root / "config.json"
        dati = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else dict(CONFIG, project=self.target.name)
        dati["language"] = self.lingua
        path.write_text(json.dumps(dati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def collega_skill(self) -> None:
        dest = self.target / ".claude" / "skills"
        if self.args.dry_run:
            self.dice(t("install.skill_dry_run"))
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
                    self.dice(t("install.skill_non_symlink", nome=link.name))
                    continue
            link.symlink_to(Path("..") / ".." / DIRNAME / "skills" / skill.name, target_is_directory=True)
        self.dice(t("install.skill_collegate"))

    def registra_hook(self) -> None:
        if self.args.no_hooks:
            return
        path = self.target / ".claude" / "settings.json"
        dati = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        comando = f'python3 "$CLAUDE_PROJECT_DIR/{DIRNAME}/hooks/session_end.py"'
        gruppi = dati.setdefault("hooks", {}).setdefault("SessionEnd", [])
        if any(DIRNAME in json.dumps(g) for g in gruppi):
            self.dice(t("install.hook_esiste"))
            return
        gruppi.append({"hooks": [{"type": "command", "command": comando,
                                  "statusMessage": t("install.hook_status")}]})
        self.scrive(path, json.dumps(dati, ensure_ascii=False, indent=2) + "\n")
        self.dice(t("install.hook_registrato"))

    def contratto(self) -> None:
        if self.args.no_claude_md:
            return
        path = self.target / "CLAUDE.md"
        blocco = f"{BEGIN}\n{(self.root / 'CONTRACT.md').read_text(encoding='utf-8').strip()}\n{END}"
        if path.is_file():
            testo = path.read_text(encoding="utf-8")
            if BEGIN in testo:
                nuovo = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), blocco, testo, flags=re.S)
                self.dice(t("install.claude_md_aggiornato"))
            else:
                nuovo = testo.rstrip() + f"\n\n{blocco}\n"
                self.dice(t("install.claude_md_appeso"))
        else:
            nuovo = f"# CLAUDE.md\n\n{blocco}\n"
            self.dice(t("install.claude_md_creato"))
        self.scrive(path, nuovo)

    def gitignore(self) -> None:
        path = self.target / ".gitignore"
        testo = path.read_text(encoding="utf-8") if path.is_file() else ""
        mancanti = [r for r in IGNORE if r not in testo]
        if not mancanti:
            return
        commento = t("install.gitignore_commento")
        coda = "\n".join(mancanti)
        self.scrive(path, f"{testo.rstrip()}\n\n{commento}\n{coda}\n"
                    if testo.strip() else f"{commento}\n{coda}\n")
        self.dice(t("install.gitignore_righe", n=len(mancanti)))

    def primo_grafo(self) -> None:
        if not self.args.graph or self.args.dry_run:
            return
        sys.path.insert(0, str(self.root))
        os.environ["ATLAS_ROOT"] = str(self.root)
        from core.cli import main  # noqa: E402
        main(["new", self.args.graph, "-t", self.args.graph.replace("-", " ").capitalize()])

    def registra_globalmente(self) -> None:
        if self.args.dry_run or getattr(self.args, "no_registry", False):
            return
        try:
            slug = registry.register(self.target, slug=getattr(self.args, "slug", None),
                                      yes=self.args.yes)
        except RegistryError as errore:
            self.dice(t("install.registro_errore", errore=errore))
            return
        if getattr(self.args, "lang", None):
            registry.set_language(self.args.lang, slug=slug)
        self.dice(t("install.registrato", slug=slug))

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
        slug = registry.find_by_path(self.target)
        if slug:
            registry.unregister(slug)
        print(t("install.rimosso", dirname=DIRNAME))
        return 0

    def run(self) -> int:
        self.scompatta()
        self.configura()
        self.imposta_lingua()
        self.collega_skill()
        self.registra_hook()
        self.contratto()
        self.gitignore()
        self.primo_grafo()
        self.registra_globalmente()
        versione = (self.root / "VERSION").read_text(encoding="utf-8").strip() \
            if (self.root / "VERSION").is_file() else "?"
        print(t("install.riepilogo", versione=versione, target=self.target))
        for riga in self.fatti:
            print(f"    · {riga}")
        print(t("install.prova_con", dirname=DIRNAME))
        if not self.args.graph:
            print(t("install.primo_grafo", dirname=DIRNAME))
        print()
        return 0


def cmd_install(args) -> int:
    if sys.version_info < (3, 10):
        print(t("install.python_richiesto"), file=sys.stderr)
        return 1
    try:
        import fcntl  # noqa: F401
    except ImportError:
        print(t("install.posix_richiesto"), file=sys.stderr)
        return 1
    target = Path(args.path).resolve()
    lingua = _lingua_per_install(target, getattr(args, "lang", None))
    set_language(lingua)  # i messaggi di questo comando seguono la lingua risolta per il progetto
    return Installer(target, args, lingua).run()


def _lingua_per_install(target: Path, lang_esplicito: str | None) -> str:
    """Reinstall senza --lang su uno slug gia' noto: rispetta la lingua gia' risolta
    per quello slug, non forza silenziosamente il default globale corrente."""
    if lang_esplicito:
        return lang_esplicito
    slug_esistente = registry.find_by_path(target)
    return registry.language_for(slug_esistente)


def cmd_uninstall(args) -> int:
    target = Path(args.path).resolve()
    set_language(registry.language_for(registry.find_by_path(target)))
    return Installer(target, args).disinstalla()
