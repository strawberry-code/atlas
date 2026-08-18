"""La semantica visiva degli stati: glifo, etichetta, tratteggio, classe CSS.

Il colore porta lo stato, la forma porta il ramo, e uno stato si riconosce anche
in scala di grigi perche' ogni stato ha il suo glifo oltre al suo colore. I colori
veri pero' non stanno qui: vivono nei token di templates/dashboard.css, in doppia
tavola light/dark, e l'SVG li aggancia con la classe CSS (st-<stato>). E' quel che
rende possibile la dark mode senza rigenerare niente.
"""
from __future__ import annotations

# stato visivo -> glifo, chiave-etichetta (in strings_docs.py), tratteggio del bordo
STATE = {
    "frontier": ("▲", "state.frontier", None),
    "claimed": ("⬤", "state.claimed", None),
    "closed": ("✓", "state.closed", None),
    "blocked": ("·", "state.blocked", None),
    "out-of-scope": ("✕", "state.out_of_scope", "4 3"),
}

ORDER = ["frontier", "claimed", "blocked", "closed", "out-of-scope"]

# ripiego per un ramo senza colore dichiarato: neutro, leggibile su chiaro e scuro
BRANCH_FALLBACK = "#7d8da3"

# Il ramo si legge da una figura, non piu' da una banda di colore sul bordo: la
# banda era tre pixel di tinta, e due rami di colore vicino si confondevano; una
# figura si riconosce anche da lontano, in bianco e nero o con un deficit di
# visione dei colori. Path in una griglia 24x24, cosi' la stessa figura serve
# sulla card, nel pannello e nella scheda cambiando solo la scala.
SHAPES = {
    "circle": "M12 3a9 9 0 1 0 .01 0z",
    "square": "M4 4h16v16H4z",
    "triangle": "M12 3l9.5 17.5H2.5z",
    "diamond": "M12 2l10 10-10 10L2 12z",
    "star": "M12 2l2.9 6.5 7.1.7-5.3 4.8 1.5 7-6.2-3.6-6.2 3.6 1.5-7L2 9.2l7.1-.7z",
    # su una riga sola: spezzarlo in due letterali incollava due numeri senza
    # separatore ('1.9' + '1-1.2') e il cuore usciva deforme
    "heart": "M12 20.7L4.3 13c-2.1-2.1-2.1-5.4 0-7.5 2.1-2.1 5.4-2.1 7.5 0l.2.2.2-.2c2.1-2.1 5.4-2.1 7.5 0 2.1 2.1 2.1 5.4 0 7.5z",
    "hexagon": "M7.2 3h9.6l4.8 9-4.8 9H7.2l-4.8-9z",
    "cross": "M9 2h6v7h7v6h-7v7H9v-7H2V9h7z",
}
SHAPE_ORDER = list(SHAPES)


def shape_of(index: int) -> str:
    """La figura del ramo, per posizione. Dal nono ramo le figure ricominciano, e a
    distinguerli resta il colore: figura e colore non si ripetono insieme."""
    return SHAPES[SHAPE_ORDER[index % len(SHAPE_ORDER)]]


def shape_svg(index: int, colore: str, lato: int, classe: str = "bshape") -> str:
    """La figura pronta da inserire fuori dalla mappa, gia' dimensionata."""
    return (f'<svg class="{classe}" viewBox="0 0 24 24" width="{lato}" height="{lato}" '
            f'aria-hidden="true"><path d="{shape_of(index)}" fill="{colore}"/></svg>')


# L'anello dei nodi in lavorazione. Il disegno sta qui una volta sola: sulla card
# gira dentro l'SVG della mappa, nella legenda e nella scheda sta fermo in un tag
# HTML, e due disegni scritti a mano nei due posti finirebbero per non somigliarsi.
RING = {"r": 5.4, "spessore": 2.2, "tratto": "20 14"}


def ring_svg(lato: int, classe: str = "st-ring") -> str:
    """L'anello fermo, da mettere accanto a un'etichetta."""
    return (f'<svg class="{classe}" viewBox="-8 -8 16 16" width="{lato}" height="{lato}" '
            f'aria-hidden="true"><circle r="{RING["r"]}" fill="none" stroke="currentColor" '
            f'stroke-width="{RING["spessore"]}" stroke-linecap="round" '
            f'stroke-dasharray="{RING["tratto"]}"/></svg>')


def glyph_html(stato: str, lato: int = 11) -> str:
    """Il marcatore dello stato fuori dalla mappa: un glifo, o l'anello se il nodo
    e' in lavorazione."""
    return ring_svg(lato) if stato == "claimed" else STATE[stato][0]


def css_class(stato: str) -> str:
    return f"st-{stato}"


def state_of(node: dict, front_ids: set[str]) -> str:
    """Lo stato visivo non e' lo stato del nodo: 'open' si biforca in prendibile o bloccato."""
    if node["status"] in ("closed", "out-of-scope"):
        return node["status"]
    if node["status"] == "claimed":
        return "claimed"
    return "frontier" if node["id"] in front_ids else "blocked"
