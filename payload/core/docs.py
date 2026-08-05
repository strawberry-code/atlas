"""I documenti markdown attorno al grafo: il ticket di un nodo e la mappa.

Qui vive la sola verifica che una macchina puo' fare sulla chiusura di un nodo,
cioe' che la risposta sia stata scritta. Che sia vera resta affare di chi la scrive.
"""
from __future__ import annotations

import re

from .config import Graph
from .store import StateError
from .strings import t

# Il marker separa la prosa scritta a mano, che sta sopra, da quel che discende dal
# grafo, che sta sotto e viene riscritto per intero a ogni render. Senza un confine
# esplicito la rigenerazione finiva per impilare una copia sull'altra.
MARK = "<!-- atlas:auto -->"

# Le sezioni di map.md che il grafo possiede, e la chiave da cui ciascuna discende.
# Le chiavi sono verso strings.py: l'intestazione vera dipende dalla lingua, e deve
# combaciare esattamente con quella scritta nel template map.{lingua}.md.
LISTS = {
    "heading.note": ("meta", "notes"),
    "heading.non_specificato": (None, "fog"),
    "heading.fuori_scopo": (None, "outOfScope"),
}


def answer_written(ref: Graph, node_id: str) -> bool:
    """La sezione Risposta contiene testo vero, non solo il commento segnaposto."""
    path = ref.ticket_path(node_id)
    if not path.exists():
        return False
    tail = path.read_text(encoding="utf-8-sig").rpartition(t("heading.risposta"))[2]
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
            blocked=", ".join(node["blockedBy"]) or t("docs.nessuno_prendibile"),
        ), encoding="utf-8-sig")
        creati += 1
    return creati


def ensure_map(ref: Graph, data: dict) -> None:
    if ref.map_path.exists():
        return
    ref.map_path.write_text(ref.workspace.template("map.md").format(
        title=data["meta"]["title"], slug=data["meta"]["slug"],
        destination=data["meta"]["destination"],
    ), encoding="utf-8-sig")


def _replace_section(text: str, heading: str, corpo: str) -> str:
    """Riscrive quel che segue il marker dentro una sezione, e lascia intatto il resto."""
    head, sep, tail = text.partition(heading)
    if not sep:
        raise StateError(t("docs.sezione_rinominata", heading=heading))
    body, nl, rest = tail.partition("\n## ")
    if MARK not in body:
        raise StateError(t("docs.marker_sezione_persa", heading=heading, mark=MARK))
    intro = body.partition(MARK)[0].rstrip()
    return f"{head}{sep}{intro}\n\n{MARK}\n{corpo}\n{nl}{rest}"


def decisions(data: dict) -> str:
    """L'indice del percorso camminato, in ordine cronologico: chiusure e rilasci motivati.
    Discende dal grafo.

    Tenerlo append-only lo rendeva l'unica parte della mappa che una rigenerazione
    non sapeva ricostruire: bastava perdere map.md per perdere la storia.
    """
    chiusi = [(n.get("closedAt") or "",
              f"- **{n['id']}** {n['title']}: {n['answer']} · [ticket](tickets/{n['id']}.md)")
             for n in data["nodes"] if n["status"] == "closed"]
    rilasci = [(r["at"], f"- **{r['id']}** {r['title']} rilasciato: {r['reason']} · "
                          f"[ticket](tickets/{r['id']}.md)")
              for r in data.get("releases", [])]
    righe = [riga for _, riga in sorted(chiusi + rilasci, key=lambda x: x[0])]
    return "\n".join(righe) or t("docs.niente")


def rewrite_lists(ref: Graph, data: dict) -> None:
    """Rigenera in map.md le sezioni che il grafo possiede. Editarle a mano non serve."""
    text = ref.map_path.read_text(encoding="utf-8-sig")
    text = _replace_section(text, t("heading.destinazione"), data["meta"]["destination"])
    text = _replace_section(text, t("heading.decisioni"), decisions(data))
    for chiave, (parent, key) in LISTS.items():
        items = data[parent][key] if parent else data[key]
        text = _replace_section(text, t(chiave), "\n".join(f"- {i}" for i in items) or t("docs.niente"))
    ref.map_path.write_text(text, encoding="utf-8-sig")
