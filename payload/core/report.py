"""Quel che la CLI stampa: frontiera, lucchetti, elenco dei grafi, scheda di un nodo."""
from __future__ import annotations

from datetime import timedelta

from . import claims
from .config import Graph, Workspace
from .model import blocked, blocks, claimed, frontier, node_of, progress
from .store import load

ETICHETTA = {
    "live": "sessione viva",
    "idle": "sessione viva ma ferma",
    "dead": "sessione finita, lucchetto orfano",
}


def durata(delta: timedelta | None) -> str:
    if delta is None:
        return "da quando non si sa"
    minuti = int(delta.total_seconds() // 60)
    if minuti < 60:
        return f"da {minuti}m"
    return f"da {minuti // 60}h{minuti % 60:02d}" if minuti < 1440 else f"da {minuti // 1440}g"


def show_status(ref: Graph, data: dict) -> None:
    agente = ref.workspace.config["agent"]
    fatti, totale = progress(data)
    print(f"\n  {data['meta']['title']} · {ref.slug} · {fatti}/{totale} nodi chiusi\n")

    if front := frontier(data):
        print("  Frontiera, prendibile adesso:")
        for node in front:
            print(f"    {node['id']}  {node['title']}  [{node['type']}/{node['mode']}]")
    elif not totale:
        print("  Grafo vuoto: popolalo con uno script di mutazione.")
        print("  'atlas new-script primo-disegno', poi 'atlas exec' su quel file.")
    elif not blocked(data) and not claimed(data):
        print("  Niente di aperto: il grafo è finito.")
    else:
        print("  Frontiera vuota: tutto quel che resta aspetta un nodo in lavorazione.")

    if presi := claimed(data):
        print("\n  In lavorazione:")
        stanchi = []
        for node in presi:
            stato = claims.claim_state(node, agente)
            quando = durata(claims.held_since(node))
            print(f"    {node['id']}  {node['title']}")
            print(f"          {node['assignee']} · {ETICHETTA[stato]}, {quando}")
            if stato != "live":
                stanchi.append(node["id"])
        if stanchi:
            print(f"\n  Sistema {', '.join(stanchi)} prima di rivendicare altro:"
                  f" 'atlas release <ID>' oppure riconfermalo lavorandolo.")
    print()


def show_graphs(ws: Workspace) -> None:
    slugs = ws.slugs()
    if not slugs:
        print("\n  Nessun grafo. Creane uno con 'atlas new <slug> -t \"titolo\"'.\n")
        return
    attivo = ws.graph().slug if len(slugs) == 1 else (ws.pinned() or "")
    print()
    for slug in slugs:
        data = load(Graph(ws, slug).json_path)
        fatti, totale = progress(data)
        segno = "→" if slug == attivo else " "
        print(f"  {segno} {slug:<22} {fatti}/{totale} chiusi · "
              f"{len(frontier(data))} prendibili · {data['meta']['title']}")
    print()


def show_node(ref: Graph, data: dict, node_id: str) -> None:
    node = node_of(data, node_id)
    ramo = data["branches"][node["branch"]]["label"]
    print(f"\n  {node['id']} · {node['title']}")
    print(f"  {ramo} · {node['type']}/{node['mode']} · {node['status']}")
    print(f"  bloccato da: {', '.join(node['blockedBy']) or 'nessuno'}")
    print(f"  blocca:      {', '.join(blocks(data, node_id)) or 'nessuno'}")
    print(f"  ticket:      {ref.ticket_path(node_id)}")
    print(f"\n  {node['question']}\n")
    if node["answer"]:
        print(f"  Risposta: {node['answer']}\n")
