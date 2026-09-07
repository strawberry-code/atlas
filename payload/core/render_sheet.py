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

from . import theme
from .config import Graph
from .model import owners_of
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


def data_island(ref: Graph, data: dict, front_ids: set[str]) -> str:
    """Nodi, ticket e etichette di stato, incorporati per la side sheet.

    La sequenza '</' viene spezzata: dentro un blocco script anche un banale
    '</p>' nel markdown di un ticket chiuderebbe il tag e romperebbe la pagina.
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
            "artifacts": n.get("artifacts") or [],
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
    il selettore di render_notifiche.py."""
    return (
        f'<div class="panel-vista panel-vista-nodo sheet" data-empty="{escape(t("render.sheet_vuoto"))}"'
        f' data-owner-label="{escape(t("render.sheet_assegnato"))}"'
        f' data-artefatti-label="{escape(t("render.sheet_artefatti"))}"'
        # le etichette del click-to-copy viaggiano nel markup, non nel JS, che resta
        # neutro di lingua: le rilegge da qui quando compone il titolo della scheda
        f' data-copia="{escape(t("render.copia"))}" data-copiato="{escape(t("render.copiato"))}">'
        '<header class="sheet-head"><div class="sheet-chips"></div>'
        f'<button type="button" class="sheet-close" aria-label="{escape(t("render.sheet_chiudi"))}">✕</button>'
        '<h2 class="sheet-title"></h2><p class="sheet-question"></p></header>'
        '<div class="sheet-body md"></div>'
        '<ul class="sheet-artifacts"></ul>'
        f'<footer class="sheet-foot"><a class="sheet-raw" target="_blank">{t("render.sheet_apri_file")}</a></footer>'
        '</div>'
    )
