"""Il meccanismo con cui si cambia un grafo: transazione, handle, validazione.

Spezzato da mutate.py, che tiene il vocabolario dei gesti (aggiungi un nodo, lega
un arco, chiudi la contabilita'): qui c'e' solo l'impalcatura dentro cui quei gesti
girano. Uno script apre una sola transazione, muta quanto vuole e alla chiusura il
grafo viene validato: se la forma non regge, il file non viene toccato affatto.

Chi scrive uno script continua a passare da mutate, che re-importa questi nomi:
'from core import mutate' e 'mutate.editing(ref)' restano la via buona.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from .config import Graph
from .model import node_of
from .store import StateError, transaction
from .strings import t
from .topology import levels


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Editor:
    """Handle su un grafo aperto in scrittura. E' l'oggetto che riceve run(g)."""

    def __init__(self, ref: Graph, data: dict, vocab: dict):
        self.ref, self.data, self.vocab = ref, data, vocab

    @property
    def slug(self) -> str:
        return self.ref.slug

    def node(self, node_id: str) -> dict:
        return node_of(self.data, node_id)

    def ids(self) -> list[str]:
        return [n["id"] for n in self.data["nodes"]]


def validate(data: dict, vocab: dict) -> None:
    """Id unici, archi risolti, vocabolario rispettato, nessun ciclo."""
    seen: set[str] = set()
    for node in data["nodes"]:
        if node["id"] in seen:
            raise StateError(t("mutate.id_duplicato", id=node["id"]))
        seen.add(node["id"])
    for node in data["nodes"]:
        if node["branch"] not in data["branches"]:
            raise StateError(t("mutate.ramo_inesistente", id=node["id"], branch=node["branch"]))
        for key, allowed in (("type", vocab["types"]), ("mode", vocab["modes"]),
                             ("status", vocab["statuses"])):
            if node[key] not in allowed:
                raise StateError(t("mutate.vocab_non_valido", id=node["id"],
                                   chiave=key, valore=node[key], ammessi=allowed))
        for dep in node["blockedBy"]:
            if dep not in seen:
                raise StateError(t("mutate.dipendenza_inesistente", id=node["id"], dep=dep))
            if dep == node["id"]:
                raise StateError(t("mutate.auto_dipendenza", id=node["id"]))
    levels(data)  # solleva sui cicli


@contextmanager
def editing(ref: Graph, vocab: dict | None = None):
    """Transazione unica per tutta la durata di uno script di mutazione."""
    with transaction(ref.json_path) as data:
        editor = Editor(ref, data, vocab or ref.workspace.config["vocab"])
        yield editor
        validate(data, editor.vocab)
        data["meta"]["updated"] = now()[:10]
