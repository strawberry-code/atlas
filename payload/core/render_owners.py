"""Le assegnazioni nella dashboard: chi ha quali nodi, e il filtro per persona.

Gli stati sono cinque e si conoscono da sempre (theme.py); le persone no, quindi
le regole CSS che le riguardano nascono qui insieme al markup. Nel selettore non
finisce mai il nome ma un indice numerico: un nome arriva dalla riga di comando,
e infilarlo dentro un selettore vorrebbe dire lasciare che chi lo scrive
componga il foglio di stile della pagina.

Le persone non hanno un colore proprio: sulla mappa il colore porta lo stato e
il bordo porta il ramo, e una terza scala cromatica renderebbe illeggibili le
prime due. Chi ha cosa si legge dal filtro e dal pannello, che accendono i nodi
di una persona sola.
"""
from __future__ import annotations

from html import escape

from .model import owners, owners_of
from .strings import t

NESSUNO = 0    # i nodi senza assegnatario stanno tutti nello stesso gruppo


def indice(data: dict) -> dict[str, int]:
    """nome -> indice stabile a partire da 1, nell'ordine alfabetico di owners()."""
    return {nome: i for i, nome in enumerate(owners(data), start=1)}


def gruppi(node: dict, idx: dict[str, int]) -> str:
    """Gli indici delle persone del nodo separati da uno spazio, '0' se nessuno."""
    return " ".join(str(idx[nome]) for nome in owners_of(node)) or str(NESSUNO)


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
    si ritrova una fila di controlli che non gli dicono niente.
    """
    if not idx:
        return ""
    quanti = owners(data)
    fuori = sum(1 for n in data["nodes"] if not owners_of(n))
    voci = [
        f'<button type="button" class="chip who" data-owner="{i}">'
        f'{escape(nome)} <b>{len(quanti[nome])}</b></button>'
        for nome, i in idx.items()
    ]
    if fuori:
        voci.append(f'<button type="button" class="chip who none" data-owner="{NESSUNO}">'
                    f'{t("render.non_assegnati")} <b>{fuori}</b></button>')
    return "".join(voci)


def panel(data: dict, idx: dict[str, int]) -> str:
    """Il blocco laterale: chi lavora su cosa, con la stessa presa del chip."""
    if not idx:
        return ""
    quanti = owners(data)
    fuori = [n["id"] for n in data["nodes"] if not owners_of(n)]
    voci = [
        f'<li data-owner="{i}"><b>{escape(nome)}</b>'
        f'<span class="tag">{len(quanti[nome])}</span></li>'
        for nome, i in idx.items()
    ]
    if fuori:
        voci.append(f'<li data-owner="{NESSUNO}">{t("render.non_assegnati")}'
                    f'<span class="tag">{len(fuori)}</span></li>')
    return (f'<section class="blocco"><h2>{t("render.assegnazioni")}</h2>'
            f'<ul>{"".join(voci)}</ul></section>')
