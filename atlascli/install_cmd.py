"""Installa/disinstalla Atlas in un progetto ospite.

Installare vuol dire scrivere i dati e i documenti del progetto, mai il motore:
dalla 0.7 quello vive nell'eseguibile. Le skill arrivano dal blob di _payload.py
(generato da build.py, mai committato) perche' devono stare su disco per essere
raggiunte dai symlink di .claude/skills/; contratto e README nascono dai template
che viaggiano nel pacchetto.
"""
from __future__ import annotations

import base64
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tarfile
from pathlib import Path

from . import hook, registry
from .errori import ErroreAtlas, leggi_json
from .registry import RegistryError
from .progetto import template
from .strings import set_language, t
from .version import current_version

DIRNAME = ".atlas"
MARCATORE = ".atlas-managed"  # dentro una copia di skill (fallback Windows al posto del simlink)
BEGIN, END = "<!-- atlas:begin -->", "<!-- atlas:end -->"
SOSTITUIBILI = ("skills",)
# Quel che le versioni precedenti scrivevano dentro il progetto e che ora vive
# nell'eseguibile: sorgenti del motore (0.5 e prima), archivio unico (0.6), template
# e hook. Restano li' finche' qualcuno non li toglie, e un progetto con due motori
# addosso e' lo stato peggiore: l'installazione li porta via e dice quali.
RESIDUI = ("core", "bin", "atlas", "templates", "hooks", "VERSION")
# Il lock e il temporaneo della scrittura atomica sono meccanica del motore, non dati:
# il primo esiste solo per essere bloccato, il secondo sopravvive a un processo ucciso
# a meta' e sparisce alla scrittura dopo. Versionarli sporcherebbe ogni diff.
IGNORE = [f"{DIRNAME}/graphs/*/dashboard.html", f"{DIRNAME}/graphs/*/graph.json.lock",
          f"{DIRNAME}/graphs/*/.graph.json.tmp", f"{DIRNAME}/current",
          # Chi lavora da questa copia: stato locale come 'current'. Versionarlo
          # farebbe ereditare a chi clona il nome dell'ultimo che l'ha scritto.
          f"{DIRNAME}/whoami", "__pycache__/"]

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

# Il merge driver per i graph.json: git chiama 'atlas merge-graph' quando deve
# unire un grafo (%O antenato, %A nostro, %B loro). Il nome del driver deve
# combaciare nei due punti: l'attributo in .gitattributes e la voce nel config
# git. Chi usa il progetto ha atlas su PATH: qui si scrive la config, non si
# verifica che il comando esista.
MERGE_DRIVER = "atlas-graph"
MERGE_COMANDO = "atlas merge-graph %O %A %B"
ATTRIBUTI_MERGE = f".atlas/graphs/*/graph.json merge={MERGE_DRIVER}"


def _gitdir_da_file(punto: Path) -> Path | None:
    """La gitdir scritta in un .git che e' un file (worktree o submodule)."""
    testo = punto.read_text(encoding="utf-8").strip()
    if not testo.startswith("gitdir:"):
        return None
    return (punto.parent / testo.split(":", 1)[1].strip()).resolve()


def config_gia_registrato(testo: str) -> bool:
    """Vero se il config git ha gia' il driver sotto [merge \"atlas-graph\"]."""
    sezione = None
    for riga in testo.splitlines():
        riga = riga.strip()
        if riga.startswith("[") and riga.endswith("]"):
            sezione = riga[1:-1].strip().replace('"', "").strip()
        elif sezione == "merge atlas-graph" and riga.startswith("driver"):
            return True
    return False


def config_con_driver(testo: str) -> str:
    """Il config git con la sezione del driver aggiunta in coda."""
    blocco = f'\n[merge "{MERGE_DRIVER}"]\n\tdriver = {MERGE_COMANDO}\n'
    return testo.rstrip() + blocco if testo.strip() else blocco.lstrip("\n")


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
            try:
                rel = path.relative_to(self.target)
            except ValueError:
                rel = path  # fuori dal progetto: e' il config comune di una worktree
            self.dice(t("install.scriverebbe", path=rel))
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(testo, encoding="utf-8")

    # --- passi ------------------------------------------------------------

    def scompatta(self) -> None:
        """Scrive dentro il progetto quel che deve stare su disco: le skill e i documenti.

        Dalla 0.7 il motore non ci finisce piu': vive nell'eseguibile atlas e basta.
        Qui restano le skill, che Claude Code legge da .claude/skills/ via symlink, e
        i due documenti generati, CONTRACT.md e README.md.
        """
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
        self.sgombera()
        for cartella in ("graphs", "scripts"):
            (self.root / cartella).mkdir(exist_ok=True)
        esempio = self.root / "scripts" / "000-promote-fog.py"
        if not esempio.is_file():          # scripts/ e' territorio dell'utente: mai sovrascriverlo
            self.scrive(esempio, template(f"promote-fog.{self.lingua}.py.tmpl"))
        self.scrive_documenti()
        self.dice(t("install.motore_in", dirname=DIRNAME, versione=current_version()))

    def scrive_documenti(self) -> None:
        """SKILL.md nella lingua scelta, il contratto e il README della cartella."""
        # Le skill possono non esserci: uninstall le porta via e lascia config.json,
        # che e' la firma del progetto. Da quello stato un 'atlas lang' moriva su
        # iterdir() con un FileNotFoundError nudo, invece di rifare i documenti.
        skills = self.root / "skills"
        for skill in (skills.iterdir() if skills.is_dir() else ()):
            if skill.is_dir():
                shutil.copyfile(skill / f"SKILL.{self.lingua}.md", skill / "SKILL.md")
        self.scrive(self.root / "CONTRACT.md", template(f"contract.{self.lingua}.md"))
        self.scrive(self.root / "README.md", template(f"readme.{self.lingua}.md"))

    def sgombera(self) -> None:
        """Porta via il motore delle versioni precedenti, che ora non abita piu' qui."""
        tolti = []
        for voce in RESIDUI:
            vecchio = self.root / voce
            if vecchio.is_dir():
                shutil.rmtree(vecchio)
                tolti.append(f"{DIRNAME}/{voce}/")
            elif vecchio.is_file():
                vecchio.unlink()
                tolti.append(f"{DIRNAME}/{voce}")
        for cache in self.root.rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)
        if tolti:
            self.dice(t("install.residui_rimossi", elenco=", ".join(tolti)))

    def _nome_chiesto(self) -> str:
        """Il nome del progetto chiesto a chi installa, o la diagnosi se non c'e' nessuno.

        Senza un terminale la domanda non ha risposta possibile, e input() usciva come
        EOFError nudo: succedeva a chiunque lanciasse install da uno script, da una CI
        o da un agente, cioe' i chiamanti per cui l'harness esiste.
        """
        try:
            risposta = input(t("install.nome_progetto", default=self.target.name))
        except EOFError:
            raise ErroreAtlas(t("install.stdin_muto")) from None
        return risposta.strip() or self.target.name

    def configura(self) -> None:
        path = self.root / "config.json"
        if path.is_file():
            self.dice(t("install.config_presente"))
            return
        nome = self.target.name if self.args.yes else self._nome_chiesto()
        # E01: nasce qui, non lazy, cosi' la primissima copia versionata del
        # progetto porta gia' il codice opaco che il relay usa per instradare
        # l'avviso 'qualcosa e' cambiato' (docs/atlas-relay-design.md SS11-bis).
        from core.project_code import genera
        cfg = dict(CONFIG, project=nome, language=self.lingua, projectCode=genera())
        self.scrive(path, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
        self.dice(t("install.config_creato", nome=nome))

    def imposta_lingua(self) -> None:
        """Patch chirurgica della sola chiave 'language': gira sempre, config.json
        esista gia' o no, a differenza di configura() che si ferma se il file c'e'."""
        if self.args.dry_run:
            return
        path = self.root / "config.json"
        dati = leggi_json(path) if path.is_file() else dict(CONFIG, project=self.target.name)
        dati["language"] = self.lingua
        path.write_text(json.dumps(dati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def collega_skill(self) -> None:
        """Symlink verso .atlas/skills/<nome>: su Windows senza admin/developer mode
        symlink_to fallisce, e si copia la cartella invece. MARCATORE distingue la
        nostra copia (si rigenera a ogni update) da una cartella messa li' da altri
        (si segnala e si lascia stare, come per un simlink sostituito a mano)."""
        dest = self.target / ".claude" / "skills"
        if self.args.dry_run:
            self.dice(t("install.skill_dry_run"))
            return
        dest.mkdir(parents=True, exist_ok=True)
        for skill in sorted((self.root / "skills").iterdir()):
            if not skill.is_dir():
                continue
            link = dest / skill.name
            if link.is_symlink():
                link.unlink()
            elif link.is_dir() and (link / MARCATORE).is_file():
                shutil.rmtree(link)
            elif link.exists():
                self.dice(t("install.skill_non_symlink", nome=link.name))
                continue
            try:
                link.symlink_to(Path("..") / ".." / DIRNAME / "skills" / skill.name, target_is_directory=True)
            except OSError:
                shutil.copytree(skill, link)
                (link / MARCATORE).write_text("", encoding="utf-8")
        self.dice(t("install.skill_collegate"))

    def registra_hook(self) -> None:
        if self.args.no_hooks:
            return
        path = self.target / ".claude" / "settings.json"
        dati = leggi_json(path, "errore.settings_rotto") if path.is_file() else {}
        gruppi = dati.setdefault("hooks", {}).setdefault("SessionEnd", [])
        aggiornato = hook.elenco_aggiornato(gruppi, t("install.hook_status"))
        if gruppi == aggiornato:
            self.dice(t("install.hook_esiste"))
            return
        dati["hooks"]["SessionEnd"] = aggiornato
        self.scrive(path, json.dumps(dati, ensure_ascii=False, indent=2) + "\n")
        self.dice(t("install.hook_registrato"))

    def contratto(self) -> None:
        if self.args.no_claude_md:
            return
        path = self.target / "CLAUDE.md"
        # Il contratto si prende dal template, non da .atlas/CONTRACT.md appena scritto:
        # sono lo stesso testo, ma sotto --dry-run quel file non viene scritto affatto e
        # rileggerlo faceva morire l'anteprima con un FileNotFoundError, cioe' proprio
        # nel modo in cui si controlla un'installazione prima di farla.
        blocco = f"{BEGIN}\n{template(f'contract.{self.lingua}.md').strip()}\n{END}"
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

    def _config_git(self) -> Path | None:
        """Il file config della repo del progetto, o None se non e' una repo.

        .git e' una cartella (repo normale) o un file con 'gitdir: <path>'
        (worktree o submodule). Per i worktree il config vero sta nel commondir,
        che il file commondir dentro la gitdir indica rispetto alla gitdir stessa.
        """
        punto = self.target / ".git"
        if punto.is_dir():
            return punto / "config"
        if punto.is_file():
            gitdir = _gitdir_da_file(punto)
            if gitdir is None:
                return None
            commondir = gitdir / "commondir"
            if commondir.is_file():
                base = (gitdir / commondir.read_text(encoding="utf-8").strip()).resolve()
                return base / "config"
            return gitdir / "config"
        return None

    def registra_merge_driver(self) -> None:
        """Registra il merge driver git per i graph.json, se il progetto e' una repo.

        Due scritture: la riga in .gitattributes (radice del working tree) e la
        voce nel config git locale. Progetto senza .git: niente da registrare, e
        non e' un errore. Se la registrazione c'e' gia', non si riscrive a vuoto.
        """
        config_path = self._config_git()
        if config_path is None:
            return
        attributi = self.target / ".gitattributes"
        testo_config = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
        testo_attr = attributi.read_text(encoding="utf-8") if attributi.is_file() else ""
        scritto = False

        if ATTRIBUTI_MERGE not in testo_attr:
            commento = t("install.merge_driver_commento")
            coda = (f"{testo_attr.rstrip()}\n\n{commento}\n{ATTRIBUTI_MERGE}\n"
                    if testo_attr.strip() else f"{commento}\n{ATTRIBUTI_MERGE}\n")
            self.scrive(attributi, coda)
            scritto = True
        if not config_gia_registrato(testo_config):
            self.scrive(config_path, config_con_driver(testo_config))
            scritto = True
        if scritto:
            chiave = "install.merge_driver_dry_run" if self.args.dry_run else "install.merge_driver_ok"
            self.dice(t(chiave))

    def primo_grafo(self) -> None:
        if not self.args.graph or self.args.dry_run:
            return
        # Niente sys.path: il motore e' questo stesso programma. ATLAS_ROOT serve
        # perche' la cwd puo' essere altrove quando si installa su un path esplicito.
        os.environ["ATLAS_ROOT"] = str(self.root)
        from core.cli import main
        main(["new", self.args.graph, "-t", self.args.graph.replace("-", " ").capitalize()])

    def rifa_dashboard(self) -> None:
        """Rigenera le dashboard dei grafi che il progetto ha gia'.

        La pagina e' un artefatto derivato e nessun altro passo dell'installazione
        la tocca: senza questo, una versione che cambia il rendering non arriverebbe
        mai nei progetti col grafo fermo, e chi la riapre dopo un update riuscito
        vede quella di prima e conclude che l'update non ha funzionato.

        Un grafo malato non deve pero' far fallire l'installazione, che a quel punto
        e' gia' andata a buon fine: si dice cosa e' successo e la dashboard si rifara'
        al primo comando che tocca quel grafo.
        """
        if self.args.dry_run:
            return
        grafi = self.root / "graphs"
        slugs = [d.name for d in sorted(grafi.iterdir()) if (d / "graph.json").is_file()] \
            if grafi.is_dir() else []
        if not slugs:
            return
        os.environ["ATLAS_ROOT"] = str(self.root)
        from core.cli import main
        # Quel che il motore stampa finisce qui: l'unica voce che esce e' quella
        # dell'installazione, e se qualcosa e' andato storto il motivo lo riporta lei.
        detto = io.StringIO()
        try:
            with contextlib.redirect_stdout(detto), contextlib.redirect_stderr(detto):
                fallito = main(["render", "--all"]) != 0
            motivo = next((r.strip() for r in detto.getvalue().splitlines() if r.strip()), "?") \
                if fallito else None
        except Exception as errore:  # noqa: BLE001 - un grafo illeggibile arriva fin qui
            motivo = str(errore)
        if motivo:
            self.dice(t("install.dashboard_errore", errore=motivo))
            return
        self.dice(t("install.dashboard_rifatte", n=len(slugs)))

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
        # RESIDUI compresi: chi disinstalla da una versione precedente non deve
        # restare con mezzo motore sul disco.
        for voce in SOSTITUIBILI + RESIDUI + ("CONTRACT.md", "README.md"):
            path = self.root / voce
            shutil.rmtree(path) if path.is_dir() else path.unlink(missing_ok=True)
        skills = self.target / ".claude" / "skills"
        for link in skills.glob("atlas-*") if skills.is_dir() else []:
            if link.is_symlink():
                link.unlink()
            elif link.is_dir() and (link / MARCATORE).is_file():
                shutil.rmtree(link)
        hook.sgancia(self.target / ".claude" / "settings.json")
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
        self.registra_merge_driver()
        self.primo_grafo()
        self.rifa_dashboard()
        self.registra_globalmente()
        print(t("install.riepilogo", versione=current_version(), target=self.target))
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
