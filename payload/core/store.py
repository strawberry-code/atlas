"""Unico proprietario in scrittura di graph.json: nessun altro modulo lo apre in scrittura.

Il ciclo leggi-modifica-scrivi passa sempre da transaction(), che tiene un flock
esclusivo per tutta la durata: due sessioni che scrivono insieme si serializzano
invece di sovrascriversi a vicenda.
"""
from __future__ import annotations

import fcntl
import json
import re
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1
OPEN, CLAIMED, CLOSED, DROPPED = "open", "claimed", "closed", "out-of-scope"

# json.dumps con indent espande ogni array su piu' righe: qui gli array sono liste
# corte di id ("blockedBy") e riespanderli renderebbe illeggibile il diff di un claim.
_STR_ARRAY = re.compile(r'\[\s+((?:"(?:[^"\\]|\\.)*",?\s*)+)\]')


class StateError(Exception):
    """Violazione del protocollo: il chiamante la mostra e si ferma."""


def dumps(graph: dict) -> str:
    text = json.dumps(graph, ensure_ascii=False, indent=2)
    return _STR_ARRAY.sub(lambda m: "[" + " ".join(m.group(1).split()) + "]", text) + "\n"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, graph: dict) -> None:
    """Prima scrittura di un grafo: fuori da transaction perche' il file non esiste ancora."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(graph), encoding="utf-8")


@contextmanager
def transaction(path: Path):
    """Sezione critica sul grafo: il flock cade da solo alla chiusura del descrittore.

    Se il corpo solleva, il file non viene riscritto: il rollback e' non scrivere.
    """
    with path.open("r+", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        graph = json.load(fh)
        yield graph
        fh.seek(0)
        fh.write(dumps(graph))
        fh.truncate()
