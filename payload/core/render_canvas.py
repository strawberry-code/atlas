"""Il contenitore della mappa: viewport, pannello col transform, i Controls
Grafite e la minimap (C05), e nient'altro.

Spezzato da render.py (F01), che tratteneva insieme la topbar, i pannelli e
il canvas: il ramo Canvas e il ramo Superficie si sarebbero contesi lo stesso
file per il resto del progetto. Il confine di proprieta' e' questo: qui vive
SOLO '<main class="map">', il suo '<div class="viewport">' (il contenitore che
ritaglia, canvas.css) con dentro '<div class="pannello">' (quello che porta
il transform translate/scale di canvas.js, C02) che chiama render_svg.canvas
per il disegno di nodi e archi, i Controls (zoom avanti/indietro, rinquadra,
lucchetto) e il contenitore vuoto della minimap, che minimap.js popola da solo
leggendo l'SVG gia' disegnato (niente layout duplicato lato server). La
legenda degli stati e il suggerimento sotto la mappa restano proprieta' di
render.py, che li passa qui gia' costruiti come markup opaco: sono contenuto
descrittivo, non la superficie di navigazione, ma vivono dentro lo stesso
contenitore perche' sono posizionati in absolute rispetto a '.map' (vedi
canvas.css), e spostarli fuori romperebbe il layout. La topbar, la colonna dei
pannelli e l'assemblaggio dell'intera pagina restano interamente a render.py.
render_svg.py continua a disegnare i nodi ed e' chiamato da qui, non piu' da
render.py. render_lite.py (S09) non passa da qui: costruisce il suo '.viewport'
da solo, senza '.pannello' ne' canvas.js, perche' e' la pagina statica senza
JavaScript (vedi il suo docstring).
"""
from __future__ import annotations

from html import escape

from . import render_svg
from .strings import t

# Le quattro icone dei Controls, viewBox 24x24: forme piene (nessun fill/stroke
# proprio tranne la gruccia del lucchetto), perche' la ricetta di Grafite
# '.gf-controls-button svg{fill:var(--ink)}' colora per eredita' e un path con
# un fill esplicito la scavalcherebbe restando vuoto (canvas-contract.md S6).
_ICONA_IN = '<path d="M11 4h2v7h7v2h-7v7h-2v-7H4v-2h7z"/>'
_ICONA_OUT = '<path d="M4 11h16v2H4z"/>'
_ICONA_FIT = ('<path d="M4 4H10V6H6V10H4Z M20 4H14V6H18V10H20Z '
              'M4 20V14H6V18H10V20Z M20 20V14H18V18H14V20Z"/>')
_ICONA_LUCCHETTO = (
    '<path d="M8 10V7a4 4 0 0 1 8 0v3" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round"/><rect x="5" y="10" width="14" height="10" rx="2"/>'
)
# freccia che torna indietro su se stessa: il bottone che riporta le card
# trascinate al layout calcolato (C10, positions.js se lo ascolta direttamente,
# nessun evento su canvas.js: non e' uno zoom).
_ICONA_RIPRISTINA = (
    '<path d="M12 4V1L7 6l5 5V8a5 5 0 1 1-4.9 6H5.03A7 7 0 1 0 12 4z"/>'
)


def _bottone(azione: str, chiave: str, icona: str) -> str:
    return (
        f'<button type="button" class="gf-controls-button" data-zoom="{azione}" '
        f'aria-label="{escape(t(chiave))}"><svg viewBox="0 0 24 24" aria-hidden="true">{icona}</svg></button>'
    )


def _controls() -> str:
    """Zoom avanti/indietro, rinquadra e il lucchetto che blocca l'interazione
    col canvas (pan, rotella, doppio clic, minimap: vedi canvas.js/minimap.js).
    Sostituiscono i tre bottoni di zoom di prima; vestiti con le ricette
    '.gf-controls'/'.gf-controls-button' di Grafite (G04), che qui non si
    riscrivono. Le due varianti testuali del lucchetto (bloccato/sbloccato)
    viaggiano gia' tradotte nei data-attribute: canvas.js si limita a
    rileggerle al clic, senza toccare il catalogo lingua a runtime."""
    bottoni = (
        _bottone("in", "render.zoom_in", _ICONA_IN)
        + _bottone("out", "render.zoom_out", _ICONA_OUT)
        + _bottone("fit", "render.zoom_fit", _ICONA_FIT)
    )
    etichetta_blocca, etichetta_sblocca = escape(t("render.zoom_lock")), escape(t("render.zoom_unlock"))
    lucchetto = (
        '<button type="button" class="gf-controls-button" data-lock aria-pressed="false" '
        f'aria-label="{etichetta_blocca}" data-label-lock="{etichetta_blocca}" '
        f'data-label-unlock="{etichetta_sblocca}"><svg viewBox="0 0 24 24" aria-hidden="true">'
        f'{_ICONA_LUCCHETTO}</svg></button>'
    )
    # riporta al layout calcolato le card trascinate a mano (C10): positions.js
    # lo ascolta di persona, non passa da canvas.js perche' non e' uno zoom.
    ripristina = (
        '<button type="button" class="gf-controls-button" data-reset-layout '
        f'aria-label="{escape(t("render.layout_reset"))}"><svg viewBox="0 0 24 24" '
        f'aria-hidden="true">{_ICONA_RIPRISTINA}</svg></button>'
    )
    return f'<div class="controls gf-controls">{bottoni}{lucchetto}{ripristina}</div>'


def _minimap() -> str:
    """Contenitore vuoto: minimap.js lo popola leggendo le posizioni e gli
    stati gia' disegnati da render_svg.canvas, non serve markup lato server.
    aria-hidden perche' e' un widget solo-puntatore (drag/rotella), non
    raggiungibile da tastiera: un pannello Controls separato lo e' gia' (S6)."""
    return '<div class="minimap gf-minimap" aria-hidden="true"></div>'


def mappa(data: dict, front_ids: set[str], gruppi: dict[str, int],
          legenda: str, hint: str) -> str:
    """Il contenitore '<main class="map">': viewport con dentro il pannello
    (quello che canvas.js trasforma) e la mappa disegnata da render_svg.canvas,
    poi legenda, Controls e minimap (in quest'ordine nel markup, che e' quello
    che canvas.css assume per il posizionamento absolute), poi il suggerimento.
    'legenda' e 'hint' sono gia' pronti, costruiti da render.py."""
    return (
        f'<main class="map"><div class="viewport"><div class="pannello">'
        f'{render_svg.canvas(data, front_ids, gruppi)}</div></div>'
        f'<div class="legend">{legenda}</div>{_controls()}{_minimap()}'
        f'<p class="hint">{hint}</p></main>'
    )
