"""Auto-layout gerarchico a rank, porta di ~/nodavia/web/src/editor/layout.ts.

Rango longest-path, non profondita' BFS: un nodo sta sotto il piu' basso dei
suoi predecessori, non sotto il primo che lo raggiunge. Compra l'invariante
che regge la lettura del canvas: un arco che risale e' SEMPRE un ritorno. Col
BFS un arco in avanti poteva risalire (un ramo di scarto raggiungeva subito
un nodo che la pipeline raggiungeva solo molto dopo) e diventava indistin-
guibile da un arco di ritorno.

Il longest-path da solo non basta con un ciclo: togliendo gli archi di
ritorno il ciclo si appiattisce, e chi ne esce sembra un fratello di chi ci
sta dentro. I ranghi si calcolano quindi sulle componenti fortemente connesse
(Tarjan): una componente occupa tutte le righe che le servono, chi la segue
parte SOTTO l'ultima. Nessuna ricorsione: Tarjan e la classificazione degli
archi di ritorno usano uno stack esplicito sulla heap.
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

def ranks(node_ids: list[NodeId], edges: list[Edge], start: NodeId | None = None) -> dict[NodeId, int]:
    """Il rango di ogni nodo: longest-path sulle componenti fortemente connesse.
    ``start`` esplicito impone un'unica radice (ingresso singolo, come un
    diagramma di flusso). A None le radici sono tutti i nodi senza
    predecessori: un grafo Atlas ha piu' rami liberi che convergono dopo."""
    if not node_ids:
        return {}
    adj = _adjacency(node_ids, edges)
    ancora = start if start is not None else node_ids[0]
    back = _back_edges(node_ids, adj, ancora)
    succ = {i: [v for v in vs if (i, v) not in back] for i, vs in adj.items()}
    comp, n_comp = _scc(node_ids, adj)
    membri: dict[int, list[NodeId]] = {}
    for i in node_ids:
        membri.setdefault(comp[i], []).append(i)
    rank = {i: 0 for i in node_ids}
    floor_of: dict[int, int] = {}
    # Le componenti escono da Tarjan in ordine topologico inverso: si scorrono a
    # ritroso per lavorarle in ordine topologico, cosi' quando tocca a una
    # componente il suo pavimento e' gia' completo (lo hanno alzato i predecessori).
    for c in range(n_comp - 1, -1, -1):
        ids = membri.get(c, [])
        dentro = set(ids)
        locale = {i: 0 for i in ids}
        indeg = {i: 0 for i in ids}
        for u in ids:
            for v in succ[u]:
                if v in dentro:
                    indeg[v] += 1
        coda = [i for i in ids if indeg[i] == 0]
        while coda:
            u = coda.pop(0)
            for v in succ[u]:
                if v not in dentro:
                    continue
                locale[v] = max(locale[v], locale[u] + 1)
                indeg[v] -= 1
                if indeg[v] == 0:
                    coda.append(v)
        base = floor_of.get(c, 0)
        alto = 0
        for i in ids:
            rank[i] = base + locale[i]
            alto = max(alto, locale[i])
        sotto = base + alto + 1
        for u in ids:
            for v in adj[u]:
                cv = comp[v]
                if cv != c:
                    floor_of[cv] = max(floor_of.get(cv, 0), sotto)

    # Chi non e' raggiungibile da nessuna radice scende sotto tutto il resto,
    # conservando il proprio ordine relativo: e' un frammento staccato.
    radici = [start] if start is not None else (_roots(node_ids, adj) or [node_ids[0]])
    seen = _reachable(adj, radici)
    orphans = [i for i in node_ids if i not in seen]
    if orphans:
        piano = max((rank[i] for i in node_ids if i in seen), default=0) + 1
        for i in orphans:
            rank[i] = piano + rank[i]
    return rank

def layout_positions(node_ids: list[NodeId], edges: list[Edge],
                      start: NodeId | None = None) -> dict[NodeId, tuple[float, float]]:
    """Posizioni x/y: un rango per riga, nodi centrati nell'ordine di ``node_ids``."""
    pos: dict[NodeId, tuple[float, float]] = {}
    if not node_ids:
        return pos
    rank = ranks(node_ids, edges, start)
    by_rank: dict[int, list[NodeId]] = {}
    for i in node_ids:
        by_rank.setdefault(rank[i], []).append(i)
    for r, ids in by_rank.items():
        for col, i in enumerate(ids):
            pos[i] = (X_BASE + (col - (len(ids) - 1) / 2) * X_GAP, Y_BASE + r * Y_GAP)
    return pos
