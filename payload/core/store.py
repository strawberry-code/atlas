"""Unico proprietario in scrittura di graph.json: nessun altro modulo lo apre in scrittura.

Il ciclo leggi-modifica-scrivi passa sempre da transaction(), che tiene un flock
esclusivo per tutta la durata: due sessioni che scrivono insieme si serializzano
invece di sovrascriversi a vicenda.
"""
from __future__ import annotations

import json
import re
import sys
from contextlib import contextmanager
from pathlib import Path

from .config import ConfigError
from .strings import t

SCHEMA_VERSION = 1
OPEN, CLAIMED, CLOSED, DROPPED = "open", "claimed", "closed", "out-of-scope"

if sys.platform == "win32":
    import msvcrt

    def _lock(fh) -> None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)

    def _unlock(fh) -> None:
        pos = fh.tell()
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        fh.seek(pos)
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


def _decodifica(path: Path, testo_o_file) -> dict:
    """Il grafo, o un ConfigError che dice quale file e' rotto e come.

    Il grafo e' l'unica fonte di verita' del progetto e lo riscrivono anche gli
    script degli agenti: puo' arrivare troncato o non essere affatto un grafo, e
    in tutti e due i casi il chiamante deve poterlo dire invece di morire.
    """
    try:
        graph = (json.loads(testo_o_file) if isinstance(testo_o_file, str)
                 else json.load(testo_o_file))
    except json.JSONDecodeError as errore:
        raise ConfigError(t("store.grafo_rotto", path=path, dettaglio=errore)) from errore
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
        raise ConfigError(t("store.grafo_senza_nodi", path=path))
    return graph


def load(path: Path) -> dict:
    return _decodifica(path, path.read_text(encoding="utf-8"))


def write_new(path: Path, graph: dict) -> None:
    """Prima scrittura di un grafo: fuori da transaction perche' il file non esiste ancora."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(graph), encoding="utf-8")


@contextmanager
def transaction(path: Path):
    """Sezione critica sul grafo: il lock esclusivo (fcntl su POSIX, msvcrt su Windows)
    si rilascia sempre nel finally, corpo sollevi o no.

    Se il corpo solleva, il file non viene riscritto: il rollback e' non scrivere.
    """
    with path.open("r+", encoding="utf-8") as fh:
        _lock(fh)
        try:
            graph = _decodifica(path, fh)
            yield graph
            fh.seek(0)
            fh.write(dumps(graph))
            fh.truncate()
        finally:
            _unlock(fh)


@contextmanager
def read_transaction(path: Path):
    """Sezione critica di sola lettura: il lock esclusivo protegge la rilettura
    dal rischio che il file venga modificato fra il load e l'uscita dal with.

    Usato dopo una mutazione per rigenerare gli artefatti con dati coerenti al grafo.
    """
    with path.open("r", encoding="utf-8") as fh:
        _lock(fh)
        try:
            graph = _decodifica(path, fh)
            yield graph
        finally:
            _unlock(fh)
