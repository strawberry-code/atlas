"""Dashboard: da graph.json a un HTML autoconsistente che si apre da disco.

Nessuna dipendenza esterna e nessuna risorsa remota, quindi niente rete e niente
JavaScript. Il grafo e' disegnato in SVG con i nodi disposti per profondita'
topologica: il verso e' dall'alto in basso perche' le catene di dipendenze sono
lunghe e strette, e sedici livelli in orizzontale non si leggerebbero.
"""
from __future__ import annotations

from html import escape

from . import claims, theme
from .config import Graph
from .model import claimed, frontier, levels, progress
from .strings import current, t
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


def edges(data: dict, pos: dict) -> str:
    """Bezier verticale dal bordo basso del blocker al bordo alto del bloccato."""
    out = []
    for node in data["nodes"]:
        if node["id"] not in pos:
            continue
        x2, y2 = pos[node["id"]]
        for dep in node["blockedBy"]:
            if dep not in pos:
                continue
            x1, y1 = pos[dep]
            sx, sy, ex, ey = x1 + W / 2, y1 + H, x2 + W / 2, y2
            mid = sy + (ey - sy) / 2
            out.append(
                f'<path d="M{sx},{sy} C{sx},{mid} {ex},{mid} {ex},{ey}" fill="none" '
                f'stroke="{theme.EDGE}" stroke-width="1.4" marker-end="url(#tip)"/>'
            )
    return "".join(out)


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
            f'<text class="ntt" x="{x + 16}" y="{y + 40 + i * 16}" fill="{theme.INK}">{escape(r)}</text>'
            for i, r in enumerate(righe) if r
        )
        out.append(
            f'<a href="tickets/{node["id"]}.md"><g class="n">'
            f'<title>{escape(node["title"])} — {escape(node["question"])}</title>'
            f'<rect class="card" x="{x}" y="{y}" width="{W}" height="{H}" rx="8" '
            f'fill="{sfondo}" stroke="{bordo}" stroke-width="1.3"{tratto}/>'
            f'<rect x="{x}" y="{y + 10}" width="4" height="{H - 20}" rx="2" fill="{ramo}"/>'
            f'<text class="nid" x="{x + 16}" y="{y + 21}" fill="{testo}">{glifo} {node["id"]}</text>'
            f'<text class="nty" x="{x + W - 14}" y="{y + 21}" text-anchor="end" '
            f'fill="{theme.FAINT}">{node["type"]} · {node["mode"]}</text>'
            f'{titolo}'
            f'<text class="ndp" x="{x + 16}" y="{y + H - 12}" fill="{theme.FAINT}">← {escape(deps)}</text>'
            f'</g></a>'
        )
    return "".join(out)


def _card_avanzamento(data: dict, fatti: int, totale: int) -> str:
    quota = round(100 * fatti / totale) if totale else 0
    return (
        f'<section class="box"><h2>{t("render.avanzamento")}</h2>'
        f'<p class="pct">{quota}%<span>{t("render.nodi_conteggio", fatti=fatti, totale=totale)}</span></p>'
        f'<div class="track"><div class="fill" style="width:{quota}%"></div></div>'
        f'<p class="dest">{escape(data["meta"]["destination"])}</p></section>'
    )


def _card_lista(titolo: str, voci: list[str], vuoto: str) -> str:
    corpo = "".join(voci) or f'<li>{vuoto}</li>'
    return f'<section class="box"><h2>{titolo}</h2><ul>{corpo}</ul></section>'


def panels(ref: Graph, data: dict, front: list[dict], presi: list[dict]) -> str:
    agente = ref.workspace.config["agent"]
    fatti, totale = progress(data)
    voci_front = [
        f'<li><b>{n["id"]}</b> {escape(n["title"])}'
        f'<span class="tag">{n["type"]} · {n["mode"]}</span></li>' for n in front
    ]
    conteggi = {k: 0 for k in data["branches"]}
    for node in data["nodes"]:
        conteggi[node["branch"]] += 1
    voci_rami = [
        f'<li><span class="dot" style="background:{r.get("color", theme.EDGE)}"></span>'
        f'<b>{k}</b> {escape(r["label"])}'
        f'<span class="tag">{t("render.nodi_del_ramo", n=conteggi[k])}</span></li>'
        for k, r in data["branches"].items()
    ]
    cards = [
        _card_avanzamento(data, fatti, totale),
        _card_lista(t("render.frontiera"), voci_front, t("render.frontiera_vuota")),
        _card_lista(t("render.rami"), voci_rami, t("render.nessun_ramo")),
    ]
    if presi:
        voci = [
            f'<li><b>{n["id"]}</b> {escape(n["title"])}'
            f'<span class="tag">{escape(n["assignee"] or "?")} · '
            f'{claims.claim_state(n, agente)}</span></li>' for n in presi
        ]
        cards.append(_card_lista(t("render.in_lavorazione"), voci, ""))
    return "".join(cards)


def build(ref: Graph, data: dict) -> str:
    depth = levels(data)
    pos = layout(data, depth)
    front = frontier(data)
    presi = claimed(data)
    larghezza = max((x + W for x, _ in pos.values()), default=600) + PAD
    altezza = max((y + H for _, y in pos.values()), default=200) + PAD
    legenda = "".join(
        f'<span><i class="dot" style="background:{STATE[s][1]};border:1.5px solid {STATE[s][0]}"></i>'
        f'{STATE[s][3]} {t(STATE[s][4])}</span>' for s in theme.ORDER
    )
    meta = data["meta"]
    sottotitolo = t("render.sottotitolo", slug=escape(meta["slug"]),
                    progetto=escape(ref.workspace.config["project"]), data=escape(meta["updated"]))
    return (
        f'<!doctype html><html lang="{current()}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{escape(meta["title"])} · atlas</title><style>{theme.CSS}</style></head><body>'
        f'<header><h1>{escape(meta["title"])}</h1>'
        f'<p class="sub">{sottotitolo}</p></header>'
        f'<div class="grid">{panels(ref, data, front, presi)}</div>'
        f'<div class="legend">{legenda}'
        f'<span style="margin-left:auto">{t("render.legenda_caption")}</span></div>'
        f'<div class="wrap"><div class="canvas">'
        f'<svg viewBox="0 0 {larghezza} {altezza}" width="{larghezza}" height="{altezza}" '
        'xmlns="http://www.w3.org/2000/svg">'
        f'<defs><marker id="tip" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" '
        f'markerHeight="6" orient="auto"><path d="M0,1 L7,4 L0,7 z" fill="{theme.EDGE}"/>'
        '</marker></defs>'
        f'{edges(data, pos)}{boxes(data, pos, {n["id"] for n in front})}'
        '</svg></div></div>'
        f'<footer>{t("render.footer")}'
        '</footer></body></html>'
    )


def write(ref: Graph, data: dict) -> None:
    ref.dashboard_path.write_text(build(ref, data), encoding="utf-8")
