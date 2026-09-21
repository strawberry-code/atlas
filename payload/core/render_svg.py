"""La mappa del grafo: layout a rank e nodi in stile Grafite, assemblati in SVG.

Spezzato da render.py perche' qui c'e' una sola responsabilita', il disegno del
grafo, mentre render.py assembla la pagina attorno; gli archi e le loro regole
di hover stanno in render_edges.py. Nessuna risorsa remota.

Il layout e' quello a rank di layout_rank.py (C08, porta di Nodavia), chiamato
con start=None: le radici sono tutti i nodi senza predecessori, perche' un
grafo Atlas ha piu' rami liberi che convergono dopo, mentre Nodavia e' un
diagramma di flusso a ingresso singolo. Con una radice sola i rami che non ne
discendono finivano marcati come frammenti staccati (vedi il ticket C08).

La card resta un solo <svg>, non un albero di <div> come in React Flow: gli
archi (render_edges.py, A03) si agganciano al bordo del rettangolo e la
mappa intera resta un solo elemento pannabile/zoomabile via CSS transform
(C02). 'rect.card' e' quindi l'unico elemento visivo del nodo che porta la
tinta di stato, ed e' anche il gancio a cui si agganciano le regole generate
da render_edges.hover_css(): cambiarne la classe romperebbe quel file senza
avviso, quindi la card resta un rettangolo con testo intorno, non un
foreignObject. La struttura (eyebrow/id/stato a destra, corpo, footer) e'
quella di customNodes.tsx, tradotta in elementi SVG.

I colori di stato non sono attributi SVG ma classi CSS (st-<stato>, vedi
canvas.css): e' cio' che fa funzionare il tema chiaro/scuro su un file gia'
generato. Ogni nodo porta data-node, che il JavaScript della pagina usa per
aprire la scheda e per selezionarlo (sheet.js); l'href resta come ripiego per
chi naviga senza script.
"""
from __future__ import annotations

from html import escape

from . import layout_rank, render_edge_ghosts, render_edges, render_owners, theme
from .model import owners_of
from .theme import STATE, css_class, state_of

W, H, PAD, PAD_IN = 230, 134, 40, 14


def wrap(text: str, limit: int = 26, lines: int = 3) -> list[str]:
    """Spezza per parola: tagliare a meta' parola rende i titoli illeggibili."""
    righe, corrente = [], ""
    for parola in text.split():
        prova = f"{corrente} {parola}".strip()
        if len(prova) <= limit:
            corrente = prova
            continue
        righe.append(corrente)
        corrente = parola
        if len(righe) == lines:
            break
    if corrente and len(righe) < lines:
        righe.append(corrente)
    if len("".join(righe)) < len(text.replace(" ", "")):
        righe[-1] = righe[-1][: limit - 1] + "…"
    return righe + [""] * (lines - len(righe))


def _trunca(testo: str, n: int) -> str:
    return testo if len(testo) <= n else testo[: n - 1] + "…"


def archi(data: dict) -> tuple[list[str], list[tuple[str, str]]]:
    """Id e archi bloccante->bloccato del grafo, nell'ordine del file: la
    stessa coppia per il layout (positions) e per la classificazione dei
    ritorni (render_edges._edge_records), cosi' i due parlano dello stesso
    grafo con la stessa visita."""
    ids = [n["id"] for n in data["nodes"]]
    validi = set(ids)
    return ids, [(dep, n["id"]) for n in data["nodes"] for dep in n["blockedBy"] if dep in validi]


def positions(data: dict) -> dict[str, tuple[float, float]]:
    """Le posizioni via layout_rank (C08): un arco 'blockedBy' e' un arco
    bloccante->bloccato, come lo legge render_edges.edges()."""
    return layout_rank.layout_positions(*archi(data), start=None)


def _head(node: dict, stato: str, x: float, y: float) -> str:
    """Eyebrow (tipo) a sinistra e stato a destra, come rf-head di
    customNodes.tsx; sotto, l'id in display. Un nodo in lavorazione porta
    l'anello che gira al posto del glifo fermo: e' l'unico stato che descrive
    qualcosa che accade adesso, e il movimento lo dice meglio di un pallino."""
    eyebrow = f'<text class="neyebrow" x="{x + PAD_IN}" y="{y + PAD_IN + 3}">{escape(node["type"])}</text>'
    if stato != "claimed":
        stato_svg = (f'<text class="ndot" x="{x + W - PAD_IN}" y="{y + PAD_IN + 3}" '
                     f'text-anchor="end">{STATE[stato][0]}</text>')
    else:
        stato_svg = (f'<g transform="translate({x + W - PAD_IN - 6},{y + PAD_IN - 1})"><g class="spin">'
                     f'<circle class="spin-arc" r="{theme.RING["r"]}" fill="none" '
                     f'stroke-width="{theme.RING["spessore"]}" stroke-linecap="round" '
                     f'stroke-dasharray="{theme.RING["tratto"]}"/></g></g>')
    nid = f'<text class="nid" x="{x + PAD_IN}" y="{y + PAD_IN + 24}">{escape(node["id"])}</text>'
    return eyebrow + stato_svg + nid


def _footer(node: dict, x: float, y: float) -> str:
    """Modo, assegnatario, costo: gli stessi tre badge del footer di
    customNodes.tsx (modello, runner, costo), qui come un'unica riga di testo
    perche' un pill con lo sfondo richiederebbe misurare il testo a runtime,
    e questa pagina non ha un motore JS per farlo prima del primo paint."""
    pezzi = [node["mode"]]
    assegnatari = owners_of(node)
    if assegnatari:
        pezzi.append(" + ".join(assegnatari))
    costo = node.get("cost")
    if costo:
        pezzi.append(costo)
    testo = _trunca(" · ".join(pezzi), 32)
    return f'<text class="nfoot" x="{x + PAD_IN}" y="{y + H - PAD_IN + 2}">{escape(testo)}</text>'


def boxes(data: dict, pos: dict, front: set[str], gruppi: dict[str, int],
          *, lite: bool = False) -> str:
    out = []
    ordine_rami = list(data["branches"])
    for node in data["nodes"]:
        if node["id"] not in pos:
            continue
        x, y = pos[node["id"]]
        stato = state_of(node, front)
        dash = STATE[stato][2]
        ramo = data["branches"][node["branch"]].get("color", theme.BRANCH_FALLBACK)
        tratto = f' stroke-dasharray="{dash}"' if dash else ""
        titolo = "".join(
            f'<text class="ntt" x="{x + PAD_IN}" y="{y + PAD_IN + 46 + i * 15}">{escape(r)}</text>'
            for i, r in enumerate(wrap(node["title"])) if r
        )
        # la pagina alleggerita (S11/4, render_lite.py) non porta la domanda del
        # nodo nemmeno nel tooltip: e' testo del ticket, non grafo/titoli/stati
        tip = (escape(node["title"]) if lite
               else f'{escape(node["title"])} — {escape(node["question"])}')
        out.append(
            f'<a href="tickets/{node["id"]}.md" data-node="{node["id"]}">'
            f'<g class="n {css_class(stato)}" id="node-{node["id"]}" '
            f'data-branch="{escape(node["branch"])}" '
            f'data-owners="{render_owners.gruppi(node, gruppi)}">'
            f'<title>{tip}</title>'
            f'<rect class="card" x="{x}" y="{y}" width="{W}" height="{H}" rx="14" '
            f'stroke-width="1"{tratto}/>'
            f'<rect class="selring" x="{x + 1.5}" y="{y + 1.5}" width="{W - 3}" height="{H - 3}" '
            f'rx="12.5" fill="none"/>'
            f'{_head(node, stato, x, y)}'
            f'{titolo}'
            f'{_footer(node, x, y)}'
            # la figura del ramo, in basso a destra: l'angolo che il footer lascia
            # libero, perche' il testo del footer parte da sinistra
            f'<g class="bmark" transform="translate({x + W - 26},{y + H - 26}) scale(.66)">'
            f'<path d="{theme.shape_of(ordine_rami.index(node["branch"]))}" fill="{ramo}"/></g>'
            f'</g></a>'
        )
    return "".join(out)


def canvas(data: dict, front_ids: set[str], gruppi: dict[str, int], *, lite: bool = False) -> str:
    """Stile dinamico + <svg> completo, pronti da inserire nella pagina.

    'lite' e' la mappa di render_lite.py (S11/4): stessa disposizione e stessi
    stati, senza la domanda del nodo nel tooltip (vedi boxes()). Il layout a
    rank puo' centrare un ramo a sinistra dell'origine (C08): il viewBox parte
    dal minimo osservato, non da zero, o quel ramo uscirebbe dal disegno."""
    pos = positions(data)
    xs = [x for x, _ in pos.values()]
    ys = [y for _, y in pos.values()]
    origine_x = (min(xs) if xs else 0) - PAD
    origine_y = (min(ys) if ys else 0) - PAD
    larghezza = (max((x + W for x in xs), default=600)) - origine_x + PAD
    altezza = (max((y + H for y in ys), default=200)) - origine_y + PAD
    ids = [n["id"] for n in data["nodes"] if n["id"] in pos]
    return (
        f'<style>{render_edges.hover_css(ids)}{render_edges.branch_css(list(data["branches"]))}'
        f'{render_owners.css(gruppi)}</style>'
        f'<svg viewBox="{origine_x} {origine_y} {larghezza} {altezza}" '
        f'width="{larghezza}" height="{altezza}" xmlns="http://www.w3.org/2000/svg">'
        f'<defs>{render_edges.markers()}</defs>'
        # gli archi vanno prima delle card, non dopo: A03 li vuole dietro ai
        # nodi, e in SVG l'ordine del documento e' l'ordine di disegno. Una
        # card non e' pero' un rettangolo pieno (le '--st-*-bg' di tokens.css
        # portano alfa, cosi' il puntinato del canvas si intravede attraverso
        # una card ferma): senza backings() in mezzo, lo stesso alfa
        # lascerebbe intravedere l'arco vero a piena saturazione, non il filo
        # tenue che ghosts() ridisegna sopra le card, ritagliato card per
        # card, appena visibile (render_edge_ghosts.py).
        # I due contenitori sono il punto d'aggancio di ghosts.js, che li
        # rifa' da capo a ogni trascinamento: qui c'e' solo lo stato a riposo.
        f'{render_edges.edges(data, pos, front_ids)}'
        f'<g class="edge-backings">{render_edge_ghosts.backings(data, pos, front_ids)}</g>'
        f'{boxes(data, pos, front_ids, gruppi, lite=lite)}'
        f'<g class="edge-ghosts">{render_edge_ghosts.ghosts(data, pos, front_ids)}</g>'
        '</svg>'
    )
