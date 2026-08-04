"""Il grafo disegnato in SVG: layout topologico, archi, card dei nodi.

Spezzato da render.py perche' qui c'e' una sola responsabilita', il disegno
del grafo, mentre render.py assembla la pagina (pannelli laterali, header,
footer). Nessuna dipendenza esterna e nessuna risorsa remota: niente rete e
niente javascript, l'evidenziazione al passaggio del mouse e' pura CSS
:has() sull'id del nodo (vedi hover_css).
"""
from __future__ import annotations

from html import escape

from . import theme
from .strings import t
from .theme import STATE, state_of

W, H, GAP_X, GAP_Y, PAD = 236, 92, 26, 48, 24


def wrap(text: str, limit: int = 30, lines: int = 3) -> list[str]:
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
    """Una riga per livello topologico, ogni riga centrata sulla piu' affollata."""
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


def _slots(ids: list[str], pos: dict, box_x: float) -> dict[str, float]:
    """Distribuisce i punti di aggancio equidistanti sul bordo di un box, ordinati
    per la x del nodo collegato: cosi' due o piu' archi che condividono lo stesso
    bordo (piu' input o piu' output sullo stesso nodo) non si sovrappongono mai.
    """
    if not ids:
        return {}
    if len(ids) == 1:
        return {ids[0]: box_x + W / 2}
    ordinati = sorted(ids, key=lambda i: pos[i][0])
    margine = W * 0.16
    utile = W - 2 * margine
    return {i: box_x + margine + utile * k / (len(ordinati) - 1) for k, i in enumerate(ordinati)}


def edges(data: dict, pos: dict) -> str:
    """Bezier verticale dal bordo basso del blocker al bordo alto del bloccato.

    data-from/data-to reggono l'evidenziazione al passaggio del mouse (vedi
    hover_css): nessun javascript, solo selettori CSS :has() sull'id del nodo.
    I punti di uscita/entrata sui bordi condivisi passano da _slots, non dal
    centro del box, per non far accavallare gli archi quando un nodo ha piu'
    di un input o un output.
    """
    deps_per_nodo = {
        node["id"]: [d for d in node["blockedBy"] if d in pos]
        for node in data["nodes"] if node["id"] in pos
    }
    uscenti: dict[str, list[str]] = {}
    for nid, deps in deps_per_nodo.items():
        for dep in deps:
            uscenti.setdefault(dep, []).append(nid)

    punti_uscita = {i: _slots(uscenti.get(i, []), pos, x) for i, (x, _) in pos.items()}
    punti_entrata = {nid: _slots(deps, pos, pos[nid][0]) for nid, deps in deps_per_nodo.items()}

    out = []
    for nid, deps in deps_per_nodo.items():
        ey = pos[nid][1]
        for dep in deps:
            sy = pos[dep][1] + H
            sx, ex = punti_uscita[dep][nid], punti_entrata[nid][dep]
            gap = ey - sy
            mid = sy + gap / 2
            piede = min(14, gap / 3)  # tratto retto finale: orientamento del marker inequivocabile
            out.append(
                f'<path class="edge" data-from="{dep}" data-to="{nid}" '
                f'd="M{sx},{sy} C{sx},{mid} {ex},{mid} {ex},{ey - piede} L{ex},{ey}" fill="none" '
                f'stroke="{theme.EDGE}" stroke-width="1.4" marker-end="url(#tip)"/>'
            )
    return "".join(out)


def hover_css(ids: list[str]) -> str:
    """Una coppia di regole per nodo: attivano archi entranti/uscenti al passaggio
    del mouse su quel nodo. Generata qui perche' dipende dagli id del grafo,
    a differenza del resto del tema che e' statico (vedi theme.CSS).
    """
    return "".join(
        f'svg:has(#node-{i}:hover) path[data-to="{i}"]{{stroke:#16a34a;stroke-width:2.2;'
        f'opacity:1;marker-end:url(#tip-in)}}'
        f'svg:has(#node-{i}:hover) path[data-from="{i}"]{{stroke:#dc2626;stroke-width:2.2;'
        f'opacity:1;marker-end:url(#tip-out)}}'
        for i in ids
    )


def _badge(x: float, y: float, testo: str) -> str:
    """Pillola destra-allineata per 'type · mode': larghezza dal conteggio caratteri,
    perche' e' monospace e non serve misurare il testo per davvero.
    """
    larghezza = len(testo) * 6.1 + 16
    bx = x + W - 14 - larghezza
    return (
        f'<rect x="{bx:.1f}" y="{y - 10}" width="{larghezza:.1f}" height="15" rx="7.5" fill="#eef2f6"/>'
        f'<text class="nbadge" x="{bx + larghezza / 2:.1f}" y="{y + 1}" text-anchor="middle" '
        f'fill="{theme.MUTED}">{escape(testo)}</text>'
    )


def boxes(data: dict, pos: dict, front: set[str]) -> str:
    out = []
    for node in data["nodes"]:
        if node["id"] not in pos:
            continue
        x, y = pos[node["id"]]
        bordo, sfondo, testo, glifo, _, dash = STATE[state_of(node, front)]
        ramo = data["branches"][node["branch"]].get("color", theme.EDGE)
        tratto = f' stroke-dasharray="{dash}"' if dash else ""
        deps = ", ".join(node["blockedBy"]) or t("render.libero")
        righe = wrap(node["title"])
        titolo = "".join(
            f'<text class="ntt" x="{x + 16}" y="{y + 41 + i * 16}" fill="{theme.INK}">{escape(r)}</text>'
            for i, r in enumerate(righe) if r
        )
        tipo_modo = f'{node["type"]} · {node["mode"]}'
        out.append(
            f'<a href="tickets/{node["id"]}.md"><g class="n" id="node-{node["id"]}">'
            f'<title>{escape(node["title"])} — {escape(node["question"])}</title>'
            f'<rect class="card" x="{x}" y="{y}" width="{W}" height="{H}" rx="9" '
            f'fill="{sfondo}" stroke="{bordo}" stroke-width="1.3"{tratto}/>'
            f'<rect x="{x}" y="{y + 10}" width="4" height="{H - 20}" rx="2" fill="{ramo}"/>'
            f'<text class="nid" x="{x + 16}" y="{y + 21}" fill="{testo}">{glifo} {node["id"]}</text>'
            f'{_badge(x, y + 21, tipo_modo)}'
            f'{titolo}'
            f'<text class="ndp" x="{x + 16}" y="{y + H - 12}" fill="{theme.FAINT}">← {escape(deps)}</text>'
            f'</g></a>'
        )
    return "".join(out)


def _markers() -> str:
    def marker(nome: str, colore: str) -> str:
        return (
            f'<marker id="{nome}" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" '
            f'markerHeight="8" orient="auto"><path d="M0,1 L7,4 L0,7 z" fill="{colore}"/></marker>'
        )
    return marker("tip", theme.EDGE) + marker("tip-in", "#16a34a") + marker("tip-out", "#dc2626")


def canvas(data: dict, depth: dict[str, int], front_ids: set[str]) -> str:
    """Stile dinamico + <svg> completo, pronti da inserire nella pagina."""
    pos = layout(data, depth)
    larghezza = max((x + W for x, _ in pos.values()), default=600) + PAD
    altezza = max((y + H for _, y in pos.values()), default=200) + PAD
    ids = [n["id"] for n in data["nodes"] if n["id"] in pos]
    return (
        f'<style>{hover_css(ids)}</style>'
        '<div class="wrap"><div class="canvas">'
        f'<svg viewBox="0 0 {larghezza} {altezza}" width="{larghezza}" height="{altezza}" '
        'xmlns="http://www.w3.org/2000/svg">'
        f'<defs>{_markers()}</defs>'
        f'{boxes(data, pos, front_ids)}{edges(data, pos)}'
        '</svg></div></div>'
    )
