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

    Esclude claim, che cambia a ogni battito senza che il nodo sia diverso, e owner,
    che dice di chi e' il pezzo e non cosa c'e' da fare: assegnare un nodo mentre
    qualcuno lo lavora non gli cambia la domanda sotto le mani, e senza questa
    esclusione gli farebbe fallire la chiusura chiedendogli un --force. E' un hash
    del contenuto e non un contatore incrementale perche' un contatore vive di
    disciplina: basta una mutazione che si dimentica di alzarlo e il controllo tace
    proprio quando servirebbe.
    """
    corpo = {chiave: valore for chiave, valore in node.items() if chiave not in ("claim", "owner")}
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
    """Quanto e' finito, sul lavoro che resta da fare.

    Non usa is_done, che comprende anche il fuori scopo: li' la domanda e' 'questo
    nodo sblocca chi lo aspetta', e la risposta e' si'. Qui la domanda e' un'altra,
    e un nodo messo fuori scopo non e' lavoro fatto; siccome pero' non e' nemmeno
    lavoro che resta, esce da tutt'e due i termini invece di pesare come debito
    eterno. Un nodo rivendicato invece resta al denominatore: e' lavoro aperto, e
    toglierlo farebbe salire l'avanzamento a chi prende un nodo senza aver ancora
    chiuso niente.
    """
    in_gioco = [n for n in graph["nodes"] if n["status"] != DROPPED]
    return sum(1 for n in in_gioco if n["status"] == CLOSED), len(in_gioco)


def fog_for(graph: dict, node_id: str) -> list[str]:
    """Le voci di nebbia che nominano questo nodo. Confine di parola, non sottostringa:
    cercando B1 non devono uscire le voci che parlano di B10. Copre sia il prefisso
    strutturato scritto da 'fog --for' sia la menzione nel testo libero."""
    confine = re.compile(rf"(?<![0-9A-Za-z_-]){re.escape(node_id)}(?![0-9A-Za-z_-])")
    return [voce for voce in graph.get("fog", []) if confine.search(voce)]


def owner_of(node: dict) -> str | None:
    """A chi e' assegnato il nodo, None se a nessuno.

    Da non confondere con 'assignee', che dice chi tiene il lucchetto adesso e
    sparisce quando il nodo si rilascia: questo resta finche' qualcuno non lo
    cambia. Si legge con get perche' i grafi nati prima non hanno il campo, e
    'non assegnato' e' uno stato legittimo, non un dato da migrare.
    """
    return node.get("owner") or None


def owners(data: dict) -> dict[str, list[str]]:
    """Chi ha nodi assegnati e quali, in ordine di nome.

    L'ordine e' alfabetico e non di apparizione perche' da qui escono le colonne
    della dashboard: con l'ordine di apparizione un nodo chiuso in mezzo alla
    lista rimescolava i colori delle persone da una resa alla successiva.
    """
    mappa: dict[str, list[str]] = {}
    for node in data["nodes"]:
        if nome := owner_of(node):
            mappa.setdefault(nome, []).append(node["id"])
    return {nome: mappa[nome] for nome in sorted(mappa)}


def unowned(data: dict) -> list[str]:
    return [n["id"] for n in data["nodes"] if not owner_of(n)]


def fog_line(node_id: str, riga: str) -> tuple[str, bool]:
    """La voce indirizzata a un nodo, con il prefisso scritto una volta sola.

    'fog --for X' antepone da se' 'per X: ', e chi scrive la nebbia tende a
    ripetere lo stesso prefisso nel testo: su un grafo reale sono uscite 14 voci
    su 57 con 'per X: per X: ...', scritte in sessioni diverse. E' quel che
    l'interfaccia induce, quindi si assorbe qui invece di chiederlo a chi scrive.

    Il prefisso da riconoscere si ricava dal catalogo, cosi' la guardia segue la
    lingua del progetto invece di inseguire l'italiano a mano; i due punti restano
    opzionali perche' chi scrive a mano li omette quanto li mette. Il confine dopo
    l'id e' lo stesso di fog_for e per la stessa ragione: con --for B1 una voce che
    dice 'per B10' non e' il prefisso di questo nodo. Una riga fatta di solo
    prefisso non lascia testo e non viene toccata: e' una voce vuota, e il
    comportamento resta quello di prima.

    Torna la riga finale e se il prefisso c'era gia', perche' riscrivere il testo
    di chi chiama e' un gesto da dichiarare, non da fare in silenzio."""
    testa, _, coda = t("fog.per", id=node_id, riga="").partition(node_id)
    apertura = rf"{re.escape(testa.strip())}\s+" if testa.strip() else ""
    separatore = rf"\s*(?:{re.escape(coda.strip())})?" if coda.strip() else ""
    gia_scritto = re.compile(
        rf"^\s*{apertura}{re.escape(node_id)}(?![0-9A-Za-z_-]){separatore}\s*", re.IGNORECASE)
    resto = gia_scritto.sub("", riga, count=1)
    if resto != riga and resto.strip():
        return t("fog.per", id=node_id, riga=resto), True
    return t("fog.per", id=node_id, riga=riga), False
