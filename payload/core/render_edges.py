"""I collegamenti della mappa: archi tra i nodi, porte, marker, hover.

Spezzato da render_svg.py, che disegna i nodi e assembla il canvas: qui vive
solo cio' che collega i nodi. Le costanti geometriche (W, H, PAD, ...) restano
in render_svg.py, che le possiede insieme al layout: questo modulo le importa.
La copia sfumata che passa sotto le card (ghosts(), A03) e' un altro file,
render_edge_ghosts.py, che riusa _edge_records() da qui.
"""
from __future__ import annotations

import re

from .edge_geometry import LOOP_DASH, loop_path, smooth_step_path
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


def _edge_records(data: dict, pos: dict, front_ids: set[str]) -> list[dict]:
    """Geometria e classi di ogni arco, calcolate una volta sola: edges() le
    disegna dietro ai nodi, render_edge_ghosts.ghosts() ne riusa la stessa
    lista per ritagliare la sola porzione che passa sotto una card, senza
    rifare il calcolo dei punti di aggancio.

    Un arco che risale, cioe' il bloccato non sta sotto il blocker nel layout a
    rank (C08: 'un arco che risale e' sempre un ritorno'), non passa dalla
    geometria in avanti (smooth_step_path, porta di Nodavia: A01): prende
    loop_path, la corsia laterale con tratteggio (LOOP_DASH) che lo distingue
    a colpo d'occhio da un arco sano, altrimenti un giro corto in colonna si
    confonderebbe con uno in avanti. loop_lane tiene apposta quella corsia
    fuori dagli altri nodi, quindi 'loop' esce marcato per farlo escludere
    da ghosts().
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
            da = f"da-{stato_di[dep]}"
            loop = ey <= pos[dep][1]
            if not loop:
                d, classi, tratto = smooth_step_path(sx, sy, ex, ey), f"edge {da}", ""
            else:
                d = loop_path(sx, sy, ex, ey)["d"]
                classi, tratto = f"edge loop {da}", f' stroke-dasharray="{LOOP_DASH}"'
            out.append({
                "from": dep, "to": nid, "sx": sx, "sy": sy, "ex": ex, "ey": ey,
                "da": da, "d": d, "classi": classi, "tratto": tratto, "loop": loop,
                "marker": f"url(#tip-{stato_di[dep]})",
            })
    return out


def edges(data: dict, pos: dict, front_ids: set[str]) -> str:
    """Arco ortogonale dal bordo basso del blocker al bordo alto del bloccato,
    con una porta di aggancio (cerchietto) sull'uscita: geometria in
    _edge_records, qui solo il disegno.

    data-from/data-to reggono l'evidenziazione al passaggio del mouse (vedi
    hover_css). Ogni arco porta invece la classe da-<stato> del nodo da cui parte,
    e il CSS gliene da' il colore: le frecce entranti dicono in che stato sono le
    dipendenze senza doverle cercare sulla mappa, e un blocco con tutte le frecce
    verdi e' un blocco pronto. Prima erano colorati gli archi entranti in un nodo
    di frontiera, che di quella lettura era il solo caso gia' risolto.
    """
    out = []
    for e in _edge_records(data, pos, front_ids):
        out.append(
            # data-sx/sy/ex/ey: i due punti di aggancio della geometria non
            # gappata, che il JS non deve riparsare dalla 'd'. Restano gli
            # unici quattro numeri che C10 non tocca mai: quando drag.js
            # sposta un nodo ricalcola 'd' e le cx/cy delle porte, ma questi
            # quattro restano il riferimento "a riposo" per ogni ricalcolo
            # successivo, e per il ripristino del layout automatico.
            f'<path class="{e["classi"]}" data-from="{e["from"]}" data-to="{e["to"]}" '
            f'data-sx="{e["sx"]}" data-sy="{e["sy"]}" data-ex="{e["ex"]}" data-ey="{e["ey"]}"{e["tratto"]} '
            f'd="{e["d"]}" '
            f'marker-end="{e["marker"]}"/>'  # spessore e colore: edges.css
            f'<circle class="port {e["da"]}" data-from="{e["from"]}" data-to="{e["to"]}" '
            f'cx="{e["sx"]}" cy="{e["sy"]}" r="2.6"/>'
        )
    return "".join(out)


def hover_css(ids: list[str]) -> str:
    """Le regole per nodo: attivano archi e porte entranti/uscenti al passaggio
    del mouse sul nodo stesso o sulla sua riga nei pannelli laterali, e in quel
    secondo caso mettono in evidenza anche il nodo. Generate qui perche'
    dipendono dagli id del grafo, a differenza del tema statico (edges.css).

    Sul nodo il segnale e' hover O selezione (':is(:hover,.sel)'): un clic
    (sheet.js/keyboard.js) lo rende persistente oltre il mouseleave, finche'
    non si seleziona un altro nodo o si clicca altrove. Sulla riga del
    pannello resta solo l'hover, che non ha un equivalente di clic.

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
        nodo = f'svg:has(#node-{i}:is(:hover,.sel))'              # mouse sul nodo, o selezionato (clic)
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
    sono dati del grafo; il resto del tema e' statico (edges.css)."""
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
