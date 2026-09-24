"""La riga di pillole in fondo alla card del nodo: assegnatari, modo, ramo.

Spezzato da render_svg.py quando questa riga (issue #34, il tag "chi ce l'ha
in carico" sulla card) lo ha fatto sfondare le 200 righe: qui vive solo la
misura e il disegno delle pillole, render_svg.py resta il layout e
l'assemblaggio della card (geometria, canvas, riga id/titolo). La geometria
della card (PAD_IN, W, l'altezza della riga) resta li': arriva qui come
parametro, non come import, per non far dipendere un modulo di disegno da un
altro solo per tre numeri.

Una pillola si misura da sola: il font e' monospace (JetBrains Mono), quindi
la larghezza di un testo e' sempre caratteri * CHAR_W, senza bisogno di un
motore JS che la misuri dopo il primo paint - questa pagina non ne ha uno
prima. Un elenco di assegnatari che non ci sta si accorcia in una pillola
'+N', mai in un nome troncato a meta'.
"""
from __future__ import annotations

from html import escape

from . import theme
from .model import owners_of
from .strings import t

PILL_FONT, CHAR_W, PILL_PAD, PILL_GAP = 10.5, 6.3, 7, 6
BRANCH_ICON = 16


def misura(testo: str) -> float:
    return len(testo) * CHAR_W + PILL_PAD * 2


def _pill(x: float, y: float, h: float, w: float, testo: str, *, fill: str = "",
          stroke: str = "", classe_testo: str) -> str:
    """Rettangolo arrotondato piu' testo mono centrato, larghezza gia' decisa
    da chi chiama (misura())."""
    tinta = f'fill="{fill}"' if fill else f'fill="none" stroke="{stroke}"'
    return (f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="{h / 2}" {tinta}/>'
            f'<text x="{x + w / 2:.1f}" y="{y + h / 2 + 4}" text-anchor="middle" '
            f'class="{classe_testo}">{escape(testo)}</text>')


def _assegnatario(x: float, y: float, h: float, w: float, testo: str, assegnato: bool, tinta: str) -> str:
    """Piena e nel colore dell'insieme se il nodo ha assegnatari (stessa tinta
    del pannello assegnazioni, render_owners.colore() - riusata, mai
    ricalcolata); a contorno e neutra come il badge del modo se non li ha
    (Anonimo) o se, per qualche chiamante che non passa un indice vero (senza
    tinta con assegnato=True e' un errore di chi chiama, non un nodo davvero
    senza assegnatari), la tinta non e' arrivata: meglio una pillola neutra
    ma leggibile che testo bianco su niente."""
    if assegnato and tinta:
        return _pill(x, y, h, w, testo, fill=tinta, classe_testo="npill-testo")
    return _pill(x, y, h, w, testo, stroke="var(--border-strong)", classe_testo="npill-modo")


def riga(node: dict, x: float, y: float, *, pad_in: float, w_card: float, pill_y: float,
         pill_h: float, tinta: str, ramo_colore: str, ramo_indice: int) -> str:
    """La riga in fondo alla card: pillole degli assegnatari a sinistra, il
    badge del modo a contorno e la figura del ramo a destra.

    Prima di mostrare un nome per intero si verifica che resti spazio anche
    per un'eventuale pillola '+N' che riassuma quanto rimane dopo di lui:
    senza quella riserva una pillola piena poteva finire a ridosso del limite
    e la '+N' successiva sforare oltre il badge del modo (misurata, non solo
    supposta - la riserva e' quello che tiene le due cose separate)."""
    py = y + pill_y
    nomi = owners_of(node)
    assegnato = bool(nomi)
    etichette = [nome if len(nome) <= 16 else nome[:15] + "…" for nome in nomi] if assegnato \
        else [t("render.anonimo")]
    modo_w = misura(node["mode"])
    limite = x + w_card - pad_in - BRANCH_ICON - PILL_GAP - modo_w - PILL_GAP
    n = len(etichette)
    out, cx = [], x + pad_in
    for i, nome in enumerate(etichette):
        w = misura(nome)
        resto = n - i - 1
        riserva = misura(f"+{resto}") + PILL_GAP if resto > 0 else 0
        if cx + w + riserva > limite and resto > 0:
            nome, w = f"+{n - i}", misura(f"+{n - i}")
            out.append(_assegnatario(cx, py, pill_h, w, nome, assegnato, tinta))
            cx += w + PILL_GAP
            break
        out.append(_assegnatario(cx, py, pill_h, w, nome, assegnato, tinta))
        cx += w + PILL_GAP
    out.append(_pill(x + w_card - pad_in - BRANCH_ICON - PILL_GAP - modo_w, py, pill_h, modo_w,
                     node["mode"], stroke="var(--border-strong)", classe_testo="npill-modo"))
    out.append(f'<g class="bmark" transform="translate({x + w_card - pad_in - BRANCH_ICON},'
              f'{py + (pill_h - BRANCH_ICON) / 2}) scale({BRANCH_ICON / 24})">'
              f'<path d="{theme.shape_of(ramo_indice)}" fill="{ramo_colore}"/></g>')
    return "".join(out)
