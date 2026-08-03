"""I documenti markdown attorno al grafo: il ticket di un nodo e la mappa.

Qui vive la sola verifica che una macchina puo' fare sulla chiusura di un nodo,
cioe' che la risposta sia stata scritta. Che sia vera resta affare di chi la scrive.
"""
from __future__ import annotations

import re

from .config import Graph
from .store import StateError

NIENTE = "_niente, per ora._"

# Il marker separa la prosa scritta a mano, che sta sopra, da quel che discende dal
# grafo, che sta sotto e viene riscritto per intero a ogni render. Senza un confine
# esplicito la rigenerazione finiva per impilare una copia sull'altra.
MARK = "<!-- atlas:auto -->"

# Le sezioni di map.md che il grafo possiede, e la chiave da cui ciascuna discende.
LISTS = {
    "## Note": ("meta", "notes"),
    "## Non ancora specificato": (None, "fog"),
    "## Fuori scopo": (None, "outOfScope"),
}


def answer_written(ref: Graph, node_id: str) -> bool:
    """La sezione Risposta contiene testo vero, non solo il commento segnaposto."""
    path = ref.ticket_path(node_id)
    if not path.exists():
        return False
    tail = path.read_text(encoding="utf-8").rpartition("## Risposta")[2]
    return bool(re.sub(r"<!--.*?-->", "", tail, flags=re.S).strip())


def write_stubs(ref: Graph, data: dict) -> int:
    """Crea i ticket mancanti. Non sovrascrive mai: il lavoro scritto resta."""
    ref.tickets_dir.mkdir(parents=True, exist_ok=True)
    stub, rami, creati = ref.workspace.template("ticket.md"), data["branches"], 0
    for node in data["nodes"]:
        path = ref.ticket_path(node["id"])
        if path.exists():
            continue
        path.write_text(stub.format(
            id=node["id"], title=node["title"], type=node["type"], mode=node["mode"],
            branch=rami[node["branch"]]["label"], question=node["question"],
            blocked=", ".join(node["blockedBy"]) or "nessuno, prendibile subito",
        ), encoding="utf-8")
        creati += 1
    return creati


def ensure_map(ref: Graph, data: dict) -> None:
    if ref.map_path.exists():
        return
    ref.map_path.write_text(ref.workspace.template("map.md").format(
        title=data["meta"]["title"], slug=data["meta"]["slug"],
        destination=data["meta"]["destination"],
    ), encoding="utf-8")


def _replace_section(text: str, heading: str, corpo: str) -> str:
    """Riscrive quel che segue il marker dentro una sezione, e lascia intatto il resto."""
    head, sep, tail = text.partition(heading)
    if not sep:
        raise StateError(
            f"map.md non ha la sezione '{heading}': rinominarla ferma la rigenerazione.\n"
            f"  Rimettila, oppure cancella map.md e lascia che 'atlas render' la ricrei."
        )
    body, nl, rest = tail.partition("\n## ")
    if MARK not in body:
        raise StateError(
            f"la sezione '{heading}' di map.md ha perso il marker {MARK}.\n"
            f"  Senza quel confine non si sa dove finisce la prosa scritta a mano."
        )
    intro = body.partition(MARK)[0].rstrip()
    return f"{head}{sep}{intro}\n\n{MARK}\n{corpo}\n{nl}{rest}"


def decisions(data: dict) -> str:
    """L'indice del percorso camminato, in ordine di chiusura. Discende dal grafo.

    Tenerlo append-only lo rendeva l'unica parte della mappa che una rigenerazione
    non sapeva ricostruire: bastava perdere map.md per perdere la storia.
    """
    chiusi = sorted((n for n in data["nodes"] if n["status"] == "closed"),
                    key=lambda n: n.get("closedAt") or "")
    return "\n".join(
        f"- **{n['id']}** {n['title']}: {n['answer']} · [ticket](tickets/{n['id']}.md)"
        for n in chiusi
    ) or NIENTE


def rewrite_lists(ref: Graph, data: dict) -> None:
    """Rigenera in map.md le sezioni che il grafo possiede. Editarle a mano non serve."""
    text = ref.map_path.read_text(encoding="utf-8")
    text = _replace_section(text, "## Destinazione", data["meta"]["destination"])
    text = _replace_section(text, "## Decisioni prese", decisions(data))
    for heading, (parent, key) in LISTS.items():
        items = data[parent][key] if parent else data[key]
        text = _replace_section(text, heading, "\n".join(f"- {i}" for i in items) or NIENTE)
    ref.map_path.write_text(text, encoding="utf-8")
