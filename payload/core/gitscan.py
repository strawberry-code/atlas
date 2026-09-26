"""Che cosa ha toccato una sessione di lavoro, secondo git.

Serve a popolare artifacts alla chiusura di un nodo senza chiedere niente a chi chiude:
un campo che si riempie solo passando un flag resta vuoto, e il controllo di
sconfinamento di doctor resta inerte.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from functools import lru_cache
from pathlib import Path

ESCLUSI = (".atlas/",)


def _git(root: Path, *argomenti: str) -> list[str]:
    esito = subprocess.run(["git", *argomenti], cwd=root, capture_output=True, text=True)
    return esito.stdout.splitlines() if esito.returncode == 0 else []


def touched(root: Path, since: str | None = None) -> list[str]:
    """I file del progetto modificati o creati e non ancora committati, esclusi quelli
    dell'harness. Con since (timestamp ISO) tiene solo quelli toccati da allora in poi.

    Il commit di chiusura arriva dopo close, quindi qui il lavoro del nodo e' ancora
    tutto nel working tree: e' il momento giusto per fotografarlo.
    """
    if not (root / ".git").exists():
        return []
    candidati = (set(_git(root, "diff", "--name-only", "HEAD"))
                 | set(_git(root, "ls-files", "--others", "--exclude-standard")))
    soglia = datetime.fromisoformat(since) if since else None
    tenuti = []
    for percorso in candidati:
        if not percorso or percorso.startswith(ESCLUSI):
            continue
        file = root / percorso
        if not file.is_file():
            continue
        if soglia and datetime.fromtimestamp(file.stat().st_mtime).astimezone() < soglia:
            continue
        tenuti.append(percorso)
    return sorted(tenuti)


def closing_commit(root: Path, graph_path: str, node_id: str, closed_at: str,
                   limite: int = 20) -> str | None:
    """Il primo commit dopo closed_at in cui graph_path registra la chiusura del nodo.

    Il contratto vuole close prima del commit: il commit che porta il lavoro del nodo
    arriva dopo closedAt. Misurare le scritture postume dall'ultimo commit prima della
    chiusura conterebbe quel commit come una scrittura postuma, su ogni nodo chiuso.
    La base giusta e' il commit che contiene la chiusura. None se non lo trova entro
    limite commit (chiusura mai committata, grafo riscritto): il chiamante ripiega.
    """
    if not (root / ".git").exists():
        return None
    for commit in _git(root, "log", "--reverse", "--format=%H", f"--since={closed_at}",
                       "--", graph_path)[:limite]:
        if _chiusure(root, commit, graph_path).get(node_id) == closed_at:
            return commit
    return None


@lru_cache(maxsize=256)
def _chiusure(root: Path, commit: str, graph_path: str) -> dict:
    """id -> closedAt del grafo in quel commit. In cache perche' doctor interroga
    gli stessi pochi commit per ogni nodo chiuso: senza, rilegge il grafo N volte."""
    esito = subprocess.run(["git", "show", f"{commit}:{graph_path}"], cwd=root,
                           capture_output=True, text=True)
    try:
        nodi = json.loads(esito.stdout)["nodes"] if esito.returncode == 0 else []
        return {n["id"]: n.get("closedAt") for n in nodi if isinstance(n, dict) and "id" in n}
    except (ValueError, KeyError, TypeError):
        return {}


def non_committati(root: Path) -> set[str]:
    """I file modificati o untracked nel working tree. Non dipende dall'artefatto:
    doctor lo calcola una volta per esecuzione, non una per artefatto (issue #35,
    su 642 artefatti erano due processi git ciascuno e 30 s di attesa)."""
    if not (root / ".git").exists():
        return set()
    return set(_git(root, "diff", "--name-only", "HEAD")) | set(
        _git(root, "ls-files", "--others", "--exclude-standard"))


def postumi(root: Path, closed_at: str, base: str | None = None) -> set[str] | None:
    """I file committati dopo la chiusura di un nodo: uno 'git diff' per nodo invece
    che uno per artefatto.

    base, se data, e' il commit di chiusura (closing_commit). Altrimenti si ripiega sul
    commit piu' recente prima della chiusura, che pero' conta come postumo anche il
    commit del lavoro del nodo stesso.

    None se non si puo' verificare (repo non git, closedAt illeggibile, nessun commit
    prima della chiusura): dichiarare "non so" e lasciare al chiamante il ripiego
    sull'mtime e' meglio di inventare una risposta, perche' l'obiettivo e' togliere
    falsi positivi, non aggiungerne.
    """
    if not (root / ".git").exists():
        return None
    try:
        datetime.fromisoformat(closed_at)   # solo per rifiutare un closedAt illeggibile
    except (ValueError, TypeError):
        return None
    commit = [base] if base else _git(root, "rev-list", "-1", f"--before={closed_at}", "HEAD")
    if not commit:
        return None
    return set(_git(root, "diff", "--name-only", f"{commit[0]}...HEAD"))


def contiene(percorsi: set[str], artifact_path: str) -> bool:
    """L'artefatto e' fra i percorsi, o ne e' una cartella che ne contiene qualcuno."""
    cartella = artifact_path.rstrip("/") + "/"
    return artifact_path in percorsi or any(p.startswith(cartella) for p in percorsi)


def changed_since(root: Path, artifact_path: str, closed_at: str,
                  base: str | None = None) -> bool | None:
    """Se un artefatto (file o cartella) e' cambiato dopo la chiusura del nodo,
    secondo git: committato dopo la base o sporco nel working tree. None se non si
    puo' verificare (vedi postumi). Per molti artefatti doctor usa direttamente
    postumi e non_committati, calcolati una volta sola."""
    cambiati = postumi(root, closed_at, base)
    if cambiati is None:
        return None
    return contiene(cambiati, artifact_path) or contiene(non_committati(root), artifact_path)


def indice(root: Path) -> set[str] | None:
    """Tutti i file nell'indice git, None fuori da una repo. Per doctor, che altrimenti
    lancerebbe un 'git ls-files' per ogni artefatto di ogni nodo chiuso."""
    if not (root / ".git").exists():
        return None
    try:
        esito = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True)
    except OSError:
        return None
    return set(esito.stdout.splitlines()) if esito.returncode == 0 else None


def tracked(root: Path, artifact_path: str) -> bool | None:
    """Dice se *artifact_path* e' nell'indice git della repo, se possibile.

    ``False`` significa che Git conosce la repo ma non quel file; ``None`` significa
    che il controllo non e' applicabile, perche' il progetto non e' una repo Git o il
    comando non si puo' eseguire. Distinguere i due casi permette a doctor di non
    scambiare un progetto non versionato per un artefatto smarrito.
    """
    if not (root / ".git").exists():
        return None
    try:
        esito = subprocess.run(["git", "ls-files", "--error-unmatch", "--", artifact_path],
                               cwd=root, capture_output=True, text=True)
    except OSError:
        return None
    righe = esito.stdout.splitlines()
    if (root / artifact_path).is_dir():
        return esito.returncode == 0 and bool(righe)   # cartella: tracciata se ha file nell'indice
    return esito.returncode == 0 and artifact_path in righe


def move(root: Path, src: Path, dst: Path) -> bool:
    """Rinomina con 'git mv' se il file e' tracciato, torna False se git non se ne occupa.

    git mv fallisce da solo su un file non tracciato, ma anche qui serve un False
    silenzioso: il chiamante ripiega su un rename normale, e un comando non deve mai
    morire per un motivo che non dipende dal progetto.
    """
    if not (root / ".git").exists():
        return False
    try:
        esito = subprocess.run(["git", "mv", str(src), str(dst)],
                               cwd=root, capture_output=True, text=True)
    except OSError:
        return False
    return esito.returncode == 0
