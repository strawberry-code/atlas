"""Quel che la CLI stampa: frontiera, lucchetti, elenco dei grafi, scheda di un nodo."""
from __future__ import annotations

from datetime import timedelta

from . import claims, docs
from .config import Graph, Workspace
from .model import (blocked, blocks, claimed, fog_for, frontier, is_done, node_of,
                    owner_of, owners, progress, unowned)
from .topology import ranked_frontier
from .store import load
from .strings import t

ETICHETTA = {
    "live": "report.stato_live",
    "idle": "report.stato_idle",
    "dead": "report.stato_dead",
}


def durata(delta: timedelta | None) -> str:
    if delta is None:
        return t("report.durata_ignota")
    minuti = int(delta.total_seconds() // 60)
    if minuti < 60:
        return t("report.durata_minuti", n=minuti)
    if minuti < 1440:
        return t("report.durata_ore", h=minuti // 60, m=minuti % 60)
    return t("report.durata_giorni", g=minuti // 1440)


def show_status(ref: Graph, data: dict) -> None:
    agente = ref.workspace.config["agent"]
    fatti, totale = progress(data)
    print(t("report.titolo", titolo=data["meta"]["title"], slug=ref.slug, fatti=fatti, totale=totale))

    if front := frontier(data):
        print(t("report.frontiera_titolo"))
        for node in front:
            print(f"    {node['id']}  {node['title']}  [{node['type']}/{node['mode']}]")
    elif not totale:
        print(t("report.grafo_vuoto_1"))
        print(t("report.grafo_vuoto_2"))
    elif not blocked(data) and not claimed(data):
        print(t("report.finito"))
    else:
        print(t("report.frontiera_vuota"))

    if presi := claimed(data):
        print(t("report.in_lavorazione"))
        stanchi = []
        for node in presi:
            stato = claims.claim_state(node, agente)
            quando = durata(claims.held_since(node))
            print(f"    {node['id']}  {node['title']}")
            print(f"          {node['assignee']} · {t(ETICHETTA[stato])}, {quando}")
            if stato != "live":
                stanchi.append(node["id"])
        if stanchi:
            print(t("report.sistema", elenco=", ".join(stanchi)))

    show_assegnazioni(ref, data)
    print()


def show_assegnazioni(ref: Graph, data: dict) -> None:
    """Chi ha cosa. Tace su un grafo che non usa le assegnazioni, invece di
    stampare una riga che dice che non c'e' niente da dire."""
    ripartizione = owners(data)
    if not ripartizione:
        return
    print(t("report.assegnazioni"))
    for nome, ids in ripartizione.items():
        print(t("report.assegnazione_riga", nome=nome, elenco=", ".join(ids)))
    if liberi := unowned(data):
        print(t("report.non_assegnati", etichetta=t("render.non_assegnati"), n=len(liberi)))
    # Il nome locale non entra nella dashboard, che e' un file condiviso: qui invece
    # siamo sul terminale di chi ha il repo davanti, ed e' il posto giusto per dirlo.
    io = ref.workspace.whoami()
    if io and io in ripartizione:
        print(t("report.assegnazione_tuoi", elenco=", ".join(ripartizione[io])))


def show_graphs(ws: Workspace) -> None:
    slugs = ws.slugs()
    if not slugs:
        print(t("report.nessun_grafo"))
        return
    attivo = ws.graph().slug if len(slugs) == 1 else (ws.pinned() or "")
    print()
    for slug in slugs:
        data = load(Graph(ws, slug).json_path)
        fatti, totale = progress(data)
        segno = "→" if slug == attivo else " "
        print(t("report.riga_grafo", segno=segno, slug=slug, fatti=fatti, totale=totale,
                n=len(frontier(data)), titolo=data["meta"]["title"]))
    print()


def show_node(ref: Graph, data: dict, node_id: str) -> None:
    node = node_of(data, node_id)
    ramo = data["branches"][node["branch"]]["label"]
    print(f"\n  {node['id']} · {node['title']}")
    print(f"  {ramo} · {node['type']}/{node['mode']} · {node['status']}")
    print(t("report.nodo_assegnato", nome=owner_of(node) or t("report.nodo_nessuno")))
    print(t("report.nodo_bloccato_da", elenco=", ".join(node["blockedBy"]) or t("report.nodo_nessuno")))
    print(t("report.nodo_blocca", elenco=", ".join(blocks(data, node_id)) or t("report.nodo_nessuno")))
    print(t("report.nodo_ticket", path=ref.ticket_path(node_id)))
    print(f"\n  {node['question']}\n")
    if node["answer"]:
        print(t("report.nodo_risposta", risposta=node["answer"]))


def show_fog(ref: Graph, data: dict) -> None:
    voci = data["fog"]
    if not voci:
        print(t("report.nebbia_vuota"))
        return
    print(t("report.nebbia_titolo"))
    for i, voce in enumerate(voci):
        print(f"    [{i}] {voce}")


def show_brief(ref: Graph, data: dict, node_id: str) -> None:
    """Il pacchetto di contesto per lavorare un nodo: domanda, risposte dei bloccanti,
    nebbia che lo nomina, rilasci passati su questo stesso nodo."""
    node = node_of(data, node_id)
    ramo = data["branches"][node["branch"]]["label"]
    print(f"\n  {node['id']} · {node['title']}")
    print(f"  {ramo} · {node['type']}/{node['mode']} · {node['status']}")
    print(f"\n  {node['question']}\n")

    if node["blockedBy"]:
        print(t("report.brief_bloccanti"))
        for dep_id in node["blockedBy"]:
            dep = node_of(data, dep_id)
            if dep["status"] == "closed":
                print(f"    {dep['id']} {dep['title']}: {dep['answer']}")
            else:
                print(t("report.brief_bloccante_aperto", id=dep["id"], titolo=dep["title"], stato=dep["status"]))

    nebbia = fog_for(data, node_id)
    if nebbia:
        print(t("report.brief_nebbia"))
        for voce in nebbia:
            print(f"    {voce}")

    rilasci = [r for r in data.get("releases", []) if r["id"] == node_id]
    if rilasci:
        print(t("report.brief_rilasci"))
        for r in rilasci:
            print(f"    {r['at']}: {r['reason']}")
    print()


def show_next(ref: Graph, data: dict) -> None:
    """La frontiera ordinata per impatto: quanti nodi sblocca, poi cammino residuo."""
    righe = ranked_frontier(data)
    if not righe:
        print(t("report.frontiera_vuota"))
        return
    print(t("report.next_titolo"))
    for nodo, sblocca, cammino in righe:
        print(t("report.next_riga", id=nodo["id"], titolo=nodo["title"], sblocca=sblocca, cammino=cammino))
    print()
