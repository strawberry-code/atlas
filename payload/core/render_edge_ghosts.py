"""Copia sfumata degli archi che passano sotto una card.

Spezzato da render_edges.py perche' e' un secondo lavoro, non lo stesso: quel
modulo disegna gli archi veri, questo ne ritaglia solo il filo che serve a
vederli in trasparenza sotto una card. Nessuna geometria propria, riusa
_edge_records() di render_edges.py.
"""
from __future__ import annotations

from .edge_geometry import CORNER
from .render_edges import _edge_records


def ghosts(data: dict, pos: dict, front_ids: set[str]) -> str:
    """render_svg.canvas() disegna gli archi prima dei nodi, cosi' come A03 li
    vuole dietro: ma una card e' un rettangolo pieno (theme.STATE, canvas.css),
    quindi un arco che ci passa sotto sparisce del tutto, non solo si abbassa
    di livello. Qui si ritaglia, nodo per nodo, la sola porzione degli archi in
    avanti (non i loop: loop_lane li tiene gia' fuori dai nodi per costruzione)
    la cui scatola d'ingombro incrocia quella card, e la si ridisegna sopra con
    poca opacita' (.edge-ghost, edges.css): l'effetto e' un filo appena
    visibile in trasparenza, non l'arco intero rimesso in primo piano.

    La scatola d'ingombro e' quella fra i due punti di aggancio (sx,sy)-(ex,ey)
    allargata di CORNER: smooth_step_path scende, piega e risale dentro quel
    rettangolo, non ne esce mai piu' del raggio dell'angolo raccordato.
    Un arco resta escluso dal ritaglio del proprio nodo di partenza o
    d'arrivo: li' l'aggancio tocca il bordo, non passa sotto la card.

    Nota: durante un trascinamento (drag.js) la 'd' vera si ricalcola dal vivo,
    questi ritagli restano quelli calcolati alla generazione della pagina e si
    aggiornano solo al prossimo render: uno scarto visibile solo per la durata
    del trascinamento, non oltre.
    """
    from .render_svg import H, W

    record = [e for e in _edge_records(data, pos, front_ids) if not e["loop"]]
    out = []
    for nid, (nx, ny) in pos.items():
        sotto = [
            e for e in record
            if e["from"] != nid and e["to"] != nid
            and min(e["sx"], e["ex"]) - CORNER < nx + W and max(e["sx"], e["ex"]) + CORNER > nx
            and e["sy"] < ny + H and e["ey"] > ny
        ]
        if not sotto:
            continue
        rami = "".join(f'<path class="{e["classi"]}" d="{e["d"]}"{e["tratto"]}/>' for e in sotto)
        out.append(
            f'<clipPath id="clip-{nid}"><rect x="{nx}" y="{ny}" width="{W}" height="{H}" rx="14"/></clipPath>'
            f'<g class="edge-ghost" clip-path="url(#clip-{nid})">{rami}</g>'
        )
    return "".join(out)
