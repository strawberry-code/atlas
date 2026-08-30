"""L'unico modo lecito di cambiare la forma di un grafo: codice, non editing a mano.

Qui c'e' il vocabolario dei gesti; la transazione dentro cui girano, l'handle che
ricevono e la validazione finale stanno in editor.py. I nomi si re-importano qui
perche' uno script scrive 'from core import mutate' e da li' chiama tutto, senza
dover sapere che il meccanismo abita altrove.
"""
from __future__ import annotations

import re

from .assign import assign, nome_persona, persone, unassign    # noqa: F401  (superficie per gli script)
from .config import Graph, Workspace
from .editor import Editor, editing, now, validate    # noqa: F401  (superficie per gli script)
from .lifecycle import amend, drop, reopen, restore_closure    # noqa: F401  (idem)
from .store import OPEN, SCHEMA_VERSION, StateError, write_new
from .strings import t
from .identity import identity


# --- struttura -------------------------------------------------------------

def add_branch(g: Editor, key: str, label: str, color: str = "#64748b") -> None:
    if key in g.data["branches"]:
        raise StateError(t("mutate.ramo_esiste", chiave=key))
    g.data["branches"][key] = {"label": label, "color": color}


def add_node(g: Editor, id: str, title: str, branch: str, question: str,
             type: str = "task", mode: str = "AFK",
             blockedBy: list[str] | tuple[str, ...] = (), artifacts: list[str] = (),
             model: str | None = None) -> dict:
    if id in g.ids():
        raise StateError(t("mutate.nodo_esiste", id=id))
    node = {"id": id, "title": title, "branch": branch, "type": type, "mode": mode,
            "status": OPEN, "assignee": None, "owner": [], "blockedBy": list(blockedBy),
            "question": question, "answer": None, "claim": None,
            "artifacts": list(artifacts), "createdAt": now()}
    if model is not None:
        node["model"] = model
    g.data["nodes"].append(node)
    return node


def edit_node(g: Editor, node_id: str, **fields) -> dict:
    """Cambia i campi descrittivi. Stato e claim passano da claims, non da qui."""
    protetti = {"id", "status", "assignee", "claim", "owner"}
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


def _next_question_id(g: Editor) -> str:
    numeri = [int(q["id"][1:]) for q in g.data.get("questions", [])
              if isinstance(q.get("id"), str) and re.fullmatch(r"Q\d+", q["id"])]
    return f"Q{max(numeri, default=0) + 1:03d}"


def ask(g: Editor, origin: str, question: str, assumption: str) -> dict:
    """Record an AFK question without changing the originating node's state."""
    node = g.node(origin)
    if node["mode"] == "HITL":
        raise StateError(t("mutate.ask_hitl", id=origin))
    if not isinstance(question, str) or not question.strip():
        raise StateError(t("mutate.ask_campo_vuoto", campo="question"))
    if not isinstance(assumption, str) or not assumption.strip():
        raise StateError(t("mutate.ask_campo_vuoto", campo="assumption"))
    record = {"id": _next_question_id(g), "question": question.strip(), "status": "open",
              "origin": origin, "assumption": assumption.strip(), "author": identity(),
              "askedAt": now(), "answer": None}
    g.data.setdefault("questions", []).append(record)
    return record


def answer(g: Editor, question_id: str, response: str) -> dict:
    """Answer a recorded question; the originating node remains untouched."""
    try:
        record = next(q for q in g.data.get("questions", []) if q["id"] == question_id)
    except StopIteration:
        raise StateError(t("mutate.domanda_inesistente", id=question_id)) from None
    if record["status"] != "open":
        raise StateError(t("mutate.domanda_gia_risposta", id=question_id))
    if not isinstance(response, str) or not response.strip():
        raise StateError(t("mutate.ask_campo_vuoto", campo="answer"))
    record.update(status="answered", answer=response.strip())
    return record


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


def conflicts_clear(g: Editor) -> None:
    """Dichiara risolti i conflitti di merge: toglie il campo 'conflicts' dal grafo.

    La risoluzione vera e' di chi legge: modifica graph.json a mano scegliendo la
    parte giusta, poi questo gesto toglie il marcatore che il merge driver ha
    lasciato (A02). Senza la correzione a mano il campo sparisce ma il contenuto
    resta quello del merge, cioe' 'nostro vince sul conflitto': il gesto dichiara,
    non risolve. Passa da mutate perche' la forma del grafo si cambia solo da qui.
    """
    g.data.pop("conflicts", None)


# --- nascita di un grafo ---------------------------------------------------

def _slug_tecnico(testo: str) -> str:
    """Normalizza un nome libero in kebab-case minuscolo: la parte tecnica dello
    slug del grafo, quella scelta da chi lo crea, prima del prefisso di data."""
    pezzo = re.sub(r"[^a-z0-9]+", "-", testo.lower()).strip("-")
    return pezzo or "grafo"


def _slug_datato(slug: str) -> str:
    """YYMMDD-<nome-tecnico>: la data e' quella di creazione, sempre aggiunta da
    qui e mai lasciata a chi chiama, cosi' ogni grafo nasce gia' ordinabile per
    quando e' nato anche solo guardando i nomi delle cartelle."""
    istante = now()
    return f"{istante[2:4]}{istante[5:7]}{istante[8:10]}-{_slug_tecnico(slug)}"


def create_graph(ws: Workspace, slug: str, title: str, destination: str,
                 branches: dict[str, dict] | None = None,
                 notes: list[str] | None = None) -> Graph:
    slug = _slug_datato(slug)
    ref = Graph(ws, slug)
    if ref.exists():
        raise StateError(t("mutate.grafo_esiste", slug=slug, dir=ref.dir))
    data = {
        "schemaVersion": SCHEMA_VERSION,
        "meta": {"slug": slug, "title": title, "destination": destination,
                 "updated": now()[:10], "notes": notes or []},
        "branches": branches or {"A": {"label": t("mutate.ramo_default_label"), "color": "#4f46e5"}},
        "nodes": [], "fog": [], "outOfScope": [],
        "questions": [],
    }
    validate(data, ws.config["vocab"])
    write_new(ref.json_path, data)
    ref.tickets_dir.mkdir(parents=True, exist_ok=True)
    return ref
