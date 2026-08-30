"""Attraversamento del grafo: profondita' topologica, impatto, convergenza.

Spezzato da model.py, che risponde sul singolo nodo (chi e', in che stato, chi lo
blocca): qui si percorrono gli archi, ed e' un lavoro con problemi suoi, cioe' la
profondita' della ricorsione e il costo dei cammini. Le visite sono iterative e
gli indici si costruiscono una volta sola per chi deve interrogare tutto il grafo.
"""
from __future__ import annotations

from .model import blocker_of, by_id, frontier, istante
from .store import DROPPED, StateError
from .strings import t


def levels(graph: dict) -> dict[str, int]:
    """Profondita' topologica: 0 per i nodi liberi, altrimenti 1 + il massimo dei blocker.

    E' anche la sola convalida strutturale che serve a ogni comando: solleva sui cicli.

    La visita e' iterativa, con lo stack sulla heap invece che sulle chiamate: una
    catena di dipendenze abbastanza lunga (misurato: 1500 nodi, e molto meno se
    l'elenco non e' gia' in ordine topologico) faceva sbattere la versione
    ricorsiva contro il limite dell'interprete, e non su un comando solo, perche'
    da qui passano validate, la dashboard e la convergenza.
    """
    index, depth = by_id(graph), {}
    for partenza in graph["nodes"]:
        if partenza["id"] in depth:
            continue
        aperti: set[str] = set()                  # il cammino in corso: se lo si rincontra, e' un ciclo
        stack = [(partenza["id"], False)]
        while stack:
            node_id, risalita = stack.pop()
            node = index[node_id]
            if risalita:
                depth[node_id] = 1 + max((depth[d] for d in node["blockedBy"]), default=-1)
                aperti.discard(node_id)
                continue
            if node_id in depth:
                continue
            if node_id in aperti:
                raise StateError(t("model.ciclo", id=node_id))
            aperti.add(node_id)
            stack.append((node_id, True))
            for dep in node["blockedBy"]:
                blocker = blocker_of(index, node, dep)     # diagnostica l'arco pendente
                if dep in aperti:
                    raise StateError(t("model.ciclo", id=dep))
                if dep not in depth:
                    stack.append((blocker["id"], False))
    return depth


def successors(graph: dict) -> dict[str, list[str]]:
    """Gli archi uscenti di tutto il grafo, in una passata sola.

    blocks() risponde per un nodo alla volta riscandendo ogni nodo: usarlo dentro
    un attraversamento costa il quadrato dei nodi. Chi visita il grafo si costruisce
    questo indice una volta e poi lo consulta.
    """
    uscenti: dict[str, list[str]] = {n["id"]: [] for n in graph["nodes"]}
    for node in graph["nodes"]:
        for dep in node["blockedBy"]:
            if dep in uscenti:
                uscenti[dep].append(node["id"])
    return uscenti


def convergence(graph: dict) -> tuple[str | None, list[str]]:
    """Il presunto nodo finale e i terminali che non vi confluiscono.

    Terminale: nessuno lo aspetta, e non e' fuori scopo. Il finale e' il
    terminale topologicamente piu' profondo (a parita', il primo nel grafo:
    max e' stabile); gli altri terminali sono rami sciolti. Non e' una regola
    del motore, un grafo che non converge resta valido: e' solo un segnale,
    che doctor e dashboard mostrano come avviso.
    """
    depth, uscenti = levels(graph), successors(graph)
    terminali = [n["id"] for n in graph["nodes"]
                 if n["status"] != DROPPED and not uscenti[n["id"]]]
    if len(terminali) < 2:
        return (terminali[0] if terminali else None), []
    end = max(terminali, key=lambda i: depth[i])
    return end, [i for i in terminali if i != end]


def _discendenti(uscenti: dict[str, list[str]], node_id: str) -> set[str]:
    visti: set[str] = set()
    coda = [node_id]
    while coda:
        for succ in uscenti.get(coda.pop(), ()):
            if succ not in visti:
                visti.add(succ)
                coda.append(succ)
    return visti


def downstream(graph: dict, node_id: str) -> set[str]:
    """Tutti i nodi che aspettano, direttamente o no, la chiusura di questo."""
    return _discendenti(successors(graph), node_id)


def closed_downstream_after(graph: dict, node_id: str, after: str) -> list[dict]:
    """Closed dependants of ``node_id`` completed after a question was asked.

    The question can only invalidate work that both depends on its origin and was
    closed later.  Invalid timestamps are deliberately excluded: guessing their
    order would turn a diagnostic into a false positive.
    """
    soglia = istante(after)
    if soglia is None:
        return []
    impacted = downstream(graph, node_id)
    return [node for node in graph["nodes"]
            if node["id"] in impacted
            and node.get("status") == "closed"
            and (closed := istante(node.get("closedAt"))) is not None
            and closed > soglia]


def _cammini_residui(graph: dict, uscenti: dict[str, list[str]]) -> dict[str, int]:
    """Il cammino residuo di ogni nodo, in una passata sola dal fondo verso l'alto.

    La versione ricorsiva ripartiva da capo per ogni successore, quindi il costo
    era il numero di cammini e non quello dei nodi: misurato, un grafo a diamanti
    di 36 nodi teneva 'atlas next' occupato per 0,7 secondi, e ogni due livelli in
    piu' il tempo raddoppiava. Qui ogni nodo si calcola una volta, in ordine di
    profondita' decrescente, cosi' quando tocca a lui i suoi successori sono gia' fatti.
    """
    depth = levels(graph)
    residuo: dict[str, int] = {}
    for node_id in sorted(depth, key=lambda i: depth[i], reverse=True):
        residuo[node_id] = 1 + max((residuo[s] for s in uscenti.get(node_id, ())), default=-1)
    return residuo


def residual_path(graph: dict, node_id: str) -> int:
    """Il piu' lungo cammino di dipendenza da qui fino a un nodo terminale."""
    return _cammini_residui(graph, successors(graph))[node_id]


def ranked_frontier(graph: dict) -> list[tuple[dict, int, int]]:
    """La frontiera ordinata per impatto: quanti nodi sblocca, poi cammino residuo.

    Gli indici si costruiscono una volta per tutta la frontiera: e' il comando che
    un agente lancia per primo, e prima era anche il piu' lento del prodotto.
    """
    uscenti = successors(graph)
    residuo = _cammini_residui(graph, uscenti)
    righe = [(n, len(_discendenti(uscenti, n["id"])), residuo[n["id"]]) for n in frontier(graph)]
    return sorted(righe, key=lambda r: (-r[1], -r[2]))
