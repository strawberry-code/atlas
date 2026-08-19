"""I collegamenti della mappa: archi tra i nodi, porte, marker, hover.

Spezzato da render_svg.py, che disegna i nodi e assembla il canvas: qui vive
solo cio' che collega i nodi. Le costanti geometriche (W, H, PAD, ...) restano
in render_svg.py, che le possiede insieme al layout: questo modulo le importa.
"""
from __future__ import annotations

import re

from .theme import STATE, state_of

# le chiavi di ramo sono dati liberi ma finiscono in un selettore: una chiave
# fuori da questo alfabeto semplicemente non genera la sua regola di hover
_CHIAVE_SICURA = re.compile(r"^[\w-]+$")


def _slots(ids: list[str], pos: dict, box_x: float, larghezza: float) -> dict[str, float]:
    """Distribuisce i punti di aggancio equidistanti sul bordo di un box, ordinati
    per la x del nodo collegato: cosi' due o piu' archi che condividono lo stesso
    bordo (piu' input o piu' output sullo stesso nodo) non si sovrappongono mai.
    """
    if not ids:
        return {}
    if len(ids) == 1:
        return {ids[0]: box_x + larghezza / 2}
    ordinati = sorted(ids, key=lambda i: pos[i][0])
    margine = larghezza * 0.16
    utile = larghezza - 2 * margine
    return {i: box_x + margine + utile * k / (len(ordinati) - 1) for k, i in enumerate(ordinati)}


def edges(data: dict, pos: dict, front_ids: set[str]) -> str:
    """Bezier verticale dal bordo basso del blocker al bordo alto del bloccato,
    con una porta di aggancio (cerchietto) a ogni estremo.

    data-from/data-to reggono l'evidenziazione al passaggio del mouse (vedi
    hover_css). Ogni arco porta invece la classe da-<stato> del nodo da cui parte,
    e il CSS gliene da' il colore: le frecce entranti dicono in che stato sono le
    dipendenze senza doverle cercare sulla mappa, e un blocco con tutte le frecce
    verdi e' un blocco pronto. Prima erano colorati gli archi entranti in un nodo
    di frontiera, che di quella lettura era il solo caso gia' risolto.
    """
    from .render_svg import H, W

    stato_di = {n["id"]: state_of(n, front_ids) for n in data["nodes"] if n["id"] in pos}
    deps_per_nodo = {
        node["id"]: [d for d in node["blockedBy"] if d in pos]
        for node in data["nodes"] if node["id"] in pos
    }
    uscenti: dict[str, list[str]] = {}
    for nid, deps in deps_per_nodo.items():
        for dep in deps:
            uscenti.setdefault(dep, []).append(nid)

    punti_uscita = {i: _slots(uscenti.get(i, []), pos, x, W) for i, (x, _) in pos.items()}
    punti_entrata = {nid: _slots(deps, pos, pos[nid][0], W) for nid, deps in deps_per_nodo.items()}

    out = []
    for nid, deps in deps_per_nodo.items():
        ey = pos[nid][1]
        for dep in deps:
            sy = pos[dep][1] + H
            sx, ex = punti_uscita[dep][nid], punti_entrata[nid][dep]
            gap = ey - sy
            mid = sy + gap / 2
            piede = min(14, gap / 3)  # tratto retto finale: orientamento del marker inequivocabile
            da = f"da-{stato_di[dep]}"
            out.append(
                f'<path class="edge {da}" data-from="{dep}" data-to="{nid}" '
                f'd="M{sx},{sy} C{sx},{mid} {ex},{mid} {ex},{ey - piede} L{ex},{ey}" '
                f'marker-end="url(#tip-{stato_di[dep]})"/>'  # spessore e colore: dashboard.css
                f'<circle class="port {da}" data-from="{dep}" data-to="{nid}" cx="{sx}" cy="{sy}" r="2.6"/>'
            )
    return "".join(out)


def hover_css(ids: list[str]) -> str:
    """Le regole per nodo: attivano archi e porte entranti/uscenti al passaggio
    del mouse sul nodo stesso o sulla sua riga nei pannelli laterali, e in quel
    secondo caso mettono in evidenza anche il nodo. Generate qui perche'
    dipendono dagli id del grafo, a differenza del tema statico (dashboard.css).

    L'evidenziazione ingrossa la linea e non la ricolora. Prima dipingeva di verde
    gli entranti e di rosso gli uscenti, e su un arco che porta gia' il colore del
    proprio mittente quel verde cancellava proprio l'informazione che si era andati
    a cercare: il mouse su un blocco serve a sapere in che stato sono le dipendenze,
    e le trovava tutte verdi. Entrata e uscita restano distinguibili senza colore:
    gli archi entranti arrivano sul bordo alto e vengono da mittenti diversi, quelli
    uscenti partono dal bordo basso e hanno tutti la tinta del nodo sotto il mouse.
    """
    out = []
    for i in ids:
        nodo = f'svg:has(#node-{i}:hover)'                       # mouse sul nodo
        riga = f'body:has(.side [data-node="{i}"]:hover)'        # mouse sulla riga del pannello
        out.append(
            f'{nodo} :is(path,circle)[data-to="{i}"],{riga} :is(path,circle)[data-to="{i}"],'
            f'{nodo} :is(path,circle)[data-from="{i}"],{riga} :is(path,circle)[data-from="{i}"]'
            f'{{opacity:1}}'
            f'{nodo} path[data-to="{i}"],{riga} path[data-to="{i}"],'
            f'{nodo} path[data-from="{i}"],{riga} path[data-from="{i}"]{{stroke-width:2.6}}'
            f'{riga} #node-{i}{{opacity:1}}'
            f'{riga} #node-{i} rect.card{{stroke-width:2.2}}'
        )
    return "".join(out)


def branch_css(keys: list[str]) -> str:
    """Una regola per ramo: il mouse sulla riga del pannello rami accende sulla
    mappa i soli nodi di quel ramo. Generata qui perche' i rami, come gli id,
    sono dati del grafo; il resto del tema e' statico (dashboard.css)."""
    out = []
    for k in keys:
        if not _CHIAVE_SICURA.match(k):
            continue
        sel = f'body:has(.side li[data-branch="{k}"]:hover)'
        out.append(
            f'{sel} .map .n:not([data-branch="{k}"]){{opacity:.13}}'
            f'{sel} .map :is(path.edge,circle.port){{opacity:.25}}'
        )
    return "".join(out)


def markers() -> str:
    """Le punte delle frecce. Una per stato di partenza, oltre alle due dell'hover:
    un marker non eredita il colore del path che lo usa, e una linea colorata con la
    punta grigia direbbe la meta' di quel che deve dire. Cinque punte in piu' nei defs
    costano nulla; context-stroke lo farebbe in una sola, ma non su tutti i browser.
    """
    def marker(nome: str) -> str:
        return (
            f'<marker id="{nome}" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" '
            f'markerHeight="7" orient="auto"><path class="{nome}" d="M0,1 L7,4 L0,7 z"/></marker>'
        )
    return marker("tip") + "".join(marker(f"tip-{s}") for s in STATE)
