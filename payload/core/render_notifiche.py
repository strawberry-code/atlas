"""Pannello destro della dashboard: un contenitore solo con due viste, Notifiche
e Nodo (S11). Prima erano due cose separate: le Interactions qui, il ticket
come scheda modale a schermo intero (render_sheet.py, col velo sfocato). Ora
condividono lo stesso contenitore, la stessa apertura/chiusura (il toggle qui
sotto) e un selettore per scegliere quale guardare: la vista Nodo e' presa
cosi' com'e' da render_sheet.sheet(), che non e' piu' una modale.

Il rendering delle singole card di Interaction e' spezzato in
render_notif_cards.py: altrimenti sarebbero stati due lavori nello stesso
file, l'assemblaggio del pannello e il bucketing attenzione/attesa/risolte.
Il blocco Telegram (pairing one-tap e levetta muto per progetto) e' in
render_notif_telegram.py, spezzato via per la stessa ragione.

Il comportamento (quando la vista Nodo prende il posto di quella Notifiche,
cosa chiude il pannello, il bottone, la memoria dello stato in localStorage)
resta di S12: qui il selettore porta gia' 'data-vista' sui due bottoni, e la
vista di partenza e' quella statica scritta nel markup ('notifiche'). Nessun
JS in questo giro tocca quell'attributo.
"""
from __future__ import annotations

from datetime import datetime
from html import escape

from . import interactions_view, render_notif_cards, render_notif_telegram, render_sheet
from .config import Graph
from .strings import t


def _selettore() -> str:
    """Le due viste, un selettore solo: quale bottone sia 'attivo' lo decide
    S12 (qui restano gli 'aria-selected' statici coerenti col default)."""
    return (
        f'<div class="panel-selettore" role="tablist" aria-label="{escape(t("render.pannello_selettore"))}">'
        f'<button type="button" class="panel-tab" data-vista="notifiche" aria-selected="true">'
        f'{escape(t("render.notif_titolo"))}</button>'
        f'<button type="button" class="panel-tab" data-vista="nodo" aria-selected="false">'
        f'{escape(t("render.pannello_nodo"))}</button></div>'
    )


def panel(ref: Graph, data: dict, now: datetime | None = None) -> str:
    """Il pannello destro: badge sul numero di card che aspettano una persona,
    poi il selettore e le due viste. Legge il ledger solo attraverso
    interactions_view (project() per lo stato), mai 'interactions' a mano."""
    momento = now or datetime.now().astimezone()
    righe = interactions_view.project(data, now=momento)
    corpo_notifiche, n_aperte = render_notif_cards.sezioni(ref, data, righe, momento)
    badge = f'<span class="badge">{n_aperte}</span>' if n_aperte else ""
    vista_notifiche = (
        f'<div class="panel-vista panel-vista-notifiche">'
        f'{render_notif_telegram.blocco(ref)}{corpo_notifiche}</div>'
    )
    return (
        # data-azione-offline/data-pairing-*: gli unici testi che dashboard.js legge
        # dal markup, per disabilitare i bottoni offline ('atlas render', file://
        # senza server) e per lo stato del pairing senza un secondo catalogo lato JS.
        # data-vista: la vista mostrata all'apertura, letta dal foglio (notifiche.css);
        # nessuno script la cambia ancora (S12).
        f'<aside class="notifiche" data-vista="notifiche" '
        f'data-azione-offline="{escape(t("render.notif_azione_offline"))}"'
        f' data-azione-errore="{escape(t("render.notif_azione_errore"))}"'
        f' data-pairing-attesa="{escape(t("render.notif_pairing_attesa"))}"'
        f' data-pairing-connesso="{escape(t("render.notif_pairing_connesso"))}"'
        f' data-pairing-scaduto="{escape(t("render.notif_pairing_scaduto"))}"'
        f' data-pairing-rifiutato="{escape(t("render.notif_pairing_rifiutato"))}"'
        f' data-pairing-senza-gestore="{escape(t("render.notif_pairing_senza_gestore"))}"'
        f' data-pairing-senza-relay="{escape(t("render.notif_pairing_senza_relay"))}"'
        f' data-pairing-relay-muto="{escape(t("render.notif_pairing_relay_muto"))}"'
        f' data-pairing-ripiego="{escape(t("render.notif_pairing_ripiego"))}">'
        '<button type="button" class="notifiche-toggle" aria-expanded="true">'
        '<svg class="bell" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M6 9a6 6 0 1 1 12 0c0 4.2 1.4 5.8 2 6.4H4c.6-.6 2-2.2 2-6.4"/>'
        '<path d="M10 19.5a2 2 0 0 0 4 0"/></svg>'
        f'<h2>{escape(t("render.notif_titolo"))}</h2>{badge}'
        '<svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg>'
        f'</button><div class="notifiche-corpo">{_selettore()}{vista_notifiche}{render_sheet.sheet()}</div></aside>'
    )
