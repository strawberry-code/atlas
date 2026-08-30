"""Segnali osservabili per la diagnosi del drift del grafo.

Questo modulo raccoglie soltanto evidenza: non aggiunge archi e non modifica il
grafo. I file collettori si escludono con path esatti nella configurazione, perché
un'estensione non dice se un documento o un foglio di test sia un deliverable.
"""
from __future__ import annotations

from .config import Graph, Workspace
from .model import istante


def collector_paths(workspace: Workspace) -> frozenset[str]:
    """Restituisce i path esatti configurati come file collettori.

    Una configurazione invalida viene trattata come vuota: la diagnosi non deve
    saltare per un dato opzionale, e un path non stringa non può accidentalmente
    escludere artefatti reali. Non sono supportati glob, directory o estensioni.
    """
    valori = workspace.config.get("drift", {}).get("collector_paths", [])
    if not isinstance(valori, list):
        return frozenset()
    return frozenset(
        valore for valore in valori
        if isinstance(valore, str) and valore and not valore.endswith("/")
        and "*" not in valore and "?" not in valore
        and not (valore.startswith(".") and "/" not in valore and valore.count(".") == 1)
    )


def shared_artifacts(ref: Graph, data: dict) -> list[dict]:
    """Raccoglie le coppie temporali di nodi chiusi con artefatti condivisi.

    Ogni riga contiene ``earlier``, ``later`` e l'elenco degli artefatti comuni.
    Una coppia è valida solo quando entrambi i timestamp sono leggibili e quello
    del secondo nodo è strettamente successivo al primo. Il risultato è ordinato
    per chiusura, così il chiamante può usarlo come evidenza senza ricostruire
    l'ordine da un elenco JSON arbitrario.
    """
    esclusi = collector_paths(ref.workspace)
    chiusi = []
    for node in data.get("nodes", []):
        if node.get("status") != "closed":
            continue
        closed_at = istante(node.get("closedAt"))
        if closed_at is None:
            continue
        artifacts = {
            path for path in node.get("artifacts", [])
            if isinstance(path, str) and path not in esclusi
        }
        if artifacts:
            chiusi.append((closed_at, node["id"], artifacts))

    chiusi.sort(key=lambda item: (item[0], item[1]))
    segnali = []
    for indice, (prima_data, prima_id, prima_artifacts) in enumerate(chiusi):
        for dopo_data, dopo_id, dopo_artifacts in chiusi[indice + 1:]:
            comuni = sorted(prima_artifacts & dopo_artifacts)
            if comuni and dopo_data > prima_data:
                segnali.append({
                    "earlier": prima_id,
                    "later": dopo_id,
                    "artifacts": comuni,
                })
    return segnali


def _ancestors(index: dict[str, dict], node_id: str) -> set[str]:
    """Restituisce tutti i nodi da cui ``node_id`` dipende, direttamente o no."""
    visti: set[str] = set()
    coda = [node_id]
    while coda:
        corrente = coda.pop()
        node = index.get(corrente)
        if node is None:
            continue
        for dipendenza in node.get("blockedBy", ()):
            if dipendenza not in visti:
                visti.add(dipendenza)
                coda.append(dipendenza)
    return visti


def missing_edges(ref: Graph, data: dict) -> list[dict]:
    """Segnala soltanto dipendenze mancanti plausibili.

    Una coppia viene segnalata quando un nodo chiuso piu' tardi condivide un
    artefatto con un nodo precedente, ma non dipende da quel nodo nemmeno per
    via transitiva. La lista degli artefatti e' l'evidenza conservata per ogni
    segnalazione; la diagnosi non propone archi spurii e non modifica il grafo.
    """
    index = {node["id"]: node for node in data.get("nodes", [])}
    return [segnale for segnale in shared_artifacts(ref, data)
            if segnale["earlier"] not in _ancestors(index, segnale["later"])]
