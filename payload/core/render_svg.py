"""La mappa del grafo: layout topologico e nodi, assemblati in SVG.

Spezzato da render.py perche' qui c'e' una sola responsabilita', il disegno del
grafo, mentre render.py assembla la pagina attorno; gli archi e le loro regole
di hover stanno in render_edges.py. Nessuna risorsa remota.
I colori di stato non sono attributi SVG ma classi CSS (st-<stato>, vedi
dashboard.css): e' cio' che fa funzionare il tema chiaro/scuro su un file gia'
generato. Ogni nodo porta data-node, che il JavaScript della pagina usa per
aprire la scheda; l'href resta come ripiego per chi naviga senza script.
"""
from __future__ import annotations

from html import escape

from . import render_edges, render_owners, theme
from .strings import t
from .theme import STATE, css_class, state_of

W, H, GAP_X, GAP_Y, PAD = 236, 92, 30, 54, 24


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


def _testa(stato: str, node_id: str, x: float, y: float) -> str:
    """Glifo e id in testa alla card. Un nodo in lavorazione porta al posto del glifo
    un anello che gira: e' l'unico stato che descrive qualcosa che sta accadendo
    adesso, e il movimento lo dice meglio di un pallino fermo. Il translate sta sul
    gruppo esterno e la rotazione sul figlio, perche' una transform CSS sullo stesso
    elemento sostituirebbe quella dell'attributo e lo spinner finirebbe nell'angolo."""
    if stato != "claimed":
        return f'<text class="nid" x="{x + 16}" y="{y + 21}">{STATE[stato][0]} {node_id}</text>'
    return (f'<g transform="translate({x + 22},{y + 16})"><g class="spin">'
            f'<circle class="spin-arc" r="{theme.RING["r"]}" fill="none" '
            f'stroke-width="{theme.RING["spessore"]}" stroke-linecap="round" '
            f'stroke-dasharray="{theme.RING["tratto"]}"/></g></g>'
            f'<text class="nid" x="{x + 32}" y="{y + 21}">{node_id}</text>')


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
        deps = ", ".join(node["blockedBy"]) or t("render.libero")
        titolo = "".join(
            f'<text class="ntt" x="{x + 16}" y="{y + 42 + i * 15}">{escape(r)}</text>'
            for i, r in enumerate(wrap(node["title"])) if r
        )
        tipo_modo = f'{node["type"]}·{node["mode"]}'
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
            f'<rect class="card" x="{x}" y="{y}" width="{W}" height="{H}" rx="3" '
            f'stroke-width="1"{tratto}/>'
            # la figura del ramo, in basso a destra: l'angolo che resta libero
            # perche' i bloccanti si scrivono in basso a sinistra
            f'<g class="bmark" transform="translate({x + W - 26},{y + H - 26}) scale(.66)">'
            f'<path d="{theme.shape_of(ordine_rami.index(node["branch"]))}" fill="{ramo}"/></g>'
            f'{_testa(stato, node["id"], x, y)}'
            f'<text class="nbadge" x="{x + W - 12}" y="{y + 21}" text-anchor="end">{escape(tipo_modo)}</text>'
            f'{titolo}'
            f'<text class="ndp" x="{x + 16}" y="{y + H - 11}">← {escape(deps)}</text>'
            f'</g></a>'
        )
    return "".join(out)


def canvas(data: dict, depth: dict[str, int], front_ids: set[str],
           gruppi: dict[str, int], *, lite: bool = False) -> str:
    """Stile dinamico + <svg> completo, pronti da inserire nella pagina.

    'lite' e' la mappa di render_lite.py (S11/4): stessa disposizione e stessi
    stati, senza la domanda del nodo nel tooltip (vedi boxes())."""
    pos = layout(data, depth)
    larghezza = max((x + W for x, _ in pos.values()), default=600) + PAD
    altezza = max((y + H for _, y in pos.values()), default=200) + PAD
    ids = [n["id"] for n in data["nodes"] if n["id"] in pos]
    return (
        f'<style>{render_edges.hover_css(ids)}{render_edges.branch_css(list(data["branches"]))}'
        f'{render_owners.css(gruppi)}</style>'
        f'<svg viewBox="0 0 {larghezza} {altezza}" width="{larghezza}" height="{altezza}" '
        'xmlns="http://www.w3.org/2000/svg">'
        f'<defs>{render_edges.markers()}</defs>'
        f'{boxes(data, pos, front_ids, gruppi, lite=lite)}{render_edges.edges(data, pos, front_ids)}'
        '</svg>'
    )
