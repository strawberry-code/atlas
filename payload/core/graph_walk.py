"""Le visite del grafo che reggono il layout a rank: adiacenza, archi di
ritorno (DFS bianco/grigio/nero), componenti fortemente connesse (Tarjan),
raggiungibilita' e radici. Spezzato da layout_rank.py, che le usa per
calcolare i ranghi; render_edges.py usa back_edges() per decidere quale arco
disegnare come ritorno. Nessuna ricorsione: ogni visita usa uno stack
esplicito sulla heap, perche' una catena lunga sbatteva contro il limite
dell'interprete.
"""
from __future__ import annotations

NodeId = str
Edge = tuple[NodeId, NodeId]  # (source, target)

X_GAP, Y_GAP, X_BASE, Y_BASE = 270, 195, 400, 60

def _adjacency(node_ids: list[NodeId], edges: list[Edge]) -> dict[NodeId, list[NodeId]]:
    adj: dict[NodeId, list[NodeId]] = {i: [] for i in node_ids}
    for src, dst in edges:
        if src in adj and dst in adj:
            adj[src].append(dst)
    return adj

def _back_edges(node_ids: list[NodeId], adj: dict[NodeId, list[NodeId]], start: NodeId) -> set[Edge]:
    """DFS bianco/grigio/nero: grigio-su-grigio e' un arco di ritorno. Si parte
    da ``start`` per un ordine di visita stabile, poi gli altri nodi in ordine."""
    color = {i: 0 for i in node_ids}  # 0 bianco, 1 grigio, 2 nero
    back: set[Edge] = set()
    ordine = [start] + [i for i in node_ids if i != start]
    for radice in ordine:
        if color[radice] != 0:
            continue
        color[radice] = 1
        stack = [(radice, iter(adj.get(radice, ())))]
        while stack:
            u, it = stack[-1]
            avanzato = False
            for v in it:
                if color.get(v, 0) == 1:
                    back.add((u, v))
                elif color.get(v, 0) == 0:
                    color[v] = 1
                    stack.append((v, iter(adj.get(v, ()))))
                    avanzato = True
                    break
            if not avanzato:
                stack.pop()
                color[u] = 2
    return back

def _scc(node_ids: list[NodeId], adj: dict[NodeId, list[NodeId]]) -> tuple[dict[NodeId, int], int]:
    """Tarjan iterativo: lo stack di lavoro porta (nodo, iteratore-dei-vicini)
    per sospendere e riprendere una visita senza ricorsione. Gli indici escono
    in ordine topologico inverso (component 0 e' un pozzo)."""
    index: dict[NodeId, int] = {}
    low: dict[NodeId, int] = {}
    on_stack: set[NodeId] = set()
    tstack: list[NodeId] = []
    comp: dict[NodeId, int] = {}
    nxt = 0
    n_comp = 0
    for radice in node_ids:
        if radice in index:
            continue
        index[radice] = low[radice] = nxt
        nxt += 1
        tstack.append(radice)
        on_stack.add(radice)
        work = [(radice, iter(adj.get(radice, ())))]
        while work:
            u, it = work[-1]
            avanzato = False
            for v in it:
                if v not in index:
                    index[v] = low[v] = nxt
                    nxt += 1
                    tstack.append(v)
                    on_stack.add(v)
                    work.append((v, iter(adj.get(v, ()))))
                    avanzato = True
                    break
                if v in on_stack:
                    low[u] = min(low[u], index[v])
            if avanzato:
                continue
            work.pop()
            if work:
                genitore = work[-1][0]
                low[genitore] = min(low[genitore], low[u])
            if low[u] == index[u]:
                while True:
                    w = tstack.pop()
                    on_stack.discard(w)
                    comp[w] = n_comp
                    if w == u:
                        break
                n_comp += 1
    return comp, n_comp

def _reachable(adj: dict[NodeId, list[NodeId]], seeds: list[NodeId]) -> set[NodeId]:
    seen = set(seeds)
    stack = list(seeds)
    while stack:
        for v in adj.get(stack.pop(), ()):
            if v not in seen:
                seen.add(v)
                stack.append(v)
    return seen

def _roots(node_ids: list[NodeId], adj: dict[NodeId, list[NodeId]]) -> list[NodeId]:
    """Nodi senza archi entranti: le radici vere, una per ramo libero in Atlas."""
    incoming = {i: 0 for i in node_ids}
    for v in (v for vs in adj.values() for v in vs):
        incoming[v] += 1
    return [i for i in node_ids if incoming[i] == 0]

def back_edges(node_ids: list[NodeId], edges: list[Edge], start: NodeId | None = None) -> set[Edge]:
    """Gli archi di ritorno del grafo, con la stessa visita e la stessa
    radice di ranks(): e' l'unica definizione di 'ritorno' che il canvas
    conosce. render_edges li disegna con la corsia laterale, e un arco che
    non sta qui e' in avanti anche se chi trascina le card lo fa risalire:
    la forma del disegno non cambia la struttura del grafo."""
    if not node_ids:
        return set()
    adj = _adjacency(node_ids, edges)
    return _back_edges(node_ids, adj, start if start is not None else node_ids[0])
