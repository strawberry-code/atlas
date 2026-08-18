"""I blocchi della colonna di sinistra: avanzamento, frontiera, costo, avvisi.

Spezzato da render.py, che assembla la pagina (intestazione, mappa del grafo,
scheda del ticket): qui c'e' solo il contenuto dei pannelli laterali, che
e' la parte che cambia piu' spesso perche' segue quel che il grafo ha da dire.
"""
from __future__ import annotations

import re
from html import escape

from . import claims, render_owners, theme
from .config import Graph
from .model import progress
from .strings import t
from .topology import convergence


def _blocco_avanzamento(data: dict, fatti: int, totale: int) -> str:
    quota = round(100 * fatti / totale) if totale else 0
    fuori = sum(1 for n in data["nodes"] if n["status"] == "out-of-scope")
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
        f'<span class="frac">{t("render.nodi_conteggio", fatti=fatti, totale=totale)}'
        # il denominatore non torna coi blocchi che si contano sulla mappa se
        # qualcuno e' fuori scopo: si dice qui, invece di lasciarlo dedurre
        f'{t("render.fuori_conteggio", n=fuori) if fuori else ""}</span></div></div>'
        f'<p class="dest">{escape(data["meta"]["destination"])}</p></section>'
    )


def _blocco_lista(titolo: str, voci: list[str], vuoto: str, classe: str = "blocco",
                  hl: str | None = None) -> str:
    """hl e' lo stato visivo che questo blocco rappresenta: passare il mouse sul
    blocco accende sulla mappa i nodi di quello stato (vedi dashboard.css)."""
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
    """L'avviso: il grafo non converge in un nodo finale unico.

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


def panels(ref: Graph, data: dict, front: list[dict], presi: list[dict],
           gruppi: dict[str, int]) -> str:
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
        f'{theme.shape_svg(i, r.get("color", theme.BRANCH_FALLBACK), 11)}'
        f'<b>{k}</b> {escape(r["label"])}'
        f'<span class="tag">{t("render.nodi_del_ramo", n=conteggi[k])}</span></li>'
        for i, (k, r) in enumerate(data["branches"].items())
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
    blocchi.append(render_owners.panel(data, gruppi))
    blocchi.append(_blocco_lista(t("render.rami"), voci_rami, t("render.nessun_ramo")))
    blocchi.append(f'<div class="firma">{t("render.footer")}</div>')
    return "".join(blocchi)
