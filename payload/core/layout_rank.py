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
archi di ritorno usano uno stack esplicito sulla heap (le visite stanno in
graph_walk.py).
"""
from __future__ import annotations

from .graph_walk import Edge, NodeId, _adjacency, _reachable, _roots, _scc, back_edges

# Il margine fra due card (non il passo, quello si ricava sommando la
# dimensione della card): 40px in orizzontale, 61px in verticale, misurati
# quando la card era 230x134 (issue #34 l'ha allargata a 260x156). Letto da
# render_svg.W/H dentro layout_positions(), mai duplicato come un secondo
# 270/195 che poi diverge dal disegno vero.
X_MARGIN, Y_MARGIN, X_BASE, Y_BASE = 40, 61, 400, 60

def ranks(node_ids: list[NodeId], edges: list[Edge], start: NodeId | None = None) -> dict[NodeId, int]:
    """Il rango di ogni nodo: longest-path sulle componenti fortemente connesse.
    ``start`` esplicito impone un'unica radice (ingresso singolo, come un
    diagramma di flusso). A None le radici sono tutti i nodi senza
    predecessori: un grafo Atlas ha piu' rami liberi che convergono dopo."""
    if not node_ids:
        return {}
    adj = _adjacency(node_ids, edges)
    back = back_edges(node_ids, edges, start)
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
    # import differito: render_svg importa questo modulo a sua volta (C08), un
    # import in testa al file creerebbe un ciclo (stesso schema di render_edges.py)
    from .render_svg import H, W
    x_gap, y_gap = W + X_MARGIN, H + Y_MARGIN
    rank = ranks(node_ids, edges, start)
    by_rank: dict[int, list[NodeId]] = {}
    for i in node_ids:
        by_rank.setdefault(rank[i], []).append(i)
    for r, ids in by_rank.items():
        for col, i in enumerate(ids):
            pos[i] = (X_BASE + (col - (len(ids) - 1) / 2) * x_gap, Y_BASE + r * y_gap)
    return pos
