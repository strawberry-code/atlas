"""Dashboard: da graph.json a un HTML autoconsistente che si apre da disco.

La pagina ha quattro parti: l'intestazione coi numeri di sintesi, la colonna
dei pannelli, il grafo come mappa navigabile e il pannello destro. Nessuna
risorsa remota: stile e comportamento viaggiano inline. Lo stile e' i font e i
token di Grafite (grafite.fonts.inline.css, grafite.offline.css) piu' otto
fogli propri di Atlas (tokens.css, shell.css, canvas.css, legend.css,
edges.css, sheet.css, table.css, notifiche.css), leggi dalla funzione
leggi_css_dashboard(). Il comportamento e' cinque moduli concatenati (canvas.js,
chrome.js, notifiche.js, table.js, sheet.js), leggi dalla funzione
leggi_js_dashboard().
Il contenitore della mappa (viewport, comandi di zoom, disegno via
render_svg.py) sta in render_canvas.py (F01): qui restano solo la legenda e il
suggerimento sotto la mappa, che render_canvas incolla dentro il suo
contenitore perche' sono posizionati in absolute rispetto a '.map'. Il pannello
destro e' un contenitore solo con due viste, Notifiche e Nodo (S11):
render_notifiche.panel() lo assembla per intero, prendendo il ticket cosi'
com'e' da render_sheet.sheet() (che non e' piu' una scheda modale) - qui
restano solo i dati incorporati per popolarla (render_sheet.data_island) e
l'assemblaggio del resto della pagina.
"""
from __future__ import annotations

from html import escape

from . import render_canvas, render_notifiche, render_owners, render_panels, render_sheet, render_table, theme
from .config import Graph
from .model import claimed, frontier, progress
from .risorse import leggi_css_dashboard, leggi_js_dashboard
from .strings import current, t
from .theme import ORDER, STATE, css_class


def _toggle_vista() -> str:
    """Mappa/tabella: l'icona mostrata e' quella della vista attiva, non quella
    del bersaglio del clic."""
    return (
        f'<button type="button" class="viewmode" aria-label="{escape(t("render.vista"))}">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">'
        '<g class="v-map"><circle cx="5.5" cy="6" r="2.3"/><circle cx="18.5" cy="6" r="2.3"/>'
        '<circle cx="12" cy="18" r="2.3"/><path stroke-linejoin="round" '
        'd="M7.4 7.6l3.3 8.6M16.6 7.6l-3.3 8.6M7.8 6h8.4"/></g>'
        '<g class="v-tbl"><rect x="3" y="4.5" width="18" height="15" rx="1"/>'
        '<path d="M3 9.5h18M3 14.5h18M10 4.5v15"/></g>'
        '</svg></button>'
    )


def _topbar(ref: Graph, data: dict, front: list[dict], presi: list[dict]) -> str:
    """I firmatari di Grafite: il wordmark porta gia' la tracking larga e le
    maiuscole (h1 esisteva cosi' da prima di questo giro), qui si aggiungono
    il pallino che respira ('.brand-dot', ricetta vanilla) e l'eyebrow sopra
    il titolo, ottenuta scambiando ordine con la vecchia '.sub' e applicandole
    la classe '.eyebrow' invece di riscriverne la tipografia a mano
    ('.section-title' regge la colonna, con margin-bottom azzerato: qui non e'
    un fine-sezione ma una riga della topbar). I tre numeri contano
    all'apertura come il resto della pagina (vedi chrome.js, 'data-count')."""
    meta = data["meta"]
    fatti, totale = progress(data)
    quota = round(100 * fatti / totale) if totale else 0
    # lo slug si incolla in '-g <slug>' ogni volta che si lavora su piu' grafi:
    # qui e' cliccabile, e il testo da copiare e' quello nudo, non il markup
    slug = (f'<code class="cp" data-copy="{escape(meta["slug"])}" '
            f'title="{escape(t("render.copia"))}" data-copiato="{escape(t("render.copiato"))}">'
            f'{escape(meta["slug"])}</code>')
    sottotitolo = t("render.sottotitolo", slug=slug,
                    progetto=escape(ref.workspace.config["project"]), data=escape(meta["updated"]))
    readouts = (
        f'<span class="ro"><label>{t("render.avanzamento")}</label>'
        f'<b data-count="{quota}" data-suffix="%">{quota}%</b></span>'
        f'<span class="ro"><label>{t("render.frontiera")}</label>'
        f'<b data-count="{len(front)}" data-pad="2">{len(front):02d}</b></span>'
        f'<span class="ro"><label>{t("render.in_lavorazione")}</label>'
        f'<b data-count="{len(presi)}" data-pad="2">{len(presi):02d}</b></span>'
    )
    return (
        f'<header class="topbar"><div class="mark">◬</div>'
        f'<div class="ident section-title"><p class="sub eyebrow">{sottotitolo}</p>'
        f'<div class="wordmark"><h1>{escape(meta["title"])}</h1>'
        f'<span class="brand-dot"></span></div></div>'
        f'<span class="spacer"></span><div class="readouts">{readouts}</div>'
        f'{_toggle_vista()}</header>'
    )


def _mappa(data: dict, front_ids: set[str], gruppi: dict[str, int]) -> str:
    """Costruisce legenda e suggerimento (proprieta' di render.py) e li passa
    al contenitore di render_canvas.py, che disegna la mappa e li incolla al
    posto giusto."""
    legenda = "".join(
        f'<button type="button" class="chip {css_class(s)}" data-state="{s}">'
        f'<i></i>{theme.glyph_html(s)} {t(STATE[s][1])}</button>' for s in ORDER
    ) + render_owners.chips(data, gruppi)
    return render_canvas.mappa(data, front_ids, gruppi, legenda, t("render.legenda_caption"))


def build(ref: Graph, data: dict) -> str:
    """La pagina."""
    front = frontier(data)
    presi = claimed(data)
    front_ids = {n["id"] for n in front}
    gruppi = render_owners.indice(data)
    # vista e notifiche salvate vanno timbrate prima del primo paint, o la pagina lampeggia
    stampo_prefs = ('<script>try{var v=localStorage.getItem("atlas-view");'
                    'if(v)document.documentElement.dataset.view=v;'
                    'var n=localStorage.getItem("atlas-notifiche");'
                    'if(n)document.documentElement.dataset.notifiche=n}catch(e){}</script>')
    css = leggi_css_dashboard()
    js = leggi_js_dashboard()
    return (
        f'<!doctype html><html lang="{current()}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{escape(data["meta"]["title"])} · atlas</title>'
        # data-slug: la chiave con cui positions.js isola in localStorage le
        # posizioni trascinate di questo grafo da quelle di un altro (C10).
        f'{stampo_prefs}<style>{css}</style></head>'
        f'<body data-slug="{escape(data["meta"]["slug"])}">'
        f'{_topbar(ref, data, front, presi)}'
        f'<aside class="side">{render_panels.panels(ref, data, front, presi, gruppi)}</aside>'
        f'{_mappa(data, front_ids, gruppi)}'
        f'{render_notifiche.panel(ref, data)}'
        f'{render_table.table(data, front_ids)}'
        f'{render_sheet.data_island(ref, data, front_ids, gruppi)}'
        f'<script>{js}</script>'
        '</body></html>'
    )


def write(ref: Graph, data: dict) -> None:
    ref.dashboard_path.write_text(build(ref, data), encoding="utf-8")
