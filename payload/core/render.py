"""Dashboard: da graph.json a un HTML autoconsistente che si apre da disco.

La pagina e' una plancia: barra dei readout in alto, strumenti in una colonna,
e il grafo come display centrale, navigabile. Nessuna risorsa remota: stile e
comportamento (templates/dashboard.css e .js) viaggiano inline. Il disegno del
grafo sta in render_svg.py, la scheda del ticket e i suoi dati in
render_sheet.py: qui c'e' solo l'assemblaggio della plancia.
"""
from __future__ import annotations

import re
from html import escape

from . import claims, render_sheet, render_svg, theme
from .config import Graph
from .model import claimed, convergence, frontier, levels, progress
from .risorse import leggi_template
from .strings import current, t
from .theme import ORDER, STATE, css_class


def _blocco_avanzamento(data: dict, fatti: int, totale: int) -> str:
    quota = round(100 * fatti / totale) if totale else 0
    return (
        f'<section class="blocco"><h2>{t("render.avanzamento")}</h2>'
        '<div class="ring-wrap">'
        '<svg class="ring" viewBox="0 0 120 120">'
        '<defs><linearGradient id="ringgrad" x1="0" y1="0" x2="1" y2="1">'
        '<stop class="rg-a" offset="0"/><stop class="rg-b" offset="1"/></linearGradient></defs>'
        '<circle class="ring-ticks" cx="60" cy="60" r="58" pathLength="120"/>'
        '<circle class="ring-bg" cx="60" cy="60" r="49" pathLength="100"/>'
        f'<circle class="ring-fg" cx="60" cy="60" r="49" pathLength="100" style="--p:{quota}"/></svg>'
        f'<div><span class="pct" data-count="{quota}">{quota}%</span>'
        f'<span class="frac">{t("render.nodi_conteggio", fatti=fatti, totale=totale)}</span></div></div>'
        f'<p class="dest">{escape(data["meta"]["destination"])}</p></section>'
    )


def _blocco_lista(titolo: str, voci: list[str], vuoto: str, classe: str = "blocco",
                  hl: str | None = None) -> str:
    """hl e' lo stato visivo che questo blocco rappresenta: passare il mouse sul
    blocco accende sulla carta i track di quello stato (vedi dashboard.css)."""
    corpo = "".join(voci) or f'<li>{vuoto}</li>'
    attr = f' data-hl="{hl}"' if hl else ""
    return f'<section class="{classe}"{attr}><h2>{titolo}</h2><ul>{corpo}</ul></section>'


def _costo_numerico(testo: str) -> float | None:
    """Primo numero dentro un costo scritto a mano, None se non ce n'e' nessuno.

    Il separatore decimale deve stare fra due cifre: una regex piu' larga
    matcherebbe la punteggiatura della prosa ("una sessione... .") e float()
    la rifiuterebbe, facendo saltare l'intera dashboard per un punto fermo.
    """
    trovato = re.search(r"\d+(?:[.,]\d+)?", testo)
    return float(trovato.group().replace(",", ".")) if trovato else None


def _blocco_costi(chiusi: list[dict]) -> str:
    con_costo = [n for n in chiusi if n.get("cost")]
    numerici = [_costo_numerico(n["cost"]) for n in con_costo]
    totale = sum(v for v in numerici if v is not None)
    fuori_conteggio = sum(1 for v in numerici if v is None)
    return (
        f'<section class="blocco"><h2>{t("render.costi")}</h2>'
        f'<p class="pct-line">{totale:g}<span>{t("render.costi_copertura", con=len(con_costo), totale=len(chiusi))}'
        f'</span></p>'
        f'<p class="nota">{t("render.costi_fuori_conteggio", n=fuori_conteggio)}</p></section>'
    )


def _blocco_caution(data: dict, fatti: int, totale: int) -> str:
    """L'annunciatore: il grafo non converge in un nodo finale unico.

    Come in doctor, a grafo finito tace: l'avviso serve mentre la struttura
    si puo' ancora correggere. Gli id sono cliccabili come le voci di lista.
    """
    end, sciolti = convergence(data)
    if not sciolti or fatti == totale:
        return ""
    chip = '<b data-node="{i}">{i}</b>'
    elenco = ", ".join(chip.format(i=escape(i)) for i in sciolti)
    return (
        f'<section class="blocco caution"><h2>{t("render.caution")}</h2>'
        f'<p>{t("render.non_converge", end=chip.format(i=escape(end)), elenco=elenco)}</p></section>'
    )


def panels(ref: Graph, data: dict, front: list[dict], presi: list[dict]) -> str:
    agente = ref.workspace.config["agent"]
    fatti, totale = progress(data)
    voci_front = [
        f'<li data-node="{n["id"]}"><b>{n["id"]}</b> {escape(n["title"])}'
        f'<span class="tag">{n["type"]}·{n["mode"]}</span></li>' for n in front
    ]
    conteggi = {k: 0 for k in data["branches"]}
    for node in data["nodes"]:
        conteggi[node["branch"]] += 1
    voci_rami = [
        f'<li data-branch="{escape(k)}">'
        f'<span class="dot" style="background:{r.get("color", theme.BRANCH_FALLBACK)}"></span>'
        f'<b>{k}</b> {escape(r["label"])}'
        f'<span class="tag">{t("render.nodi_del_ramo", n=conteggi[k])}</span></li>'
        for k, r in data["branches"].items()
    ]
    blocchi = [
        _blocco_caution(data, fatti, totale),
        _blocco_avanzamento(data, fatti, totale),
        _blocco_lista(t("render.frontiera"), voci_front, t("render.frontiera_vuota"), hl="frontier"),
    ]
    if presi:
        voci = [
            f'<li data-node="{n["id"]}"><b>{n["id"]}</b> {escape(n["title"])}'
            f'<span class="tag">{escape(n["assignee"] or "?")} · '
            f'{claims.claim_state(n, agente)}</span></li>' for n in presi
        ]
        blocchi.append(_blocco_lista(t("render.in_lavorazione"), voci, "", hl="claimed"))
    chiusi = [n for n in data["nodes"] if n["status"] == "closed"]
    if chiusi:
        voci_chiusi = [
            f'<li data-node="{n["id"]}"><b>{n["id"]}</b> {escape(n["title"])}'
            f'<span class="tag">{escape(n.get("cost") or t("render.costo_ignoto"))}</span></li>'
            for n in chiusi
        ]
        blocchi.append(_blocco_lista(t("render.chiusi"), voci_chiusi, "",
                                     classe="blocco blocco-chiusi", hl="closed"))
        blocchi.append(_blocco_costi(chiusi))
    blocchi.append(_blocco_lista(t("render.rami"), voci_rami, t("render.nessun_ramo")))
    blocchi.append(f'<div class="firma">{t("render.footer")}</div>')
    return "".join(blocchi)


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
        f'<aside class="side">{panels(ref, data, front, presi)}</aside>'
        f'{_mappa(data, depth, front_ids)}'
        f'{render_sheet.sheet()}{render_sheet.data_island(ref, data, front_ids)}'
        f'<script>{leggi_template("dashboard.js")}</script>'
        '</body></html>'
    )


def write(ref: Graph, data: dict) -> None:
    ref.dashboard_path.write_text(build(ref, data), encoding="utf-8")
