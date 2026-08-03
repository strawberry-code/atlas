"""Il registro dei progetti installati: ~/.atlas/registry.json, slug -> path assoluto.

Non duplica stato mutabile del progetto: versione installata e validita' si leggono
sempre dal vivo (status_of, installed_version), mai dalla cache. Il registro sa solo
chi si chiama come e dove sta.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .paths import registry_path

SCHEMA_VERSION = 1
STATO_OK, STATO_MANCANTE, STATO_NON_VALIDO = "ok", "mancante", "non valido"


class RegistryError(Exception):
    """Collisione di slug non risolta, o registrazione annullata dall'utente."""


def slugify(nome: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")
    return slug or "progetto"


def _adesso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load() -> dict:
    path = registry_path()
    if not path.is_file():
        return {"version": SCHEMA_VERSION, "projects": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save(data: dict) -> None:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _per_path(projects: dict, resolto: str) -> str | None:
    for slug, voce in projects.items():
        if voce["path"] == resolto:
            return slug
    return None


def register(path: Path, slug: str | None = None, *, yes: bool = False,
             chiedi: Callable[[str], str] = input) -> str:
    """Registra path sotto slug (default: nome cartella). Ritorna lo slug usato.

    Path gia' registrato altrove e slug non forzato esplicitamente -> riusa quella
    voce invece di duplicarla. Slug gia' occupato da un path diverso -> mai
    sovrascrittura silenziosa: prompt in interattivo, errore con --yes.
    """
    resolto = str(Path(path).resolve())
    data = load()
    projects = data["projects"]

    if slug is None:
        esistente = _per_path(projects, resolto)
        if esistente:
            projects[esistente]["last_seen"] = _adesso()
            save(data)
            return esistente
        slug = slugify(Path(resolto).name)

    attuale = projects.get(slug)
    if attuale and attuale["path"] != resolto:
        if yes:
            raise RegistryError(
                f"'{slug}' è già registrato per {attuale['path']}: usa --slug per un nome diverso")
        risposta = chiedi(f"  '{slug}' è già registrato per {attuale['path']}. "
                           f"Sovrascrivere con {resolto}? [y/N] ").strip().lower()
        if risposta != "y":
            raise RegistryError("registrazione annullata")

    projects[slug] = {
        "path": resolto,
        "registered_at": attuale["registered_at"] if attuale else _adesso(),
        "last_seen": _adesso(),
    }
    save(data)
    return slug


def resolve(slug: str) -> Path | None:
    voce = load()["projects"].get(slug)
    return Path(voce["path"]) if voce else None


def find_by_path(path: Path) -> str | None:
    return _per_path(load()["projects"], str(Path(path).resolve()))


def repoint(slug: str, path: Path) -> None:
    """Ripunta uno slug gia' registrato su un path diverso, senza chiedere conferma:

    chi scrive 'atlas <slug> update <path>' ha gia' dichiarato l'intento esplicito.
    """
    data = load()
    resolto = str(Path(path).resolve())
    esistente = data["projects"].get(slug)
    data["projects"][slug] = {
        "path": resolto,
        "registered_at": esistente["registered_at"] if esistente else _adesso(),
        "last_seen": _adesso(),
    }
    save(data)


def unregister(slug: str) -> bool:
    data = load()
    if slug not in data["projects"]:
        return False
    del data["projects"][slug]
    save(data)
    return True


def status_of(path: Path) -> str:
    if not path.is_dir():
        return STATO_MANCANTE
    if not (path / ".atlas" / "core").is_dir():
        return STATO_NON_VALIDO
    return STATO_OK


def installed_version(path: Path) -> str | None:
    version_file = path / ".atlas" / "VERSION"
    return version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else None


def prune() -> list[str]:
    """Rimuove le voci il cui path e' mancante o non valido. Ritorna gli slug tolti."""
    data = load()
    tolti = [slug for slug, voce in data["projects"].items()
             if status_of(Path(voce["path"])) != STATO_OK]
    for slug in tolti:
        del data["projects"][slug]
    if tolti:
        save(data)
    return tolti
