"""Le assegnazioni nella dashboard: chi ha quali nodi, e il filtro per persona.

Gli stati sono cinque e si conoscono da sempre (theme.py); le persone no, quindi
le regole CSS che le riguardano nascono qui insieme al markup. Nel selettore non
finisce mai il nome ma un indice numerico: un nome arriva dalla riga di comando,
e infilarlo dentro un selettore vorrebbe dire lasciare che chi lo scrive
componga il foglio di stile della pagina.

Sulla card il colore di stato resta l'unico riempimento pieno e il bordo resta
del ramo: le persone hanno una tinta propria (colore(), sotto), ma la portano
solo le pillole degli assegnatari, mai la card intera, o la terza scala
cromatica renderebbe illeggibili le prime due. Chi ha cosa si legge anche dal
filtro e dal pannello, che accendono i nodi di un insieme di assegnatari alla
volta: una persona sola, oppure la squadra esatta che quel nodo ha.
"""
from __future__ import annotations

from html import escape

from .model import insiemi, owners_of
from .strings import t

NESSUNO = 0    # i nodi senza assegnatario stanno tutti nello stesso gruppo
SEPARATORE = " + "    # una squadra si legge come i suoi nomi uniti; il '+' nei nomi e' vietato

# Otto tinte, una per indice di insieme (vedi indice()/gruppi()): round-robin
# oltre l'ottava. Scelte scure a sufficienza da reggere testo bianco sopra (le
# pillole della card e della scheda, render_svg.py/sheet.js), non tarate sui
# token di stato (--st-*) perche' quelli restano il solo asse cromatico dello
# stato del nodo (Q001/Q03): un insieme di assegnatari e' un'altra domanda
# ("di chi e'"), non un'altra sfumatura della stessa. Un solo elenco, letto
# dal chip del filtro, dalla riga del pannello, dalla card e dalla scheda:
# quattro elenchi indipendenti prima o poi divergono.
PALETTE = (
    "#b45309", "#0f766e", "#7c3aed", "#be123c",
    "#0369a1", "#4d7c0f", "#a21caf", "#c2410c",
)


def colore(i: int) -> str:
    """La tinta di un insieme di assegnatari, stabile per indice. Nessuno
    (indice NESSUNO) non ha una tinta propria: torna stringa vuota, perche' i
    nodi senza assegnatario restano neutri e non vanno confusi con una vera
    persona che sia finita per caso sullo stesso indice."""
    return PALETTE[(i - 1) % len(PALETTE)] if i > NESSUNO else ""


def voci(data: dict) -> list[tuple[str, list[str]]]:
    """Le righe delle assegnazioni, etichetta e nodi, nell'ordine di insiemi().
    Una sola fonte per il pannello, i chip e gli indici, perche' le tre cose
    devono numerare le stesse righe nello stesso ordine."""
    return [(SEPARATORE.join(nomi), ids) for nomi, ids in insiemi(data).items()]


def indice(data: dict) -> dict[str, int]:
    """etichetta -> indice stabile a partire da 1, nell'ordine di voci()."""
    return {etichetta: i for i, (etichetta, _) in enumerate(voci(data), start=1)}


def gruppi(node: dict, idx: dict[str, int]) -> str:
    """L'indice dell'insieme a cui il nodo appartiene, '0' se non e' assegnato.

    Uno solo, perche' un nodo sta in un insieme e in nessun altro: e' quel che
    rende il filtro leggibile, dato che il chip di una persona accende i suoi
    nodi soltanto e non quelli in cui e' uno dei partecipanti. Resta un attributo
    a lista (data-owners, selettori con ~=) perche' la resa non deve cambiare
    forma ogni volta che cambia il criterio di raggruppamento.
    """
    return str(idx.get(SEPARATORE.join(owners_of(node)), NESSUNO))


def css(idx: dict[str, int]) -> str:
    """Il filtro per persona, nelle due forme che hanno tutte le prese di questa
    pagina: il puntatore mostra in anteprima, il clic fissa finche' non si rifa'.

    Le regole si generano qui perche' dipendono da quante persone ci sono, e il
    selettore porta l'indice invece del nome per non far comporre a chi scrive dal
    terminale un pezzo di foglio di stile."""
    if not idx:
        return ""
    regole = []
    for i in (*idx.values(), NESSUNO):
        regole.append(f'body[data-owner="{i}"] .n:not([data-owners~="{i}"]){{opacity:.13}}')
        regole.append(f'.map:has(.legend .chip[data-owner="{i}"]:hover) .n:not([data-owners~="{i}"]),'
                      f'.side:has(li[data-owner="{i}"]:hover) ~ .map .n:not([data-owners~="{i}"])'
                      f'{{opacity:.13}}')
    regole.append("body[data-owner] path.edge{opacity:.25}")
    regole.append(".side:has(li[data-owner]:hover) ~ .map :is(path.edge,circle.port){opacity:.25}")
    return "".join(regole)


def chips(data: dict, idx: dict[str, int]) -> str:
    """La fila di chip in legenda: una persona per chip, piu' i non assegnati.

    Tace del tutto su un grafo senza assegnazioni: chi non usa questa parte non
    si ritrova una fila di controlli che non gli dicono niente. Il quadratino
    porta la stessa tinta di colore(): e' lo stesso indice che finisce sulla
    pillola della card e della scheda (issue #34), non un secondo calcolo.
    """
    if not idx:
        return ""
    fuori = sum(1 for n in data["nodes"] if not owners_of(n))
    righe = [
        f'<button type="button" class="chip who" data-owner="{idx[etichetta]}">'
        f'<i style="background:{colore(idx[etichetta])}"></i>'
        f'{escape(etichetta)} <b>{len(ids)}</b></button>'
        for etichetta, ids in voci(data)
    ]
    if fuori:
        righe.append(f'<button type="button" class="chip who none" data-owner="{NESSUNO}">'
                     f'<i style="background:var(--border-strong)"></i>'
                     f'{t("render.non_assegnati")} <b>{fuori}</b></button>')
    return "".join(righe)


def panel(data: dict, idx: dict[str, int]) -> str:
    """Il blocco laterale: chi lavora su cosa, con la stessa presa del chip.

    Veste .panel-dense/.row-dense/.badge-count (G03), come gli altri pannelli
    della colonna: 'blocco' resta accanto a 'panel-dense' solo perche' edges.css
    lo lega alla mappa, non porta piu' un aspetto suo (era il duplicato in
    shell.css, tolto insieme a questa migrazione).
    """
    if not idx:
        return ""
    fuori = [n["id"] for n in data["nodes"] if not owners_of(n)]
    righe = []
    for etichetta, ids in voci(data):
        # una squadra resta in tondo: nomina persone gia' elencate sopra, e il
        # grassetto la farebbe leggere come una quarta persona.
        nome = escape(etichetta)
        label = nome if SEPARATORE in etichetta else f"<b>{nome}</b>"
        righe.append(f'<li class="row-dense" data-owner="{idx[etichetta]}">'
                     f'<i class="who-dot" style="background:{colore(idx[etichetta])}"></i>'
                     f'<span class="row-dense-label">{label}</span>'
                     f'<span class="badge-count muted">{len(ids)}</span></li>')
    if fuori:
        righe.append(f'<li class="row-dense" data-owner="{NESSUNO}">'
                     f'<i class="who-dot" style="background:var(--border-strong)"></i>'
                     f'<span class="row-dense-label">{t("render.non_assegnati")}</span>'
                     f'<span class="badge-count muted">{len(fuori)}</span></li>')
    return (f'<section class="blocco panel-dense"><h2 class="eyebrow">{t("render.assegnazioni")}</h2>'
            f'<ul>{"".join(righe)}</ul></section>')
