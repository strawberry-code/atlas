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


def css_class(stato: str) -> str:
    return f"st-{stato}"


def state_of(node: dict, front_ids: set[str]) -> str:
    """Lo stato visivo non e' lo stato del nodo: 'open' si biforca in prendibile o bloccato."""
    if node["status"] in ("closed", "out-of-scope"):
        return node["status"]
    if node["status"] == "claimed":
        return "claimed"
    return "frontier" if node["id"] in front_ids else "blocked"
