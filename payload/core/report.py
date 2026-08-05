"""Quel che la CLI stampa: frontiera, lucchetti, elenco dei grafi, scheda di un nodo."""
from __future__ import annotations

from datetime import datetime, timedelta

from . import claims
from .config import Graph, Workspace
from .model import blocked, blocks, by_id, claimed, frontier, node_of, progress
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
    print()


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
    print(t("report.nodo_bloccato_da", elenco=", ".join(node["blockedBy"]) or t("report.nodo_nessuno")))
    print(t("report.nodo_blocca", elenco=", ".join(blocks(data, node_id)) or t("report.nodo_nessuno")))
    print(t("report.nodo_ticket", path=ref.ticket_path(node_id)))
    print(f"\n  {node['question']}\n")
    if node["answer"]:
        print(t("report.nodo_risposta", risposta=node["answer"]))


def doctor_avvisi(data: dict, ref: Graph, agente: dict) -> list[str]:
    """Avvisi sulla salute di un grafo: non bloccano niente, segnalano soltanto."""
    avvisi = []

    foglie = [n["id"] for n in data["nodes"] if not blocks(data, n["id"])]
    if len(foglie) > 1:
        avvisi.append(t("doctor.nodi_pendenti", elenco=", ".join(foglie)))

    for nodo in claimed(data):
        stato = claims.claim_state(nodo, agente)
        if stato != "live":
            avvisi.append(t("doctor.lucchetto_fermo", id=nodo["id"], stato=t(ETICHETTA[stato])))

    if ref.dashboard_path.is_file() and ref.json_path.stat().st_mtime > ref.dashboard_path.stat().st_mtime:
        avvisi.append(t("doctor.dashboard_stantia"))

    index = by_id(data)
    for nodo in claimed(data):
        chi = claims.holder(nodo).get("identity")
        autoverificati = [d for d in nodo["blockedBy"] if index[d].get("closedBy") == chi]
        if chi and autoverificati:
            avvisi.append(t("doctor.autoverifica", id=nodo["id"], chi=chi, elenco=", ".join(autoverificati)))

    for nodo in data["nodes"]:
        chiuso = nodo.get("closedAt")
        if nodo["status"] != "closed" or not chiuso or not nodo.get("artifacts"):
            continue
        soglia = datetime.fromisoformat(chiuso)
        tocchi = [a for a in nodo["artifacts"] if (ref.workspace.project_root / a).is_file()
                  and datetime.fromtimestamp((ref.workspace.project_root / a).stat().st_mtime).astimezone() > soglia]
        if tocchi:
            avvisi.append(t("doctor.ambito_toccato", id=nodo["id"], elenco=", ".join(tocchi)))

    return avvisi


def show_doctor(ws: Workspace) -> None:
    """Avvisi sulla salute di ogni grafo del progetto: non bloccano niente, segnalano soltanto."""
    agente = ws.config["agent"]
    for slug in ws.slugs():
        ref = Graph(ws, slug)
        data = load(ref.json_path)
        avvisi = doctor_avvisi(data, ref, agente)
        if avvisi:
            print(t("doctor.grafo_titolo", slug=slug))
            for avviso in avvisi:
                print(f"    {avviso}")
    print()


def show_fog(ref: Graph, data: dict) -> None:
    voci = data["fog"]
    if not voci:
        print(t("report.nebbia_vuota"))
        return
    print(t("report.nebbia_titolo"))
    for i, voce in enumerate(voci):
        print(f"    [{i}] {voce}")
