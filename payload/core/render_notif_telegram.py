"""Il blocco Telegram in cima al pannello Notifiche: il bottone di pairing
one-tap (D05/A04) e la levetta muto per progetto (SS7-ter/1, che ribalta la
decisione 30). Spezzato da render_notifiche.py per la stessa ragione di
serve_pairing.py rispetto a serve.py: qui c'e' solo questo blocco, la' il
resto del pannello.
"""
from __future__ import annotations

import os
from html import escape

from . import capability, relay_client
from .config import Graph
from .strings import t


def _levetta(ref: Graph) -> str:
    """Accesa di default, un clic la spegne per un progetto riservato
    (SS11/11). Vuota se questa installazione non ha Telegram configurato
    (stesso gate di serve_notify._canali_attivi): senza, sarebbe una levetta
    su un canale che chi guarda non ha mai collegato, e chi lavora offline
    non deve vederla ne' sentirne parlare."""
    if relay_client.da_ambiente(os.environ) is None or capability.da_ambiente(os.environ) is None:
        return ""
    acceso = bool(ref.workspace.config.get("notify", {}).get("telegram_enabled", True))
    on, off = t("render.notif_muto_attivo"), t("render.notif_muto_silenziato")
    az_on, az_off = t("render.notif_muto_silenzia"), t("render.notif_muto_riattiva")
    return (
        '<div class="pairing-riga notif-muto-riga">'
        f'<button type="button" class="notif-muto" data-muto="{"on" if acceso else "off"}" '
        f'aria-pressed="{"true" if acceso else "false"}" data-stato-on="{escape(on)}" '
        f'data-stato-off="{escape(off)}" data-azione-on="{escape(az_on)}" '
        f'data-azione-off="{escape(az_off)}">'
        f'<span class="notif-muto-stato">{escape(on if acceso else off)}</span>'
        f'<span class="notif-muto-azione">{escape(az_on if acceso else az_off)}</span></button></div>'
    )


def blocco(ref: Graph) -> str:
    """Il bottone di pairing e' sempre presente (grilling 27), discreto,
    senza campi da compilare: dashboard.js fa il resto (POST/GET
    /pairing/telegram*, apertura del link t.me, poll dello stato). La levetta
    sta subito sotto, quando visibile. In fondo la promessa nulla di grilling
    33 ('servizio sperimentale, si puo' fermare quando vuole chi lo
    gestisce'): sempre a video, non solo dopo il tap, mai in un documento che
    nessuno legge."""
    return (
        '<div class="notif-canali">'
        '<div class="pairing-riga">'
        '<button type="button" class="pairing-telegram" data-pairing="telegram">'
        f'{escape(t("render.notif_pairing_bottone"))}</button>'
        '<span class="pairing-stato" aria-live="polite"></span>'
        '</div>'
        f'{_levetta(ref)}'
        f'<p class="pairing-nota">{escape(t("render.notif_pairing_promessa"))}</p>'
        '</div>'
    )
