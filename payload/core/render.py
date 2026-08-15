"""Dashboard: da graph.json a un HTML autoconsistente che si apre da disco.

La pagina ha tre parti: l'intestazione coi numeri di sintesi, la colonna dei
pannelli e il grafo come mappa navigabile. Nessuna risorsa remota: stile e
comportamento (templates/dashboard.css e .js) viaggiano inline. Il disegno del
grafo sta in render_svg.py, la scheda del ticket e i suoi dati in
render_sheet.py: qui c'e' solo l'assemblaggio della pagina.
"""
from __future__ import annotations

from html import escape

from . import render_panels, render_sheet, render_svg
from .config import Graph
from .model import claimed, frontier, progress
from .risorse import leggi_template
from .strings import current, t
from .theme import ORDER, STATE, css_class
from .topology import levels


def _toggle_tema() -> str:
    return (
        f'<button type="button" class="theme" aria-label="{escape(t("render.tema"))}">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">'
        '<g class="sun"><circle cx="12" cy="12" r="4.4"/>'
        '<path d="M12 2.8v2.2M12 19v2.2M2.8 12h2.2M19 12h2.2M5.2 5.2l1.6 1.6M17.2 17.2l1.6 1.6'
        'M18.8 5.2l-1.6 1.6M6.8 17.2l-1.6 1.6"/></g>'
        '<g class="moon"><path d="M20 13.2A8 8 0 1 1 10.8 4a6.4 6.4 0 0 0 9.2 9.2z"/></g>'
        '</svg></button>'
    )


def _topbar(ref: Graph, data: dict, front: list[dict], presi: list[dict]) -> str:
    meta = data["meta"]
    fatti, totale = progress(data)
    quota = round(100 * fatti / totale) if totale else 0
    sottotitolo = t("render.sottotitolo", slug=escape(meta["slug"]),
                    progetto=escape(ref.workspace.config["project"]), data=escape(meta["updated"]))
    readouts = (
        f'<span class="ro"><label>{t("render.avanzamento")}</label><b>{quota}%</b></span>'
        f'<span class="ro"><label>{t("render.frontiera")}</label><b>{len(front):02d}</b></span>'
        f'<span class="ro"><label>{t("render.in_lavorazione")}</label><b>{len(presi):02d}</b></span>'
    )
    return (
        f'<header class="topbar"><div class="mark">◬</div>'
        f'<div class="ident"><h1>{escape(meta["title"])}</h1>'
        f'<p class="sub">{sottotitolo}</p></div>'
        f'<span class="spacer"></span><div class="readouts">{readouts}</div>{_toggle_tema()}</header>'
    )


def _mappa(data: dict, depth: dict, front_ids: set[str]) -> str:
    legenda = "".join(
        f'<button type="button" class="chip {css_class(s)}" data-state="{s}">'
        f'<i></i>{STATE[s][0]} {t(STATE[s][1])}</button>' for s in ORDER
    )
    zoom = (
        f'<div class="zoom"><button type="button" data-zoom="in" aria-label="{escape(t("render.zoom_in"))}">+</button>'
        f'<button type="button" data-zoom="out" aria-label="{escape(t("render.zoom_out"))}">−</button>'
        f'<button type="button" data-zoom="fit" aria-label="{escape(t("render.zoom_fit"))}">⌖</button></div>'
    )
    return (
        f'<main class="map"><div class="viewport">{render_svg.canvas(data, depth, front_ids)}</div>'
        f'<div class="legend">{legenda}</div>{zoom}'
        f'<p class="hint">{t("render.legenda_caption")}</p></main>'
    )


def build(ref: Graph, data: dict) -> str:
    depth = levels(data)
    front = frontier(data)
    presi = claimed(data)
    front_ids = {n["id"] for n in front}
    # il tema salvato va timbrato prima del primo paint, o la pagina lampeggia
    stampo_tema = ('<script>try{var t=localStorage.getItem("atlas-theme");'
                   'if(t)document.documentElement.dataset.theme=t}catch(e){}</script>')
    return (
        f'<!doctype html><html lang="{current()}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{escape(data["meta"]["title"])} · atlas</title>'
        f'{stampo_tema}<style>{leggi_template("dashboard.css")}</style></head><body>'
        f'{_topbar(ref, data, front, presi)}'
        f'<aside class="side">{render_panels.panels(ref, data, front, presi)}</aside>'
        f'{_mappa(data, depth, front_ids)}'
        f'{render_sheet.sheet()}{render_sheet.data_island(ref, data, front_ids)}'
        f'<script>{leggi_template("dashboard.js")}</script>'
        '</body></html>'
    )


def write(ref: Graph, data: dict) -> None:
    ref.dashboard_path.write_text(build(ref, data), encoding="utf-8")
