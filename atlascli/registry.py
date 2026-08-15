"""Il registro dei progetti installati: ~/.config/atlas.json, slug -> path assoluto.

Non duplica stato mutabile del progetto: versione installata e validita' si leggono
sempre dal vivo (status_of), mai dalla cache. Il registro sa solo
chi si chiama come e dove sta.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .errori import leggi_json
from .paths import config_path, progetto_valido
from .strings import t
from .version import current_version

SCHEMA_VERSION = 2
STATO_OK, STATO_MANCANTE, STATO_NON_VALIDO = "ok", "mancante", "non valido"
LINGUE = ("it", "en")


class RegistryError(Exception):
    """Collisione di slug non risolta, o registrazione annullata dall'utente."""


def slugify(nome: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")
    return slug or "progetto"


def _adesso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load() -> dict:
    path = config_path()
    if not path.is_file():
        return {"version": SCHEMA_VERSION, "language": "it", "projects": {}}
    # Il registro si legge all'avvio di quasi ogni comando, anche di quelli che col
    # registro non c'entrano: un traceback qui murerebbe il CLI su tutta la macchina,
    # non un progetto solo.
    dati = leggi_json(path, "errore.registro_rotto")
    dati.setdefault("language", "it")
    dati.setdefault("projects", {})
    return dati


def save(data: dict) -> None:
    """Scrittura atomica del registro: temporaneo accanto, poi scambio.

    Il registro elenca tutti i progetti Atlas della macchina, e lo riscrive anche
    il controllo automatico degli aggiornamenti in coda a ogni comando. Con una
    write_text diretta un processo ucciso a meta' lasciava un JSON troncato, e da
    li' in poi install, list, lang e uninstall fallivano tutti insieme. Lo scambio
    con os.replace e' atomico sullo stesso filesystem, quindi o si legge il registro
    di prima o quello di dopo, mai un file a meta'.
    """
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    testo = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                      prefix=f".{path.name}.", delete=False)
    try:
        with tmp:
            tmp.write(testo)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp.name, path)
    except BaseException:
        Path(tmp.name).unlink(missing_ok=True)
        raise


def aggiorna_cache(campi: dict) -> None:
    """Scrive solo questi campi radice, rileggendo il registro all'ultimo momento.

    La cache del controllo aggiornamenti si salva dopo una chiamata di rete che
    puo' durare quindici secondi. Risalvare la copia letta prima della chiamata
    riportava indietro tutto cio' che nel frattempo avevano scritto gli altri
    comandi: un 'atlas install' lanciato in un'altra shell spariva dal registro
    senza un errore da nessuna delle due parti. Qui si rilegge e si tocca solo
    quel che ci riguarda, quindi l'unica cosa che si puo' perdere e' la cache.
    """
    data = load()
    data.update(campi)
    save(data)


def language_for(slug: str | None = None) -> str:
    """Override per-progetto se c'e', altrimenti il default globale, altrimenti 'it'."""
    data = load()
    if slug:
        voce = data["projects"].get(slug, {})
        if "language" in voce:
            return voce["language"]
    return data.get("language", "it")


def set_language(lingua: str, slug: str | None = None) -> None:
    """Senza slug cambia il default globale; con slug l'override di quel progetto.

    Lo slug deve gia' essere registrato: un override senza 'path' corromperebbe lo schema.
    """
    data = load()
    if slug is None:
        data["language"] = lingua
    else:
        if slug not in data["projects"]:
            raise RegistryError(t("registry.slug_senza_progetto", slug=slug))
        data["projects"][slug]["language"] = lingua
    save(data)


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

    Si annota anche con quale versione il progetto e' stato installato: e' cio' che
    permette a 'atlas update' di sapere chi e' rimasto indietro quando l'eseguibile
    e' gia' all'ultima versione e non c'e' nessun download da cui dedurlo. Non e'
    stato mutabile duplicato dal progetto: lo scrive chi installa, nel momento in
    cui installa, ed e' l'unico che lo sa.
    """
    resolto = str(Path(path).resolve())
    data = load()
    projects = data["projects"]

    if slug is None:
        esistente = _per_path(projects, resolto)
        if esistente:
            projects[esistente]["last_seen"] = _adesso()
            projects[esistente]["version"] = current_version()
            save(data)
            return esistente
        slug = slugify(Path(resolto).name)

    attuale = projects.get(slug)
    if attuale and attuale["path"] != resolto:
        if yes:
            raise RegistryError(t("registry.slug_occupato", slug=slug, path=attuale["path"]))
        risposta = chiedi(t("registry.conferma_prompt", slug=slug,
                            path=attuale["path"], nuovo=resolto)).strip().lower()
        if risposta != "y":
            raise RegistryError(t("registry.annullata"))

    projects[slug] = {
        "path": resolto,
        "registered_at": attuale["registered_at"] if attuale else _adesso(),
        "last_seen": _adesso(),
        "version": current_version(),
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
    Si cambia il path e si tiene il resto della voce: ricostruirla da zero buttava
    via l'override di lingua del progetto, e adesso butterebbe anche la versione
    con cui e' installato. Spostare una cartella non cambia nessuna delle due.
    """
    data = load()
    voce = dict(data["projects"].get(slug) or {})
    voce["path"] = str(Path(path).resolve())
    voce.setdefault("registered_at", _adesso())
    voce["last_seen"] = _adesso()
    data["projects"][slug] = voce
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
    if not progetto_valido(path):
        return STATO_NON_VALIDO
    return STATO_OK


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
