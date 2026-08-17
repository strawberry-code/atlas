"""Sola lettura sul singolo nodo: indici, stato, frontiera, avanzamento.

L'attraversamento del grafo (profondita', impatto, convergenza) sta in
topology.py: qui non si percorrono archi oltre il primo salto."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime

from .store import CLAIMED, CLOSED, DROPPED, OPEN, StateError
from .strings import t


def istante(testo: str | None) -> datetime | None:
    """Un timestamp del grafo reso confrontabile, o None se non si legge.

    closedAt lo scrive il motore in ISO col fuso, ma il grafo e' un file di testo
    versionato: dentro ci finiscono anche date scritte a mano ('ieri', oppure un
    '2026-01-02' senza fuso come quello di meta.updated). La prima faceva morire
    doctor con ValueError, la seconda con TypeError sul confronto fra un istante
    con fuso e uno senza. Qui una data senza fuso si legge come ora locale, e
    quel che resta illeggibile vale come 'non lo so': tocca a chi chiama decidere
    cosa fare di quel non-so.
    """
    try:
        letto = datetime.fromisoformat(testo)
    except (ValueError, TypeError):
        return None
    return letto if letto.tzinfo else letto.astimezone()


def by_id(graph: dict) -> dict[str, dict]:
    return {n["id"]: n for n in graph["nodes"]}


def node_of(graph: dict, node_id: str) -> dict:
    try:
        return by_id(graph)[node_id]
    except KeyError:
        raise StateError(t("model.nodo_inesistente", id=node_id)) from None


def blocker_of(index: dict[str, dict], node: dict, dep: str) -> dict:
    """Il blocker di un nodo, o la diagnosi se il grafo lo nomina senza averlo.

    Un arco verso un id che non esiste arriva da un graph.json scritto a mano o
    da un merge mal risolto, ed e' proprio lo stato in cui si va a cercare aiuto.
    Senza questa rete ogni lettura del grafo muore con un KeyError nudo: non solo
    i comandi di lavoro, ma anche doctor, cioe' l'attrezzo che dovrebbe dire cosa
    si e' rotto. Il messaggio e' lo stesso che da' 'validate', perche' il difetto
    e' lo stesso e la cura pure.
    """
    try:
        return index[dep]
    except KeyError:
        raise StateError(t("mutate.dipendenza_inesistente", id=node["id"], dep=dep)) from None


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


def frontier(graph: dict) -> list[dict]:
    """Aperti con ogni blocker chiuso: il lavoro prendibile adesso."""
    index = by_id(graph)
    return [n for n in graph["nodes"]
            if n["status"] == OPEN and all(is_done(blocker_of(index, n, d)) for d in n["blockedBy"])]


def blocked(graph: dict) -> list[dict]:
    index = by_id(graph)
    return [n for n in graph["nodes"]
            if n["status"] == OPEN and not all(is_done(blocker_of(index, n, d)) for d in n["blockedBy"])]


def claimed(graph: dict) -> list[dict]:
    return [n for n in graph["nodes"] if n["status"] == CLAIMED]


def blocks(graph: dict, node_id: str) -> list[str]:
    """Archi uscenti, derivati: chi resta fermo finche' questo nodo non chiude."""
    return [n["id"] for n in graph["nodes"] if node_id in n["blockedBy"]]


def progress(graph: dict) -> tuple[int, int]:
    return sum(1 for n in graph["nodes"] if is_done(n)), len(graph["nodes"])


def fog_for(graph: dict, node_id: str) -> list[str]:
    """Le voci di nebbia che nominano questo nodo. Confine di parola, non sottostringa:
    cercando B1 non devono uscire le voci che parlano di B10. Copre sia il prefisso
    strutturato scritto da 'fog --for' sia la menzione nel testo libero."""
    confine = re.compile(rf"(?<![0-9A-Za-z_-]){re.escape(node_id)}(?![0-9A-Za-z_-])")
    return [voce for voce in graph.get("fog", []) if confine.search(voce)]
