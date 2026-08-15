"""I documenti markdown attorno al grafo: il ticket di un nodo e la mappa.

Qui vive la sola verifica che una macchina puo' fare sulla chiusura di un nodo,
cioe' che la risposta sia stata scritta. Che sia vera resta affare di chi la scrive.
"""
from __future__ import annotations

import re

from .config import Graph
from .store import StateError, scrivi_atomico
from .strings import t

# Il marker separa la prosa scritta a mano, che sta sopra, da quel che discende dal
# grafo, che sta sotto e viene riscritto per intero a ogni render. Senza un confine
# esplicito la rigenerazione finiva per impilare una copia sull'altra.
MARK = "<!-- atlas:auto -->"

# Nel ticket il rapporto e' rovesciato: la parte derivata (titolo, ramo, tipo, modo,
# bloccanti, domanda) sta in testa fra i due marker, e la prosa umana viene dopo. Serve
# un marker di chiusura perche' la testa contiene gia' un '## ', che nella mappa basta
# a chiudere una sezione.
MARK_END = "<!-- /atlas:auto -->"

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
    modello, coda = _modello(ref)
    rami, creati = data["branches"], 0
    for node in data["nodes"]:
        path = ref.ticket_path(node["id"])
        if path.exists():
            continue
        scrivi_atomico(path, _testa(modello, node, rami) + coda)
        creati += 1
    return creati


def _modello(ref: Graph) -> tuple[str, str]:
    """Il template spezzato sul marker: la testa da formattare, la coda da lasciar stare.
    Il layout del ticket resta scritto una volta sola, nel template."""
    testa, _, coda = ref.workspace.template("ticket.md").partition(MARK_END)
    return testa + MARK_END, coda


def _testa(modello: str, node: dict, rami: dict) -> str:
    """La parte del ticket che discende dal grafo: titolo, ramo, tipo, modo, bloccanti, domanda."""
    return modello.format(
        id=node["id"], title=node["title"], type=node["type"], mode=node["mode"],
        branch=rami[node["branch"]]["label"], question=node["question"],
        blocked=", ".join(node["blockedBy"]) or t("docs.nessuno_prendibile"),
    )


def _coda(testo: str) -> str | None:
    """Quel che nel ticket e' stato scritto a mano, o None se il confine non si riconosce.

    Per i ticket nati prima che il marker esistesse il confine si deduce dall'intestazione
    della Lavorazione: cosi' il primo render li riallinea invece di lasciarli indietro.
    """
    if MARK_END in testo:
        return testo.partition(MARK_END)[2]
    _, sep, resto = testo.partition(t("heading.lavorazione"))
    return f"\n\n{sep}{resto}" if sep else None


def rewrite_heads(ref: Graph, data: dict) -> int:
    """Riallinea al grafo la testa dei ticket gia' esistenti, e ritorna quanti ne ha toccati.

    E' il rimedio a un ticket che invecchia: edit_node cambia graph.json, e senza questo
    il markdown continuava a raccontare il titolo, la domanda e i bloccanti di prima.
    Riscrive solo se qualcosa e' davvero cambiato, perche' un mtime mosso a vuoto e'
    rumore per il controllo di sconfinamento di doctor.
    """
    modello, _ = _modello(ref)
    rami, riscritti = data["branches"], 0
    for node in data["nodes"]:
        path = ref.ticket_path(node["id"])
        if not path.exists():
            continue
        testo = path.read_text(encoding="utf-8-sig")
        coda = _coda(testo)
        if coda is None:
            continue                       # segnalato da unalignable(), mai sovrascritto alla cieca
        nuovo = _testa(modello, node, rami) + coda
        if nuovo != testo:
            scrivi_atomico(path, nuovo)
            riscritti += 1
    return riscritti


def unalignable(ref: Graph, data: dict) -> list[str]:
    """I ticket in cui non si riconosce il confine fra parte derivata e testo scritto:
    nessuna rigenerazione li tocca, quindi restano indietro in silenzio."""
    return [node["id"] for node in data["nodes"]
            if ref.ticket_path(node["id"]).exists()
            and _coda(ref.ticket_path(node["id"]).read_text(encoding="utf-8-sig")) is None]


def ensure_map(ref: Graph, data: dict) -> None:
    if ref.map_path.exists():
        return
    scrivi_atomico(ref.map_path, ref.workspace.template("map.md").format(
        title=data["meta"]["title"], slug=data["meta"]["slug"],
        destination=data["meta"]["destination"],
    ))


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
    scrivi_atomico(ref.map_path, text)
