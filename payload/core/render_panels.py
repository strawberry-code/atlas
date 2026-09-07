"""I blocchi della colonna di sinistra: avanzamento, frontiera, costo, avvisi.

Spezzato da render.py, che assembla la pagina (intestazione, mappa del grafo,
scheda del ticket): qui c'e' l'involucro dei pannelli laterali e la loro
assemblatura; le righe '<li>' di ciascuno stanno in render_panel_rows.py,
spezzate via perche' questo file faceva due lavori insieme.

Le superfici sono le ricette dense di Grafite (G03): .panel-dense per il
pannello, .row-dense (+ .reveal-on-hover, in render_panel_rows.py) per le
righe, .chip-state per i segnali semantici, .badge-count per i conteggi. La
classe 'blocco' resta accanto a 'panel-dense' su ogni pannello, incluso quello
di render_owners.py (migrato in S07): serve solo perche' edges.css la lega
alla mappa (':has([data-hl]...)'), non porta piu' un aspetto suo.
"""
from __future__ import annotations

import re

from html import escape

from . import questions, render_owners
from . import render_panel_rows as righe
from .config import Graph
from .model import progress
from .strings import t
from .topology import convergence


def _blocco_avanzamento(data: dict, fatti: int, totale: int) -> str:
    quota = round(100 * fatti / totale) if totale else 0
    fuori = sum(1 for n in data["nodes"] if n["status"] == "out-of-scope")
    return (
        f'<section class="blocco panel-dense"><h2 class="eyebrow">{t("render.avanzamento")}</h2>'
        '<div class="ring-wrap">'
        '<svg class="ring" viewBox="0 0 120 120">'
        '<defs><linearGradient id="ringgrad" x1="0" y1="0" x2="1" y2="1">'
        '<stop class="rg-a" offset="0"/><stop class="rg-b" offset="1"/></linearGradient></defs>'
        '<circle class="ring-ticks" cx="60" cy="60" r="58" pathLength="120"/>'
        '<circle class="ring-bg" cx="60" cy="60" r="49" pathLength="100"/>'
        f'<circle class="ring-fg" cx="60" cy="60" r="49" pathLength="100" style="--p:{quota}"/></svg>'
        f'<div><span class="pct" data-count="{quota}" data-suffix="%">{quota}%</span>'
        f'<span class="frac">{t("render.nodi_conteggio", fatti=fatti, totale=totale)}'
        # il denominatore non torna coi blocchi che si contano sulla mappa se
        # qualcuno e' fuori scopo: si dice qui, invece di lasciarlo dedurre
        f'{t("render.fuori_conteggio", n=fuori) if fuori else ""}</span></div></div>'
        f'<p class="dest">{escape(data["meta"]["destination"])}</p></section>'
    )


def _blocco_lista(titolo: str, voci: list[str], vuoto: str, extra: str = "",
                  hl: str | None = None) -> str:
    """hl e' lo stato visivo che questo blocco rappresenta: passare il mouse sul
    blocco accende sulla mappa i nodi di quello stato (vedi edges.css, che lega
    la mappa a '.blocco[data-hl]'). 'extra' aggiunge classi al pannello, per
    esempio 'blocco-chiusi' per la lista scrollabile dei nodi chiusi."""
    corpo = "".join(voci) or f'<li>{vuoto}</li>'
    attr = f' data-hl="{hl}"' if hl else ""
    classe = f'blocco panel-dense{" " + extra if extra else ""}'
    return f'<section class="{classe}"{attr}><h2 class="eyebrow">{titolo}</h2><ul>{corpo}</ul></section>'


def costo_numerico(testo: str) -> float | None:
    """Primo numero dentro un costo scritto a mano, None se non ce n'e' nessuno.

    Il separatore decimale deve stare fra due cifre: una regex piu' larga
    matcherebbe la punteggiatura della prosa ("una sessione... .") e float()
    la rifiuterebbe, facendo saltare l'intera dashboard per un punto fermo.

    Pubblica perche' la vista tabellare (render_table.py) la riusa per ordinare
    la colonna costo: la stessa cifra deve valere la stessa cosa nei due posti.
    """
    trovato = re.search(r"\d+(?:[.,]\d+)?", testo)
    return float(trovato.group().replace(",", ".")) if trovato else None


def _blocco_costi(chiusi: list[dict]) -> str:
    con_costo = [n for n in chiusi if n.get("cost")]
    numerici = [costo_numerico(n["cost"]) for n in con_costo]
    totale = sum(v for v in numerici if v is not None)
    fuori_conteggio = sum(1 for v in numerici if v is None)
    return (
        f'<section class="blocco panel-dense"><h2 class="eyebrow">{t("render.costi")}</h2>'
        f'<p class="pct-line">{totale:g}<span>{t("render.costi_copertura", con=len(con_costo), totale=len(chiusi))}'
        f'</span></p>'
        f'<p class="nota">{t("render.costi_fuori_conteggio", n=fuori_conteggio)}</p></section>'
    )


def _blocco_caution(data: dict, fatti: int, totale: int) -> str:
    """L'avviso: il grafo non converge in un nodo finale unico.

    Come in doctor, a grafo finito tace: l'avviso serve mentre la struttura
    si puo' ancora correggere. Gli id sono cliccabili come le voci di lista.
    Il chip-state 'warn' (pulsante, ricetta G03) tiene l'avviso visibilmente
    tale anche dentro la stessa veste densa degli altri pannelli, non solo il
    bordo colorato con lo stato 'frontier'."""
    end, sciolti = convergence(data)
    if not sciolti or fatti == totale:
        return ""
    chip = '<b data-node="{i}">{i}</b>'
    elenco = ", ".join(chip.format(i=escape(i)) for i in sciolti)
    return (
        f'<section class="blocco caution panel-dense"><h2 class="eyebrow">{t("render.caution")}'
        f'<span class="chip-state warn"><i class="chip-state-dot"></i>{len(sciolti)}</span></h2>'
        f'<p>{t("render.non_converge", end=chip.format(i=escape(end)), elenco=elenco)}</p></section>'
    )


def _blocco_remoto(remoto: list[object], errore: bool) -> str:
    voci = righe.remoto(remoto)
    if errore:
        voci.insert(0, f'<li class="remoto-rete">{escape(t("render.remoto_rete"))}</li>')
    return _blocco_lista(t("render.remoto"), voci, t("render.remoto_vuoto"))


def panels(ref: Graph, data: dict, front: list[dict], presi: list[dict],
           gruppi: dict[str, int], remoto: list[object] | None = None,
           remoto_errore: bool = False) -> str:
    agente = ref.workspace.config["agent"]
    fatti, totale = progress(data)
    blocchi = [
        _blocco_caution(data, fatti, totale),
        _blocco_avanzamento(data, fatti, totale),
        _blocco_lista(t("render.frontiera"), righe.frontiera(front),
                     t("render.frontiera_vuota"), hl="frontier"),
    ]
    aperte = questions.open_questions(data)
    if aperte:
        vecchie = {q["id"] for q in questions.aged_questions(data)}
        blocchi.append(_blocco_lista(t("render.domande"), righe.domande(aperte, vecchie), ""))
    if presi:
        blocchi.append(_blocco_lista(t("render.in_lavorazione"),
                                     righe.in_lavorazione(presi, agente), "", hl="claimed"))
    # I lucchetti delle altre macchine: compaiono solo col lucchetto remoto attivo
    # (serve.py li inietta come dati), e si mettono accanto a 'in lavorazione'
    # perche' dicono la stessa cosa dall'altro lato della rete.
    if remoto is not None or remoto_errore:
        blocchi.append(_blocco_remoto(remoto or [], remoto_errore))
    chiusi = [n for n in data["nodes"] if n["status"] == "closed"]
    if chiusi:
        blocchi.append(_blocco_lista(t("render.chiusi"), righe.chiusi(chiusi), "",
                                     extra="blocco-chiusi", hl="closed"))
        blocchi.append(_blocco_costi(chiusi))
    blocchi.append(render_owners.panel(data, gruppi))
    blocchi.append(_blocco_lista(t("render.rami"), righe.rami(data), t("render.nessun_ramo")))
    blocchi.append(f'<div class="firma">{t("render.footer")}</div>')
    return "".join(blocchi)
