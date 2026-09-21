"""Cio' che serve a tenere gli archi davvero dietro a una card translucida.

Spezzato da render_edges.py perche' e' un secondo lavoro, non lo stesso: quel
modulo disegna gli archi veri, questo si occupa di cosa succede dove una card
ci sta sopra. Nessuna geometria propria, riusa _edge_records() di
render_edges.py.
"""
from __future__ import annotations

from .edge_geometry import CORNER
from .render_edges import _edge_records


def _sotto_per_nodo(data: dict, pos: dict, front_ids: set[str]) -> dict[str, list[dict]]:
    """Per ogni nodo, gli archi in avanti (non i loop: loop_lane li tiene gia'
    fuori dai nodi per costruzione) la cui scatola d'ingombro incrocia la sua
    card - condiviso da backings() e ghosts(), stesso filtro per entrambe.

    La scatola d'ingombro e' quella fra i due punti di aggancio (sx,sy)-(ex,ey)
    allargata di CORNER: smooth_step_path scende, piega e risale dentro quel
    rettangolo, non ne esce mai piu' del raggio dell'angolo raccordato.
    Un arco resta escluso dal calcolo del proprio nodo di partenza o d'arrivo:
    li' l'aggancio tocca il bordo, non passa sotto la card.
    """
    from .render_svg import H, W

    record = [e for e in _edge_records(data, pos, front_ids) if not e["loop"]]
    mappa = {}
    for nid, (nx, ny) in pos.items():
        sotto = [
            e for e in record
            if e["from"] != nid and e["to"] != nid
            and min(e["sx"], e["ex"]) - CORNER < nx + W and max(e["sx"], e["ex"]) + CORNER > nx
            and e["sy"] < ny + H and e["ey"] > ny
        ]
        if sotto:
            mappa[nid] = sotto
    return mappa


def backings(data: dict, pos: dict, front_ids: set[str]) -> str:
    """Il piano opaco fra gli archi e le card che ne hanno uno dietro.

    render_svg.canvas() disegna gli archi prima dei nodi, cosi' come A03 li
    vuole dietro: ma il fondo di una card non e' un colore pieno (theme.STATE,
    tokens.css: '--st-<stato>-bg' porta alfa, cosi' il puntinato del canvas si
    intravede attraverso una card ferma, l'effetto voluto). Senza un piano
    opaco proprio, lo stesso alfa lascerebbe intravedere anche l'arco vero a
    piena saturazione, non il filo tenue di ghosts() qui sotto: un regresso
    rispetto a prima di A03, quando gli archi stavano sopra le card e la
    translucidita' non li toccava mai. Questo rettangolo, dipinto fra gli
    archi e le card (solo sotto quelle che ne hanno uno dietro: le altre non
    ne hanno bisogno, restano translucide come sempre), sostituisce li' il
    puntinato con lo sfondo piatto del canvas: la card ci si tinge sopra come
    sempre, l'arco vero sotto sparisce per davvero.
    """
    from .render_svg import H, W

    return "".join(
        f'<rect class="edge-backing" x="{pos[nid][0]}" y="{pos[nid][1]}" width="{W}" height="{H}" rx="14"/>'
        for nid in _sotto_per_nodo(data, pos, front_ids)
    )


def ghosts(data: dict, pos: dict, front_ids: set[str]) -> str:
    """Copia sfumata degli archi che passano sotto una card: ritagliata,
    nodo per nodo, sulla sola porzione dentro la sua scatola d'ingombro
    (_sotto_per_nodo) e ridisegnata sopra con poca opacita' (.edge-ghost path,
    edges.css) - l'effetto e' un filo appena visibile in trasparenza, non
    l'arco intero rimesso in primo piano.

    'data-ghost-from'/'data-ghost-to' portano lo stesso mittente/bersaglio
    dell'arco vero, ma con un nome diverso da 'data-from'/'data-to' apposta:
    quella coppia e' cio' che drag.js usa per selezionare gli archi veri da
    ricalcolare al volo ('path.edge[data-from]'), e un ghost preso in quel
    giro finirebbe con una 'd' di NaN (non porta data-sx/sy/ex/ey da cui
    ripartire), invisibile a qualunque opacita' (bug osservato in S13/10).
    render_edges.hover_css() li legge per accendere anche il ghost quando il
    suo arco e' quello selezionato, non solo l'arco vero.

    Questo e' lo stato a riposo: a ogni trascinamento (drag.js) ghosts.js
    rifa' backing e ritagli con la stessa regola di _sotto_per_nodo, sulle
    posizioni correnti. Prima restavano quelli calcolati qui e la
    trasparenza rimaneva ferma dove la card era stata generata.
    """
    from .render_svg import H, W

    out = []
    for nid, sotto in _sotto_per_nodo(data, pos, front_ids).items():
        nx, ny = pos[nid]
        rami = "".join(
            f'<path class="{e["classi"]}" data-ghost-from="{e["from"]}" data-ghost-to="{e["to"]}" '
            f'd="{e["d"]}"{e["tratto"]}/>' for e in sotto
        )
        out.append(
            f'<clipPath id="clip-{nid}"><rect x="{nx}" y="{ny}" width="{W}" height="{H}" rx="14"/></clipPath>'
            f'<g class="edge-ghost" clip-path="url(#clip-{nid})">{rami}</g>'
        )
    return "".join(out)
