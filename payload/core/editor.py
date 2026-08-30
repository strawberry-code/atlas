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
from .model import node_of, owners_of
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
        if "model" in node and (not isinstance(node["model"], str) or not node["model"].strip()):
            raise StateError(t("mutate.modello_non_valido", id=node["id"]))
        for dep in node["blockedBy"]:
            if dep not in seen:
                raise StateError(t("mutate.dipendenza_inesistente", id=node["id"], dep=dep))
            if dep == node["id"]:
                raise StateError(t("mutate.auto_dipendenza", id=node["id"]))
    nodi = {node["id"] for node in data["nodes"]}
    domande = data.get("questions", [])
    if not isinstance(domande, list):
        raise StateError(t("mutate.domande_non_lista"))
    ids: set[str] = set()
    for domanda in domande:
        if not isinstance(domanda, dict):
            raise StateError(t("mutate.domanda_invalida", dettaglio="record non è un oggetto"))
        richiesti = ("id", "question", "status", "origin", "assumption", "author", "askedAt", "answer")
        mancanti = [campo for campo in richiesti if campo not in domanda]
        if mancanti:
            raise StateError(t("mutate.domanda_invalida", dettaglio="campi mancanti: " + ", ".join(mancanti)))
        if not isinstance(domanda["id"], str) or not domanda["id"] or domanda["id"] in ids:
            raise StateError(t("mutate.domanda_invalida", dettaglio="id non valido o duplicato"))
        ids.add(domanda["id"])
        if domanda["status"] not in ("open", "answered"):
            raise StateError(t("mutate.domanda_invalida", dettaglio="stato non valido"))
        if domanda["origin"] not in nodi:
            raise StateError(t("mutate.domanda_invalida", dettaglio="nodo d'origine inesistente"))
        if any(not isinstance(domanda[campo], str) or not domanda[campo].strip()
               for campo in ("question", "assumption", "author", "askedAt")):
            raise StateError(t("mutate.domanda_invalida", dettaglio="testo o timestamp non validi"))
        if domanda["status"] == "open" and domanda["answer"] is not None:
            raise StateError(t("mutate.domanda_invalida", dettaglio="una domanda aperta non ha risposta"))
        if domanda["status"] == "answered" and (not isinstance(domanda["answer"], str)
                                                   or not domanda["answer"].strip()):
            raise StateError(t("mutate.domanda_invalida", dettaglio="risposta mancante"))
    levels(data)  # solleva sui cicli


@contextmanager
def editing(ref: Graph, vocab: dict | None = None):
    """Transazione unica per tutta la durata di uno script di mutazione."""
    with transaction(ref.json_path) as data:
        editor = Editor(ref, data, vocab or ref.workspace.config["vocab"])
        # La transazione riscrive il file intero: la prima mutazione qualsiasi
        # mette in pari un grafo vecchio, sciogliendo anche i congiunti scritti a
        # mano. La lettura pura non riscrive niente e regge grazie a owners_of.
        for node in data["nodes"]:
            node["owner"] = owners_of(node)
        yield editor
        validate(data, editor.vocab)
        data["meta"]["updated"] = now()[:10]
