"""Dashboard: da graph.json a un HTML autoconsistente che si apre da disco.

Nessuna dipendenza esterna e nessuna risorsa remota, quindi niente rete e niente
JavaScript. Il disegno vero e proprio del grafo (layout, archi, card dei nodi)
sta in render_svg.py: qui c'e' solo l'assemblaggio della pagina attorno a
quel canvas, cioe' header, pannelli laterali, legenda, footer.
"""
from __future__ import annotations

import re
from html import escape

from . import claims, render_svg, theme
from .config import Graph
from .model import claimed, frontier, levels, progress
from .strings import current, t
from .theme import STATE


def _card_avanzamento(data: dict, fatti: int, totale: int) -> str:
    quota = round(100 * fatti / totale) if totale else 0
    return (
        f'<section class="box box-avanzamento"><h2>{t("render.avanzamento")}</h2>'
        f'<p class="pct">{quota}%<span>{t("render.nodi_conteggio", fatti=fatti, totale=totale)}</span></p>'
        f'<div class="track"><div class="fill" style="width:{quota}%"></div></div>'
        f'<p class="dest">{escape(data["meta"]["destination"])}</p></section>'
    )


def _card_lista(titolo: str, voci: list[str], vuoto: str, classe: str = "box") -> str:
    corpo = "".join(voci) or f'<li>{vuoto}</li>'
    return f'<section class="{classe}"><h2>{titolo}</h2><ul>{corpo}</ul></section>'


def _costo_numerico(testo: str) -> float | None:
    """Primo numero dentro un costo scritto a mano, None se non ce n'e' nessuno.

    Il separatore decimale deve stare fra due cifre: una regex piu' larga
    matcherebbe la punteggiatura della prosa ("una sessione... .") e float()
    la rifiuterebbe, facendo saltare l'intera dashboard per un punto fermo.
    """
    trovato = re.search(r"\d+(?:[.,]\d+)?", testo)
    return float(trovato.group().replace(",", ".")) if trovato else None


def _card_costi(chiusi: list[dict]) -> str:
    con_costo = [n for n in chiusi if n.get("cost")]
    numerici = [_costo_numerico(n["cost"]) for n in con_costo]
    totale = sum(v for v in numerici if v is not None)
    fuori_conteggio = sum(1 for v in numerici if v is None)
    return (
        f'<section class="box"><h2>{t("render.costi")}</h2>'
        f'<p class="pct">{totale:g}<span>{t("render.costi_copertura", con=len(con_costo), totale=len(chiusi))}'
        f'</span></p>'
        f'<p class="dest">{t("render.costi_fuori_conteggio", n=fuori_conteggio)}</p></section>'
    )


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
    chiusi = [n for n in data["nodes"] if n["status"] == "closed"]
    if chiusi:
        cards.append(_card_costi(chiusi))
        voci_chiusi = [
            f'<li><b>{n["id"]}</b> {escape(n["title"])}'
            f'<span class="tag">{escape(n.get("cost") or t("render.costo_ignoto"))}</span></li>'
            for n in chiusi
        ]
        cards.append(_card_lista(t("render.chiusi"), voci_chiusi, "", classe="box box-chiusi"))
    return "".join(cards)


def build(ref: Graph, data: dict) -> str:
    depth = levels(data)
    front = frontier(data)
    presi = claimed(data)
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
        f'<span class="hint" style="margin-left:auto">{t("render.legenda_caption")}</span></div>'
        f'{render_svg.canvas(data, depth, {n["id"] for n in front})}'
        f'<footer>{t("render.footer")}'
        '</footer></body></html>'
    )


def write(ref: Graph, data: dict) -> None:
    ref.dashboard_path.write_text(build(ref, data), encoding="utf-8")
