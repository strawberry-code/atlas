"""Il display tattico: layout topologico e track dei nodi, assemblati in SVG.

Spezzato da render.py perche' qui c'e' una sola responsabilita', il disegno del
grafo, mentre render.py assembla la plancia attorno; gli archi e le loro regole
di hover stanno in render_edges.py. Nessuna risorsa remota.
I colori di stato non sono attributi SVG ma classi CSS (st-<stato>, vedi
dashboard.css): e' cio' che fa funzionare il night/day mode su un file gia'
generato. Ogni nodo porta data-node, che il JavaScript della pagina usa per
aprire la scheda; l'href resta come ripiego per chi naviga senza script.
"""
from __future__ import annotations

from html import escape

from . import render_edges, theme
from .strings import t
from .theme import STATE, css_class, state_of

W, H, GAP_X, GAP_Y, PAD = 236, 92, 30, 54, 24
# ritardi dell'animazione d'ingresso: una riga topologica dopo l'altra
DELAY_ROW, DELAY_COL = 0.1, 0.03


def wrap(text: str, limit: int = 27, lines: int = 3) -> list[str]:
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


def layout(data: dict, depth: dict[str, int]) -> dict[str, tuple[float, float]]:
    """Una riga per livello topologico, ogni riga centrata sulla piu' affollata:
    l'albero resta simmetrico e il tronco delle dipendenze si legge al centro."""
    ordine, righe, pos = list(data["branches"]), {}, {}
    for node in data["nodes"]:
        righe.setdefault(depth[node["id"]], []).append(node)
    if not righe:
        return pos
    larga = max(len(n) for n in righe.values())
    campata = larga * W + (larga - 1) * GAP_X
    for livello, nodi in righe.items():
        nodi.sort(key=lambda n: (ordine.index(n["branch"]), n["id"]))
        corsa = len(nodi) * W + (len(nodi) - 1) * GAP_X
        sinistra = PAD + (campata - corsa) / 2
        for colonna, node in enumerate(nodi):
            pos[node["id"]] = (sinistra + colonna * (W + GAP_X), PAD + livello * (H + GAP_Y))
    return pos


def _delay(x: float, y: float) -> str:
    riga = (y - PAD) / (H + GAP_Y)
    colonna = (x - PAD) / (W + GAP_X)
    return f"{riga * DELAY_ROW + colonna * DELAY_COL:.2f}s"


def _reticolo(x: float, y: float) -> str:
    """Quattro staffe angolari attorno a un track di frontiera: il bersaglio
    prioritario del display, quello su cui conviene agganciarsi adesso."""
    b, s = 5, 11  # sbalzo dal bordo e lunghezza del braccio
    angoli = (
        f'M{x - b},{y + s - b} V{y - b} H{x + s - b}',
        f'M{x + W - s + b},{y - b} H{x + W + b} V{y + s - b}',
        f'M{x + W + b},{y + H - s + b} V{y + H + b} H{x + W - s + b}',
        f'M{x + s - b},{y + H + b} H{x - b} V{y + H - s + b}',
    )
    return "".join(f'<path class="ret" d="{d}"/>' for d in angoli)


def boxes(data: dict, pos: dict, front: set[str]) -> str:
    out = []
    for node in data["nodes"]:
        if node["id"] not in pos:
            continue
        x, y = pos[node["id"]]
        stato = state_of(node, front)
        dash = STATE[stato][2]
        ramo = data["branches"][node["branch"]].get("color", theme.BRANCH_FALLBACK)
        tratto = f' stroke-dasharray="{dash}"' if dash else ""
        deps = ", ".join(node["blockedBy"]) or t("render.libero")
        titolo = "".join(
            f'<text class="ntt" x="{x + 16}" y="{y + 42 + i * 15}">{escape(r)}</text>'
            for i, r in enumerate(wrap(node["title"])) if r
        )
        tipo_modo = f'{node["type"]}·{node["mode"]}'
        reticolo = _reticolo(x, y) if stato == "frontier" else ""
        out.append(
            f'<a href="tickets/{node["id"]}.md" data-node="{node["id"]}">'
            f'<g class="n {css_class(stato)}" id="node-{node["id"]}" '
            f'data-branch="{escape(node["branch"])}" style="--d:{_delay(x, y)}">'
            f'<title>{escape(node["title"])} — {escape(node["question"])}</title>'
            f'<rect class="card" x="{x}" y="{y}" width="{W}" height="{H}" rx="3" '
            f'stroke-width="1.2"{tratto}/>'
            f'<rect x="{x}" y="{y}" width="3" height="{H}" fill="{ramo}"/>'
            f'{reticolo}'
            f'<text class="nid" x="{x + 16}" y="{y + 21}">{STATE[stato][0]} {node["id"]}</text>'
            f'<text class="nbadge" x="{x + W - 12}" y="{y + 21}" text-anchor="end">{escape(tipo_modo)}</text>'
            f'{titolo}'
            f'<text class="ndp" x="{x + 16}" y="{y + H - 11}">← {escape(deps)}</text>'
            f'</g></a>'
        )
    return "".join(out)


def canvas(data: dict, depth: dict[str, int], front_ids: set[str]) -> str:
    """Stile dinamico + <svg> completo, pronti da inserire nella plancia."""
    pos = layout(data, depth)
    larghezza = max((x + W for x, _ in pos.values()), default=600) + PAD
    altezza = max((y + H for _, y in pos.values()), default=200) + PAD
    ids = [n["id"] for n in data["nodes"] if n["id"] in pos]
    return (
        f'<style>{render_edges.hover_css(ids)}{render_edges.branch_css(list(data["branches"]))}</style>'
        f'<svg viewBox="0 0 {larghezza} {altezza}" width="{larghezza}" height="{altezza}" '
        'xmlns="http://www.w3.org/2000/svg">'
        f'<defs>{render_edges.markers()}</defs>'
        f'{boxes(data, pos, front_ids)}{render_edges.edges(data, pos, front_ids)}'
        '</svg>'
    )
