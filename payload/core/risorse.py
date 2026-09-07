"""I template viaggiano dentro il pacchetto, non dentro il progetto.

Prima stavano dentro il progetto e si leggevano con Path: erano file
che nessuno modificava mai, e che a ogni aggiornamento del motore andavano riscritti.
Ora sono risorse del package, quindi importlib.resources e non open(): dentro un
zipapp i file dati non si aprono con Path, e quel percorso e' proprio quello che il
CLI usa in produzione.

Dai sorgenti (sviluppo e test) core/templates/ puo' non esistere ancora, perche' e'
build.py a copiarcelo da payload/templates/: in quel caso si legge da li'.
"""
from __future__ import annotations

from importlib.resources import files
from pathlib import Path

PACCHETTO = "core.templates"
# payload/core/risorse.py -> payload/templates/
SORGENTI = Path(__file__).resolve().parent.parent / "templates"


def leggi_template(nome: str) -> str:
    try:
        return (files(PACCHETTO) / nome).read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError):
        return (SORGENTI / nome).read_text(encoding="utf-8")


_FOGLI_DASHBOARD = [
    "grafite.fonts.inline.css",
    "grafite.offline.css",
    "tokens.css",
    "shell.css",
    "canvas.css",
    "legend.css",
    "edges.css",
    "sheet.css",
    "table.css",
    "notifiche.css",
]

# La pagina alleggerita (render_lite.py, S09) non porta ne' la scheda del
# ticket ne' il pannello Notifiche: fuori sheet.css e notifiche.css. Fuori
# anche grafite.fonts.inline.css, 208KB di font incorporati in base64: su
# Telegram ogni KB si vede, e grafite.offline.css lascia comunque i fallback
# di sistema gia' dichiarati in --sans/--display/--mono (nessun @import
# remoto: verificato, quel foglio non ne porta uno). Il resto (token, shell,
# canvas, legend, edges, table) e' cio' che il grafo e la tabella disegnano
# davvero in quella pagina.
_FOGLI_LITE = [f for f in _FOGLI_DASHBOARD
               if f not in {"grafite.fonts.inline.css", "sheet.css", "notifiche.css"}]


def leggi_css_dashboard() -> str:
    """Dashboard CSS: font Grafite, poi i token Grafite, poi gli otto fogli
    tematici di Atlas che li consumano, concatenati nell'ordine dichiarato.
    I due fogli grafite.* arrivano da un'altra repo (vedi la riga in testa a
    ciascuno) e non si toccano qui. Usato da render.py per la dashboard vera;
    render_lite.py prende il sottoinsieme di leggi_css_lite()."""
    return "".join(leggi_template(f) for f in _FOGLI_DASHBOARD)


def leggi_css_lite() -> str:
    """CSS della pagina alleggerita: il sottoinsieme di _FOGLI_DASHBOARD che
    le serve davvero (vedi il commento su _FOGLI_LITE), nello stesso ordine."""
    return "".join(leggi_template(f) for f in _FOGLI_LITE)


def leggi_js_dashboard() -> str:
    """Dashboard JavaScript: undici moduli per argomento concatenati nell'ordine dichiarato.
    Usato da render.py per il comportamento della dashboard.

    canvas.js prima di fitview.js/controls.js/minimap.js non e' un dettaglio:
    quei tre moduli dispatchano su '.viewport' al proprio caricamento (il
    rinquadro al mount, la prima lettura dei controlli/della minimap), e
    canvas.js dev'essere gia' in ascolto (C05). Fra loro tre l'ordine non conta,
    ognuno parla solo con canvas.js, mai con gli altri due.

    drag.js prima di positions.js (C10) e' lo stesso vincolo: positions.js
    applica il layout salvato al caricamento e chiede subito un ricalcolo
    degli archi con l'evento 'atlas:ricalcola-archi', e drag.js dev'essere
    gia' in ascolto, perche' e' l'unico che sa disegnare un arco. Entrambi
    prima di minimap.js, che legge le posizioni gia' spostate per disegnare
    una sagoma coerente con l'ultimo layout salvato.

    keyboard.js (C12) chiude il gruppo Canvas: legge le stesse card gia'
    disegnate (come minimap.js) e parla con canvas.js coi soli eventi che
    Controls/minimap gia' usano, quindi non ha un vincolo d'ordine suo -
    ma resta con gli altri moduli del suo ramo, non sparso altrove.

    edges.js (A05) non ha un vincolo di caricamento: legge '.sel' via
    MutationObserver invece che a un evento di un altro modulo, quindi non
    deve gia' trovare nessuno in ascolto. Resta qui, dopo drag.js di cui
    osserva le riscritture di 'd' in tempo reale, e prima dei moduli di
    chrome/scheda che non lo riguardano."""
    moduli = [
        "canvas.js",
        "drag.js",
        "positions.js",
        "fitview.js",
        "controls.js",
        "minimap.js",
        "keyboard.js",
        "edges.js",
        "chrome.js",
        "notifiche.js",
        "table.js",
        "sheet.js",
    ]
    return "".join(leggi_template(f) for f in moduli)


def elenco_template() -> list[str]:
    """I nomi disponibili, per chi deve controllare che una lingua sia completa."""
    try:
        return sorted(r.name for r in files(PACCHETTO).iterdir() if r.is_file())
    except ModuleNotFoundError:
        return sorted(p.name for p in SORGENTI.iterdir() if p.is_file())
