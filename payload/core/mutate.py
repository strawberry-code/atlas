"""L'unico modo lecito di cambiare la forma di un grafo: codice, non editing a mano.

Qui c'e' il vocabolario dei gesti; la transazione dentro cui girano, l'handle che
ricevono e la validazione finale stanno in editor.py. I nomi si re-importano qui
perche' uno script scrive 'from core import mutate' e da li' chiama tutto, senza
dover sapere che il meccanismo abita altrove.
"""
from __future__ import annotations

from .config import Graph, Workspace
from .editor import Editor, editing, now, validate    # noqa: F401  (superficie per gli script)
from .identity import identity
from .model import by_id, is_done
from .store import OPEN, DROPPED, SCHEMA_VERSION, StateError, write_new
from .strings import t


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


def amend(g: Editor, node_id: str, artifacts: list[str] | None = None,
          cost: str | None = None, summary: str | None = None) -> dict:
    """Corregge la contabilita' di un nodo gia' chiuso: artefatti, costo, sintesi.

    La deduzione automatica degli artefatti sbaglia in una classe di casi nota, e
    chi se ne accorge lo fa rileggendo la chiusura appena fatta: senza questa via
    il dato sbagliato resta li', e con lui gli avvisi che doctor ne ricava.

    Tocca solo i campi passati e lascia stare stato, closedAt e closedBy: e' una
    riga di contabilita' riscritta, non una chiusura rifatta, e doctor deve
    continuare a misurare le scritture postume dall'istante vero della chiusura.
    La correzione resta scritta nel nodo, cosi' chi rilegge sa che quel campo e'
    stato messo a mano e non dedotto.
    """
    node = g.node(node_id)
    if not is_done(node):
        raise StateError(t("mutate.amend_non_chiuso", id=node_id, stato=node["status"]))
    cambiati = {}
    if artifacts is not None:
        cambiati["artifacts"] = list(artifacts)
    if cost is not None:
        cambiati["cost"] = cost
    if summary is not None:
        cambiati["answer"] = summary
    if not cambiati:
        raise StateError(t("mutate.amend_senza_campi", id=node_id))
    node.update(cambiati)
    node.setdefault("amendments", []).append(
        {"at": now(), "by": identity(), "fields": sorted(cambiati)})
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
