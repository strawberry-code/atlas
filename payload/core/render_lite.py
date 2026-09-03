"""La pagina alleggerita per '/view' (D02, docs/atlas-relay-design.md S11/4):
grafo, titoli e stati, mai il testo di un ticket ne' quello di
un'Interazione aperta, che sono contenuto del lavoro quanto un ticket (S5).
E' la sola pagina che puo' lasciare questa macchina: passa dal relay verso
Telegram come foto scattata da un browser di sistema, o come il file stesso
quando nessun browser risponde (S7-bis/9). Le due uscite condividono
questa costruzione (S7-bis, "vanno progettate insieme"): payload/core/
telegram_view.py sceglie quale delle due, questo modulo non lo sa.

Statica apposta, niente dashboard.js: quello script legge '#atlas-data' al
primo avvio (render_sheet.py), che qui non esiste, e senza sheet non c'e'
comunque niente da aprire ("per leggere un ticket si va al computer",
S11/4). Riusa render_svg.py e render_table.py in quanto disegnano solo
struttura, titoli e stati; esclude render_panels.py e render_notifiche.py,
che mostrano prosa (destinazione del grafo, domande aperte, riassunti delle
Interazioni) fuori da quell'elenco chiuso.
"""
from __future__ import annotations

from html import escape

from . import render_svg, render_table, theme
from .config import Graph
from .model import claimed, frontier, progress
from .risorse import leggi_template
from .strings import current, t
from .theme import ORDER, STATE, css_class
from .topology import levels


def _topbar(data: dict, front: list[dict], presi: list[dict]) -> str:
    meta = data["meta"]
    fatti, totale = progress(data)
    quota = round(100 * fatti / totale) if totale else 0
    readouts = (
        f'<span class="ro"><label>{t("render.avanzamento")}</label><b>{quota}%</b></span>'
        f'<span class="ro"><label>{t("render.frontiera")}</label><b>{len(front):02d}</b></span>'
        f'<span class="ro"><label>{t("render.in_lavorazione")}</label><b>{len(presi):02d}</b></span>'
    )
    return (
        f'<header class="topbar"><div class="mark">◬</div>'
        f'<div class="ident"><h1>{escape(meta["title"])}</h1></div>'
        f'<span class="spacer"></span><div class="readouts">{readouts}</div></header>'
    )


def _legenda() -> str:
    return "".join(
        f'<span class="chip {css_class(s)}"><i></i>{theme.glyph_html(s)} {t(STATE[s][1])}</span>'
        for s in ORDER
    )


def build(ref: Graph, data: dict) -> str:
    """La pagina intera, gia' pronta da scrivere su disco o da dare a un
    browser: stesso foglio di stile della dashboard vera (dashboard.css),
    cosi' la foto e la pagina vera si somigliano."""
    depth = levels(data)
    front = frontier(data)
    presi = claimed(data)
    front_ids = {n["id"] for n in front}
    return (
        f'<!doctype html><html lang="{current()}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{escape(data["meta"]["title"])} · atlas</title>'
        f'<style>{leggi_template("dashboard.css")}</style></head><body>'
        f'{_topbar(data, front, presi)}'
        f'<main class="map"><div class="viewport">'
        f'{render_svg.canvas(data, depth, front_ids, {}, lite=True)}</div>'
        f'<div class="legend">{_legenda()}</div></main>'
        f'{render_table.table(data, front_ids)}'
        '</body></html>'
    )
