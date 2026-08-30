"""Che cosa ha toccato una sessione di lavoro, secondo git.

Serve a popolare artifacts alla chiusura di un nodo senza chiedere niente a chi chiude:
un campo che si riempie solo passando un flag resta vuoto, e il controllo di
sconfinamento di doctor resta inerte.
"""
from __future__ import annotations

import subprocess
from datetime import datetime
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


def changed_since(root: Path, artifact_path: str, closed_at: str) -> bool | None:
    """Verifica se un artefatto e' davvero cambiato dopo la chiusura di un nodo,
    guardando il contenuto versionato in git invece dell'mtime del filesystem.

    Restituisce:
    - True se il file e' cambiato (committato dopo closed_at O modifiche non committate)
    - False se il file non e' cambiato rispetto al commit precedente
    - None se non possiamo verificare (repo non git O rev-list non ha trovato un commit)

    Quando restituisce None, il chiamante puo' fallback all'mtime come ultimo ricorso.

    Nota sulla prudenza: quando rev-list non trova niente (repo creata dopo la chiusura,
    o chiusura piu' vecchia del primo commit), restituiamo None perche' non possiamo
    sapere se il file e' stato modificato dopo. L'obiettivo e' togliere falsi positivi,
    non aggiungermi di nuovi: dichiarare "non so" e lasciare decidere al caller e'
    meglio di inventare una risposta errata.
    """
    if not (root / ".git").exists():
        return None

    try:
        datetime.fromisoformat(closed_at)   # solo per rifiutare un closedAt illeggibile
    except (ValueError, TypeError):
        return None

    # Trova il commit piu' recente prima della chiusura.
    # --before usa un formato che git capisce: "before:<ISO-timestamp>"
    commit = _git(root, "rev-list", "-1", f"--before={closed_at}", "HEAD")
    if not commit:
        # Non c'e' un commit prima di closed_at: non possiamo verificare.
        # Restituiamo None per forzare il fallback all'mtime nel caller.
        return None

    base_commit = commit[0]

    # Controlla se l'artefatto compare in git diff fra il commit base e HEAD.
    # Se si', il file e' stato modificato dopo la chiusura.
    diff_risultato = _git(root, "diff", "--name-only", f"{base_commit}...HEAD", "--", artifact_path)
    if diff_risultato and artifact_path in diff_risultato:
        return True

    # Controlla se l'artefatto ha modifiche non committate nel working tree.
    # Questo copre sia i file modificati che gli untracked.
    uncommitted = set(_git(root, "diff", "--name-only", "HEAD"))
    uncommitted.update(_git(root, "ls-files", "--others", "--exclude-standard"))
    if artifact_path in uncommitted:
        return True

    # L'artefatto non e' cambiato.
    return False


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
    return esito.returncode == 0 and artifact_path in esito.stdout.splitlines()


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
