"""Sola lettura sul grafo: indici, profondita' topologica, frontiera, avanzamento."""
from __future__ import annotations

import hashlib
import json
import re

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


def fingerprint(node: dict) -> str:
    """Impronta del contenuto di un nodo, per accorgersi che e' cambiato sotto le mani.

    Il lock impedisce a due processi di scrivere insieme e la rilettura dentro la
    transazione impedisce di partire da uno stato vecchio, ma nessuno dei due sa cosa
    l'agente aveva letto quando ha deciso cosa scrivere: se la premessa e' cambiata
    mentre lavorava, la sua sintesi entra pulita e poggia sul vuoto. Questa impronta,
    registrata alla presa e riverificata alla chiusura, e' l'unico modo di accorgersene.

    Esclude claim, che cambia a ogni battito senza che il nodo sia diverso. E' un hash
    del contenuto e non un contatore incrementale perche' un contatore vive di
    disciplina: basta una mutazione che si dimentica di alzarlo e il controllo tace
    proprio quando servirebbe.
    """
    corpo = {chiave: valore for chiave, valore in node.items() if chiave != "claim"}
    testo = json.dumps(corpo, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(testo.encode("utf-8")).hexdigest()[:12]


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


def convergence(graph: dict) -> tuple[str | None, list[str]]:
    """Il presunto nodo finale e i terminali che non vi confluiscono.

    Terminale: nessuno lo aspetta, e non e' fuori scopo. Il finale e' il
    terminale topologicamente piu' profondo (a parita', il primo nel grafo:
    max e' stabile); gli altri terminali sono rami sciolti. Non e' una regola
    del motore, un grafo che non converge resta valido: e' solo un segnale,
    che doctor e dashboard mostrano come avviso.
    """
    depth = levels(graph)
    terminali = [n["id"] for n in graph["nodes"]
                 if n["status"] != DROPPED and not blocks(graph, n["id"])]
    if len(terminali) < 2:
        return (terminali[0] if terminali else None), []
    end = max(terminali, key=lambda i: depth[i])
    return end, [i for i in terminali if i != end]


def downstream(graph: dict, node_id: str) -> set[str]:
    """Tutti i nodi che aspettano, direttamente o no, la chiusura di questo."""
    visti: set[str] = set()
    coda = [node_id]
    while coda:
        corrente = coda.pop()
        for succ in blocks(graph, corrente):
            if succ not in visti:
                visti.add(succ)
                coda.append(succ)
    return visti


def residual_path(graph: dict, node_id: str) -> int:
    """Il piu' lungo cammino di dipendenza da qui fino a un nodo terminale."""
    succ = blocks(graph, node_id)
    return 1 + max((residual_path(graph, s) for s in succ), default=-1)


def ranked_frontier(graph: dict) -> list[tuple[dict, int, int]]:
    """La frontiera ordinata per impatto: quanti nodi sblocca, poi cammino residuo."""
    righe = [(n, len(downstream(graph, n["id"])), residual_path(graph, n["id"])) for n in frontier(graph)]
    return sorted(righe, key=lambda r: (-r[1], -r[2]))


def fog_for(graph: dict, node_id: str) -> list[str]:
    """Le voci di nebbia che nominano questo nodo. Confine di parola, non sottostringa:
    cercando B1 non devono uscire le voci che parlano di B10. Copre sia il prefisso
    strutturato scritto da 'fog --for' sia la menzione nel testo libero."""
    confine = re.compile(rf"(?<![0-9A-Za-z_-]){re.escape(node_id)}(?![0-9A-Za-z_-])")
    return [voce for voce in graph.get("fog", []) if confine.search(voce)]
