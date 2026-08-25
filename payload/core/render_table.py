"""La vista tabellare della dashboard: stessi nodi di render_svg.py, righe e
colonne invece di un canvas. Alternativa al grafo, non un suo sostituto: le
due viste condividono lo stesso stato visivo (theme.state_of) e si scambiano
sotto lo stesso toggle assemblato in render.py.

Ogni riga porta data-node come le card della mappa: il clic la apre nella
stessa scheda-ticket, senza JavaScript dedicato a questa vista. L'ordinamento
e' tutto lato client (dashboard.js): ogni cella porta gia' un data-v pronto
al confronto, cosi' il JS non deve interpretare testo di dominio (uno stato
si ordina per gravita', non per alfabeto).
"""
from __future__ import annotations

from html import escape

from . import theme
from .model import owners_of
from .render_panels import costo_numerico
from .strings import t

_COLONNE = (
    "render.tbl_id", "render.tbl_titolo", "render.tbl_stato", "render.tbl_ramo",
    "render.tbl_tipo_modo", "render.tbl_assegnato", "render.tbl_costo", "render.tbl_dipendenze",
)


def _head() -> str:
    voci = "".join(
        f'<th scope="col" data-col="{i}" title="{escape(t("render.tbl_ordina"))}">{escape(t(chiave))}</th>'
        for i, chiave in enumerate(_COLONNE)
    )
    return f'<thead><tr>{voci}</tr></thead>'


def _td(html: str, sort: str) -> str:
    return f'<td data-v="{escape(sort)}">{html}</td>'


def _riga(node: dict, ramo: dict, i_ramo: int, stato: str) -> str:
    titolo = escape(node["title"])
    chi = owners_of(node)
    nomi = ", ".join(chi)
    costo = node.get("cost") or ""
    numero_costo = costo_numerico(costo) if costo else None
    deps = escape(", ".join(node["blockedBy"]) or t("render.libero"))
    tipo_modo = f'{node["type"]}·{node["mode"]}'
    celle = (
        _td(f'<code class="cp tid" data-copy="{escape(node["id"])}" '
            f'title="{escape(t("render.copia"))}" data-copiato="{escape(t("render.copiato"))}">'
            f'{escape(node["id"])}</code>', node["id"]),
        _td(f'<span class="tclip" title="{titolo}">{titolo}</span>', node["title"]),
        _td(f'<span class="tchip {theme.css_class(stato)}">{theme.glyph_html(stato, 10)} '
            f'{escape(t(theme.STATE[stato][1]))}</span>', str(theme.ORDER.index(stato))),
        _td(f'{theme.shape_svg(i_ramo, ramo.get("color", theme.BRANCH_FALLBACK), 10)} '
            f'{escape(ramo["label"])}', str(i_ramo)),
        _td(escape(tipo_modo), tipo_modo),
        _td(escape(nomi) if nomi else f'<i class="tmuted">{escape(t("render.tbl_non_assegnato"))}</i>', nomi),
        _td(escape(costo) if costo else f'<i class="tmuted">{escape(t("render.costo_ignoto"))}</i>',
            "" if numero_costo is None else f"{numero_costo:g}"),
        _td(f'<span class="tclip" title="{deps}">{deps}</span>', str(len(node["blockedBy"]))),
    )
    return f'<tr data-node="{escape(node["id"])}">{"".join(celle)}</tr>'


def table(data: dict, front_ids: set[str]) -> str:
    ordine_rami = list(data["branches"])
    righe = "".join(
        _riga(node, data["branches"][node["branch"]], ordine_rami.index(node["branch"]),
              theme.state_of(node, front_ids))
        for node in data["nodes"]
    )
    return f'<div class="tablewrap"><table class="gridtbl">{_head()}<tbody>{righe}</tbody></table></div>'
