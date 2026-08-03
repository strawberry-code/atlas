"""L'unico modo lecito di cambiare la forma di un grafo: codice, non editing a mano.

Uno script apre una sola transazione, muta quanto vuole e alla chiusura il grafo
viene validato: se la forma non regge, il file non viene toccato affatto. Cosi' gli
script in .atlas/scripts/ diventano la storia delle modifiche, rileggibile in diff.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from .config import Graph, Workspace
from .model import by_id, levels, node_of
from .store import OPEN, DROPPED, SCHEMA_VERSION, StateError, transaction, write_new
from .strings import t


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


# --- struttura -------------------------------------------------------------

def add_branch(g: Editor, key: str, label: str, color: str = "#64748b") -> None:
    if key in g.data["branches"]:
        raise StateError(t("mutate.ramo_esiste", chiave=key))
    g.data["branches"][key] = {"label": label, "color": color}


def add_node(g: Editor, id: str, title: str, branch: str, question: str,
             type: str = "task", mode: str = "AFK",
             blockedBy: list[str] | tuple[str, ...] = (), artifacts: list[str] = ()) -> dict:
    if id in g.ids():
        raise StateError(t("mutate.nodo_esiste", id=id))
    node = {"id": id, "title": title, "branch": branch, "type": type, "mode": mode,
            "status": OPEN, "assignee": None, "blockedBy": list(blockedBy),
            "question": question, "answer": None, "claim": None,
            "artifacts": list(artifacts), "createdAt": now()}
    g.data["nodes"].append(node)
    return node


def edit_node(g: Editor, node_id: str, **fields) -> dict:
    """Cambia i campi descrittivi. Stato e claim passano da claims, non da qui."""
    protetti = {"id", "status", "assignee", "claim"}
    if illeciti := protetti & set(fields):
        raise StateError(t("mutate.campi_protetti", elenco=", ".join(sorted(illeciti))))
    node = g.node(node_id)
    node.update(fields)
    return node


def remove_node(g: Editor, node_id: str) -> None:
    """Cancella davvero. Se il nodo e' stato lavorato, drop() e' quasi sempre meglio."""
    if dipendenti := [n["id"] for n in g.data["nodes"] if node_id in n["blockedBy"]]:
        raise StateError(t("mutate.blocca_ancora", id=node_id, dipendenti=", ".join(dipendenti)))
    g.node(node_id)
    g.data["nodes"] = [n for n in g.data["nodes"] if n["id"] != node_id]


def link(g: Editor, node_id: str, blocked_by: str) -> None:
    node = g.node(node_id)
    g.node(blocked_by)
    if blocked_by not in node["blockedBy"]:
        node["blockedBy"].append(blocked_by)


def unlink(g: Editor, node_id: str, blocked_by: str) -> None:
    node = g.node(node_id)
    if blocked_by not in node["blockedBy"]:
        raise StateError(t("mutate.non_bloccato", id=node_id, blocked_by=blocked_by))
    node["blockedBy"].remove(blocked_by)


def drop(g: Editor, node_id: str, reason: str) -> dict:
    """Fuori scopo: il nodo esce dal percorso ma continua a sbloccare chi lo aspettava."""
    node = g.node(node_id)
    node.update(status=DROPPED, assignee=None, claim=None, answer=reason)
    g.data["outOfScope"].append(f"**{node['title']}** ({node_id}): {reason}")
    return node


def reopen(g: Editor, node_id: str) -> dict:
    node = g.node(node_id)
    node.update(status=OPEN, assignee=None, claim=None, answer=None)
    node.pop("closedAt", None)
    return node


# --- contorno --------------------------------------------------------------

def fog_add(g: Editor, line: str) -> None:
    g.data["fog"].append(line)


def fog_drop(g: Editor, needle: str) -> int:
    """Toglie dalla nebbia le righe che contengono needle: si usa dopo averle promosse."""
    prima = len(g.data["fog"])
    g.data["fog"] = [f for f in g.data["fog"] if needle not in f]
    return prima - len(g.data["fog"])


def set_meta(g: Editor, **fields) -> None:
    g.data["meta"].update(fields)


def note_add(g: Editor, line: str) -> None:
    g.data["meta"]["notes"].append(line)


# --- nascita di un grafo ---------------------------------------------------

def create_graph(ws: Workspace, slug: str, title: str, destination: str,
                 branches: dict[str, dict] | None = None,
                 notes: list[str] | None = None) -> Graph:
    ref = Graph(ws, slug)
    if ref.exists():
        raise StateError(t("mutate.grafo_esiste", slug=slug, dir=ref.dir))
    data = {
        "schemaVersion": SCHEMA_VERSION,
        "meta": {"slug": slug, "title": title, "destination": destination,
                 "updated": now()[:10], "notes": notes or []},
        "branches": branches or {"A": {"label": t("mutate.ramo_default_label"), "color": "#4f46e5"}},
        "nodes": [], "fog": [], "outOfScope": [],
    }
    validate(data, ws.config["vocab"])
    write_new(ref.json_path, data)
    ref.tickets_dir.mkdir(parents=True, exist_ok=True)
    return ref
