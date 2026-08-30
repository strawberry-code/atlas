"""Quel che la CLI stampa: frontiera, lucchetti, elenco dei grafi, scheda di un nodo."""
from __future__ import annotations

from datetime import timedelta

from . import claims, docs, drift, questions
from .config import Graph, Workspace
from .model import (blocked, blocks, claimed, fog_for, frontier, is_done, node_of,
                    owners, owners_of, progress, unowned)
from .topology import ranked_frontier
from .run_state import RunState
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
    show_run_status(ref, quiet=True)
    print()


def show_run_status(ref: Graph, quiet: bool = False) -> None:
    """Mostra lo snapshot durevole dell'ultima esecuzione Automata."""
    stato = RunState.read(ref.run_state_path)
    if stato is None:
        if not quiet:
            print(t("report.run_nessuno"))
        return
    if not quiet:
        print(t("report.run_titolo", id=stato["run_id"], status=stato["status"],
                parallelism=stato["parallelism"]))
    else:
        print(t("report.run_riga", status=stato["status"], id=stato["run_id"]))
    if stato.get("node"):
        dettagli = [f"node={stato['node']}"]
        if stato.get("provider"):
            dettagli.append(f"provider={stato['provider']}")
        if stato.get("attempt") is not None:
            dettagli.append(f"attempt={stato['attempt']}")
        print("    " + " ".join(dettagli))
    if stato.get("reason"):
        print(t("report.run_motivo", reason=stato["reason"]))
    if stato.get("next_at") is not None:
        print(t("report.run_prossimo", at=stato["next_at"]))
    print(t("report.run_frontiera", ids=", ".join(stato.get("frontier", [])) or "-"))
    for blocker in stato.get("blockers", []):
        print(t("report.run_blocco", node=blocker["node"],
                blockers=", ".join(blocker.get("blocked_by", [])) or "-"))


def show_run_log(ref: Graph, tail: int | None = None) -> None:
    """Stampa la cronologia persistente, senza usarla per lo scheduling."""
    stato = RunState.read(ref.run_state_path)
    if stato is None:
        print(t("report.run_nessuno"))
        return
    eventi = stato["events"][-tail:] if tail is not None else stato["events"]
    print(t("report.run_log_titolo", id=stato["run_id"], n=len(eventi)))
    for evento in eventi:
        campi = " ".join(f"{key}={value}" for key, value in evento.items()
                         if key not in ("at", "type"))
        print(f"    {evento['at']} {evento['type']}" + (f" {campi}" if campi else ""))


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
    print(t("report.nodo_assegnato", nome=", ".join(owners_of(node)) or t("report.nodo_nessuno")))
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


def show_questions(ref: Graph, data: dict) -> None:
    """Mostra solo le domande ancora aperte, con origine e assunzione visibili."""
    aperte = questions.open_questions(data)
    if not aperte:
        print(t("asks.nessuna"))
        return
    print(t("asks.titolo"))
    for domanda in aperte:
        print(t("asks.riga", id=domanda["id"], origin=domanda["origin"],
                author=domanda["author"]))
        print(f"      {domanda['question']}")
        print(t("asks.assunzione", assumption=domanda["assumption"]))


def show_drift(ref: Graph, data: dict) -> None:
    """Stampa segnali di drift e il percorso umano per dichiarare un arco."""
    segnali = drift.missing_edges(ref, data)
    print(t("drift.titolo", slug=ref.slug))
    if not segnali:
        print(t("drift.nessun_segnale"))
    else:
        for segnale in segnali:
            print(t("drift.riga", earlier=segnale["earlier"], later=segnale["later"],
                    artifacts=", ".join(segnale["artifacts"])))
    print(t("drift.sola_diagnosi"))
    print(t("drift.rimedio"))


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
