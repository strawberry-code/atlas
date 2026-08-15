"""La scheda del ticket dentro la dashboard: scheletro della side sheet e dati.

Spezzato da render.py perche' sono due lavori: la' l'assemblaggio della plancia,
qui tutto cio' che serve a leggere un ticket senza lasciare la pagina. I ticket
sono incorporati come JSON al momento della generazione, perche' da file://
nessuna fetch potrebbe leggerli dopo; il markdown lo trasforma il JavaScript
della pagina (templates/dashboard.js), qui viaggia grezzo.
"""
from __future__ import annotations

import json
import re
from html import escape

from . import theme
from .config import Graph
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
    for n in data["nodes"]:
        ramo = data["branches"][n["branch"]]
        nodi[n["id"]] = {
            "title": n["title"], "question": n["question"],
            "state": state_of(n, front_ids), "type": n["type"], "mode": n["mode"],
            "branchLabel": ramo["label"],
            "branchColor": ramo.get("color", theme.BRANCH_FALLBACK),
            "cost": n.get("cost") or "",
            "md": _ticket_md(ref, n["id"]),
        }
    stati = {s: {"glyph": STATE[s][0], "label": t(STATE[s][1])} for s in ORDER}
    testo = json.dumps({"nodes": nodi, "states": stati}, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/json" id="atlas-data">{testo}</script>'


def sheet() -> str:
    return (
        '<div class="scrim"></div>'
        f'<aside class="sheet" role="dialog" aria-modal="true" data-empty="{escape(t("render.sheet_vuoto"))}">'
        '<header class="sheet-head"><div class="sheet-chips"></div>'
        f'<button type="button" class="sheet-close" aria-label="{escape(t("render.sheet_chiudi"))}">✕</button>'
        '<h2 class="sheet-title"></h2><p class="sheet-question"></p></header>'
        '<div class="sheet-body md"></div>'
        f'<footer class="sheet-foot"><a class="sheet-raw" target="_blank">{t("render.sheet_apri_file")}</a></footer>'
        '</aside>'
    )
