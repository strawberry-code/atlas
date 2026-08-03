"""Sola lettura sul grafo: indici, profondita' topologica, frontiera, avanzamento."""
from __future__ import annotations

from .store import CLAIMED, CLOSED, DROPPED, OPEN, StateError


def by_id(graph: dict) -> dict[str, dict]:
    return {n["id"]: n for n in graph["nodes"]}


def node_of(graph: dict, node_id: str) -> dict:
    try:
        return by_id(graph)[node_id]
    except KeyError:
        raise StateError(f"{node_id} non esiste nel grafo") from None


def is_done(node: dict) -> bool:
    """Anche un nodo fuori scopo e' soddisfatto: sblocca chi dipendeva da lui."""
    return node["status"] in (CLOSED, DROPPED)


def levels(graph: dict) -> dict[str, int]:
    """Profondita' topologica: 0 per i nodi liberi, altrimenti 1 + il massimo dei blocker.

    E' anche la sola convalida strutturale che serve a ogni comando: solleva sui cicli.
    """
    index, depth = by_id(graph), {}

    def walk(node_id: str, seen: frozenset[str]) -> int:
        if node_id in depth:
            return depth[node_id]
        if node_id in seen:
            raise StateError(f"ciclo di dipendenze su {node_id}")
        deps = index[node_id]["blockedBy"]
        depth[node_id] = 1 + max((walk(d, seen | {node_id}) for d in deps), default=-1)
        return depth[node_id]

    for node in graph["nodes"]:
        walk(node["id"], frozenset())
    return depth


def frontier(graph: dict) -> list[dict]:
    """Aperti con ogni blocker chiuso: il lavoro prendibile adesso."""
    index = by_id(graph)
    return [n for n in graph["nodes"]
            if n["status"] == OPEN and all(is_done(index[d]) for d in n["blockedBy"])]


def blocked(graph: dict) -> list[dict]:
    index = by_id(graph)
    return [n for n in graph["nodes"]
            if n["status"] == OPEN and not all(is_done(index[d]) for d in n["blockedBy"])]


def claimed(graph: dict) -> list[dict]:
    return [n for n in graph["nodes"] if n["status"] == CLAIMED]


def blocks(graph: dict, node_id: str) -> list[str]:
    """Archi uscenti, derivati: chi resta fermo finche' questo nodo non chiude."""
    return [n["id"] for n in graph["nodes"] if node_id in n["blockedBy"]]


def progress(graph: dict) -> tuple[int, int]:
    return sum(1 for n in graph["nodes"] if is_done(n)), len(graph["nodes"])
