"""Le righe '<li>' dei pannelli della colonna sinistra, spezzate da render_panels.py
perche' quel file faceva due lavori: costruire ogni riga (qui) e assemblare i
pannelli attorno (li'). Ogni funzione ritorna solo la lista di stringhe '<li>',
gia' in veste .row-dense (G03): id/branch in evidenza, un'etichetta e un badge
o chip-state che si rivela all'hover ('.reveal-on-hover'). L'involucro
'.panel-dense'/'.blocco' e l'accensione sulla mappa (data-hl) restano a chi
chiama, in render_panels.py.
"""
from __future__ import annotations

from html import escape

from . import claims, theme
from .strings import t

# claim_state() -> (classe .chip-state, chiave del catalogo)
CLAIM_CHIP = {
    "live": ("ok", "render.claim_live"),
    "idle": ("warn", "render.claim_idle"),
    "dead": ("error", "render.claim_dead"),
}


def frontiera(front: list[dict]) -> list[str]:
    """Un nodo sospeso sta in frontiera come gli altri, ma il chip che lo dice
    resta visibile senza hover: e' il motivo per cui lo si sceglie o lo si evita."""
    sospeso = (f'<span class="chip-state warn"><i class="chip-state-dot"></i>'
               f'{t("state.suspended")}</span>')
    return [
        f'<li class="row-dense" data-node="{n["id"]}"><b>{n["id"]}</b>'
        f'<span class="row-dense-label">{escape(n["title"])}</span>'
        f'<span class="row-dense-meta reveal-on-hover">{n["type"]}·{n["mode"]}</span>'
        f'{sospeso if n["status"] == "suspended" else ""}</li>'
        for n in front
    ]


def rami(data: dict) -> list[str]:
    conteggi = {k: 0 for k in data["branches"]}
    for node in data["nodes"]:
        conteggi[node["branch"]] += 1
    return [
        f'<li class="row-dense" data-branch="{escape(k)}">'
        f'{theme.shape_svg(i, r.get("color", theme.BRANCH_FALLBACK), 11)}'
        f'<span class="row-dense-label">{escape(r["label"])}</span>'
        f'<span class="badge-count muted reveal-on-hover">{conteggi[k]}</span></li>'
        for i, (k, r) in enumerate(data["branches"].items())
    ]


def domande(aperte: list[dict], vecchie: set[str]) -> list[str]:
    voci = []
    for q in aperte:
        invecchiata = q["id"] in vecchie
        stato_txt = t("render.domanda_invecchiata") if invecchiata else t("render.domanda_aperta")
        chip_classe = "warn" if invecchiata else "neutral"
        voci.append(
            f'<li class="row-dense"><b>{escape(q["id"])}</b>'
            f'<span class="row-dense-label">{escape(q["question"])}</span>'
            f'<span class="row-dense-meta reveal-on-hover">{escape(q["origin"])}</span>'
            f'<span class="chip-state {chip_classe} reveal-on-hover">'
            f'<i class="chip-state-dot"></i>{stato_txt}</span></li>'
        )
    return voci


def in_lavorazione(presi: list[dict], agente: dict) -> list[str]:
    voci = []
    for n in presi:
        chip_classe, chiave = CLAIM_CHIP[claims.claim_state(n, agente)]
        voci.append(
            f'<li class="row-dense" data-node="{n["id"]}"><b>{n["id"]}</b>'
            f'<span class="row-dense-label">{escape(n["title"])}</span>'
            f'<span class="row-dense-meta reveal-on-hover">{escape(n["assignee"] or "?")}</span>'
            f'<span class="chip-state {chip_classe} reveal-on-hover">'
            f'<i class="chip-state-dot"></i>{t(chiave)}</span></li>'
        )
    return voci


def chiusi(nodi: list[dict]) -> list[str]:
    return [
        f'<li class="row-dense" data-node="{n["id"]}"><b>{n["id"]}</b>'
        f'<span class="row-dense-label">{escape(n["title"])}</span>'
        f'<span class="row-dense-meta reveal-on-hover">'
        f'{escape(n.get("cost") or t("render.costo_ignoto"))}</span></li>'
        for n in nodi
    ]
