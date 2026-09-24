"""Il ticket dentro la dashboard: scheletro della vista Nodo e dati.

Fino a S11 la vista era una scheda modale a se stante, con un velo sfocato
sopra la pagina; ora e' una delle due viste del pannello destro, incollata
dentro '.notifiche-corpo' da render_notifiche.panel() insieme alla vista
Notifiche - stesso contenitore, stessa apertura/chiusura, un selettore per
scegliere quale guardare (S12 decide quando). Qui restano lo scheletro vuoto
che sheet.js riempie (invariato: la scheda cambia contenitore, non le classi
che quel modulo legge) e i dati del grafo per popolarlo. I ticket sono
incorporati come JSON al momento della generazione, perche' da file:// nessuna
fetch potrebbe leggerli dopo; il markdown lo trasforma sheet.js, qui viaggia
grezzo.
"""
from __future__ import annotations

import json
import re
from html import escape

from . import render_owners, theme
from .config import Graph
from .model import owners_of, url_valido
from .strings import t
from .theme import ORDER, STATE, state_of

# il blocco autogenerato in testa al ticket: nella scheda e' rumore, la scheda
# stessa mostra gia' id, titolo, domanda e stato presi dal grafo
_AUTO = re.compile(r"<!--\s*atlas:auto\s*-->.*?<!--\s*/atlas:auto\s*-->\s*", re.S)


def _ticket_md(ref: Graph, node_id: str) -> str:
    path = ref.ticket_path(node_id)
    if not path.is_file():
        return ""
    return _AUTO.sub("", path.read_text(encoding="utf-8"), count=1)


def data_island(ref: Graph, data: dict, front_ids: set[str], gruppi: dict[str, int]) -> str:
    """Nodi, ticket e etichette di stato, incorporati per la side sheet.

    La sequenza '</' viene spezzata: dentro un blocco script anche un banale
    '</p>' nel markdown di un ticket chiuderebbe il tag e romperebbe la pagina.
    'gruppi' e' lo stesso indice che la card porta in 'data-owners' (issue
    #34): 'ownerColor' esce gia' calcolato da render_owners.colore(), cosi'
    sheet.js non ricalcola una sua tavolozza che prima o poi diverge da quella
    della card.
    """
    nodi = {}
    ordine_rami = list(data["branches"])
    for n in data["nodes"]:
        ramo = data["branches"][n["branch"]]
        nodi[n["id"]] = {
            "title": n["title"], "question": n["question"],
            "state": state_of(n, front_ids), "type": n["type"], "mode": n["mode"],
            "branchLabel": ramo["label"],
            "branchColor": ramo.get("color", theme.BRANCH_FALLBACK),
            # la stessa figura che il nodo porta sulla mappa, cosi' la scheda e la
            # card si riconoscono l'una nell'altra
            "branchShape": theme.shape_of(ordine_rami.index(n["branch"])),
            "cost": n.get("cost") or "",
            "model": n.get("model") or "",
            "owner": owners_of(n),
            "ownerColor": render_owners.colore(int(render_owners.gruppi(n, gruppi))),
            "artifacts": n.get("artifacts") or [],
            # Filtrato qui, non solo giudicato da validate(): un graph.json scritto a
            # mano puo' non essere mai passato da una mutazione, e un href javascript:/
            # data: non deve arrivare al browser solo perche' nessuno ha lanciato
            # 'atlas validate' prima di 'atlas render' (OWASP).
            "links": [l for l in (n.get("links") or []) if url_valido(l.get("url"))],
            "md": _ticket_md(ref, n["id"]),
        }
    # il marcatore, non il glifo nudo: per un nodo in lavorazione e' l'anello, lo
    # stesso che la card porta sulla mappa, qui fermo
    stati = {s: {"glyph": theme.glyph_html(s, 10), "label": t(STATE[s][1])} for s in ORDER}
    testo = json.dumps({"nodes": nodi, "states": stati}, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/json" id="atlas-data">{testo}</script>'


def sheet() -> str:
    """La vista Nodo: niente piu' '.scrim' ne' 'role=dialog'/'aria-modal', non
    e' una modale. La classe 'sheet' resta (sheet.js la cerca con
    'document.querySelector(".sheet")': cambiarla romperebbe l'intero modulo,
    non solo questa vista), affiancata da 'panel-vista panel-vista-nodo' per
    il selettore di render_notifiche.py.

    Fisso solo l'header (selettore schede piu' su, chip e titolo qui dentro):
    domanda, corpo markdown e artefatti scorrono insieme dentro '.sheet-scroll',
    non piu' la domanda fissa in testa e gli artefatti fissi in coda come prima
    di S13. '.sheet-body' resta il bersaglio che sheet.js sovrascrive con
    'innerHTML' (vedi corpo() li'): deve restare un fratello di
    '.sheet-question'/'.sheet-artifacts' dentro lo scroll, mai un loro genitore,
    o ogni rendering del markdown li cancellerebbe insieme al contenuto vecchio."""
    return (
        f'<div class="panel-vista panel-vista-nodo sheet" data-empty="{escape(t("render.sheet_vuoto"))}"'
        # la pillola di un nodo senza assegnatari (issue #34): stessa chiave
        # della card, mai 'render.non_assegnati' che conta piu' nodi insieme
        f' data-anonimo="{escape(t("render.anonimo"))}"'
        f' data-artefatti-label="{escape(t("render.sheet_artefatti"))}"'
        # le etichette del click-to-copy viaggiano nel markup, non nel JS, che resta
        # neutro di lingua: le rilegge da qui quando compone il titolo della scheda
        f' data-copia="{escape(t("render.copia"))}" data-copiato="{escape(t("render.copiato"))}">'
        '<header class="sheet-head"><div class="sheet-chips"></div>'
        f'<button type="button" class="sheet-close" aria-label="{escape(t("render.sheet_chiudi"))}">✕</button>'
        '<h2 class="sheet-title"></h2></header>'
        '<div class="sheet-scroll"><p class="sheet-question"></p>'
        '<div class="sheet-links"></div>'
        '<div class="sheet-body md"></div>'
        '<ul class="sheet-artifacts"></ul></div>'
        f'<footer class="sheet-foot"><a class="sheet-raw" target="_blank">{t("render.sheet_apri_file")}</a></footer>'
        '</div>'
    )
