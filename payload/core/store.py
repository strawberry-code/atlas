"""Unico proprietario in scrittura di graph.json: nessun altro modulo lo apre in scrittura.

Il ciclo leggi-modifica-scrivi passa sempre da transaction(), che tiene un lock
esclusivo per tutta la durata: due sessioni che scrivono insieme si serializzano
invece di sovrascriversi a vicenda. Il lock vive su un file dedicato accanto al
grafo, perche' il grafo viene sostituito con os.replace e un lock preso sul suo
descrittore proteggerebbe un inode che nel frattempo non e' piu' quello buono.
"""
from __future__ import annotations

import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path

from .config import ConfigError
from .strings import t

SCHEMA_VERSION = 1
# Quando SCHEMA_VERSION cambia, la lettura migrera' automaticamente i dati senza
# flag per restare sul formato vecchio. Il grafo e' versionato in git (reversibile);
# chi lo consuma non vede mai il JSON grezzo, solo la struttura in memoria.
OPEN, CLAIMED, CLOSED, DROPPED = "open", "claimed", "closed", "out-of-scope"

if sys.platform == "win32":
    import msvcrt

    def _lock(fh) -> None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)

    def _unlock(fh) -> None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock(fh) -> None:
        fcntl.flock(fh, fcntl.LOCK_EX)

    def _unlock(fh) -> None:
        fcntl.flock(fh, fcntl.LOCK_UN)

# json.dumps con indent espande ogni array su piu' righe: qui gli array sono liste
# corte di id ("blockedBy") e riespanderli renderebbe illeggibile il diff di un claim.
_STR_ARRAY = re.compile(r'\[\s+((?:"(?:[^"\\]|\\.)*",?\s*)+)\]')


class StateError(Exception):
    """Violazione del protocollo: il chiamante la mostra e si ferma."""


def dumps(graph: dict) -> str:
    text = json.dumps(graph, ensure_ascii=False, indent=2)
    return _STR_ARRAY.sub(lambda m: "[" + " ".join(m.group(1).split()) + "]", text) + "\n"


def _decodifica(path: Path, testo: str) -> dict:
    """Il grafo, o un ConfigError che dice quale file e' rotto e come.

    Il grafo e' l'unica fonte di verita' del progetto e lo riscrivono anche gli
    script degli agenti: puo' arrivare troncato o non essere affatto un grafo, e
    in tutti e due i casi il chiamante deve poterlo dire invece di morire.
    """
    try:
        graph = json.loads(testo)
    except json.JSONDecodeError as errore:
        raise ConfigError(t("store.grafo_rotto", path=path, dettaglio=errore)) from errore
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
        raise ConfigError(t("store.grafo_senza_nodi", path=path))
    return graph


def load(path: Path) -> dict:
    return _decodifica(path, path.read_text(encoding="utf-8"))


def _path_lock(path: Path) -> Path:
    return path.with_name(path.name + ".lock")


@contextmanager
def _sotto_lock(path: Path):
    """Serializza sul file di lock, che esiste solo per essere bloccato.

    Non viene mai rinominato ne' cancellato: cancellarlo aprirebbe la finestra in cui
    due processi bloccano due inode diversi credendo di escludersi. Il lucchetto lo
    rilascia il kernel alla morte del processo, quindi un lock rimasto appeso non e'
    un caso da gestire.
    """
    lock = _path_lock(path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    if not lock.exists():
        # Un byte per avere qualcosa da bloccare: msvcrt.locking lavora su un intervallo
        # a partire dalla posizione corrente, e su un file vuoto quel byte non c'e'.
        lock.write_bytes(b"\0")
    with lock.open("r+b") as fh:
        _lock(fh)
        try:
            yield
        finally:
            _unlock(fh)


def _sincronizza_cartella(cartella: Path) -> None:
    """Rende durevole il rename, non solo il contenuto del file rinominato.

    Su Windows non si fa, perche' una directory non si apre come file. Un fallimento
    qui non e' un fallimento della mutazione: il replace e' gia' avvenuto e il grafo
    sul disco e' quello nuovo, manca solo la garanzia contro un blackout immediato.
    """
    if sys.platform == "win32":
        return
    try:
        fd = os.open(cartella, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _scrivi_atomico(path: Path, testo: str) -> None:
    """Sostituisce il grafo in un colpo solo: chi legge vede il vecchio o il nuovo.

    Riscrivere il file vivo (seek, write, truncate) lascia una finestra in cui un
    processo ucciso a meta' lascia sul disco un grafo troncato, oppure un grafo
    valido che contiene uno stato mai esistito, che e' il caso peggiore perche'
    supera la validazione. Il temporaneo sta nella stessa cartella perche'
    os.replace e' atomico solo all'interno dello stesso filesystem.
    """
    tmp = path.with_name("." + path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(testo)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    _sincronizza_cartella(path.parent)


def write_new(path: Path, graph: dict) -> None:
    """Prima scrittura di un grafo: fuori da transaction perche' il file non esiste ancora."""
    path.parent.mkdir(parents=True, exist_ok=True)
    _scrivi_atomico(path, dumps(graph))


@contextmanager
def transaction(path: Path):
    """Sezione critica sul grafo: leggi, muta, riscrivi, tutto con il lock in mano.

    La lettura sta dentro il lock e non fuori: chi arriva secondo parte dallo stato
    che il primo ha appena scritto, non dalla copia che aveva in mano prima di
    mettersi in coda. Se il corpo solleva, il file non viene toccato affatto: il
    rollback e' non scrivere.
    """
    with _sotto_lock(path):
        graph = load(path)
        yield graph
        _scrivi_atomico(path, dumps(graph))


@contextmanager
def read_transaction(path: Path):
    """Sezione critica di sola lettura: il lock protegge la rilettura dal rischio
    che il file venga modificato fra il load e l'uscita dal with.

    Usato dopo una mutazione per rigenerare gli artefatti con dati coerenti al grafo.
    """
    with _sotto_lock(path):
        yield load(path)
