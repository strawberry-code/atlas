"""Pannello destro Notifiche: le Interactions aperte, il run in attesa e le
risolte di oggi.

Le tre sezioni ricalcano il vocabolario di A02: 'open' e' 'Attenzione
richiesta', i tre stati terminali sono 'Risolte oggi'. 'In attesa' non e' uno
stato Interaction (A02 lo dice esplicito: e' il run o la consegna), quindi non
viene da interactions_view ma da run_state.py, letto cosi' com'e' in
report.show_run_status: nessuna azione, solo contesto su cosa sta facendo il
runner adesso.

Le azioni (data-interaction/data-action) le esegue dashboard.js con un POST a
'atlas serve' (B03): qui c'e' solo il markup, mai una chiamata diretta al
lifecycle. Il log di audit di ogni card e' un <details> nativo, chiuso di
default: contesto, artefatti e log restano consultazione su richiesta (A02),
mai contenuto della card stessa.

La card aperta porta anche 'data-interaction' sul suo <li>, non solo sui
bottoni: e' quanto basta a dashboard.js (C02) per riconoscere una card gia'
vista da una nuova, senza inventare un secondo indice.

In cima al corpo del pannello c'e' anche il blocco Telegram (pairing one-tap
e levetta muto per progetto): render_notif_telegram.py, spezzato via per la
stessa ragione di serve_pairing.py rispetto a serve.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from html import escape

from . import interactions_view, notify, render_notif_telegram
from .config import Graph
from .run_state import RunState
from .strings import t

_TIPO_EVENTO = {
    "opened": "render.notif_log_aperta", "resolved": "render.notif_log_risolta",
    "cancelled": "render.notif_log_annullata", "expired": "render.notif_log_scaduta",
}


def _breve(delta: timedelta) -> str:
    minuti = int(abs(delta).total_seconds() // 60)
    if minuti < 60:
        return f"{minuti}m"
    if minuti < 1440:
        return f"{minuti // 60}h{minuti % 60:02d}"
    return f"{minuti // 1440}g"


def _scadenza(urgency: timedelta) -> str:
    breve = _breve(urgency)
    return (t("render.notif_scaduta", t=breve) if urgency.total_seconds() < 0
            else t("render.notif_scade", t=breve))


def _azioni(voce: dict) -> str:
    if not voce["allowedActions"]:
        return ""
    bottoni = "".join(
        f'<button type="button" data-interaction="{escape(voce["id"])}" '
        f'data-action="{escape(azione["id"])}">{escape(azione["label"])}</button>'
        for azione in voce["allowedActions"]
    )
    return f'<div class="notif-azioni">{bottoni}</div>'


def _log(data: dict, voce: dict, now: datetime) -> str:
    """Il log di audit della card, chiuso di default: consultazione su
    richiesta (A02), niente da leggere finche' non si apre il <details>."""
    eventi = interactions_view.events_of(data, voce["id"])
    if not eventi:
        return ""
    righe = "".join(
        f'<li>{escape(t(_TIPO_EVENTO.get(ev["type"], "render.notif_log_evento"), tipo=ev["type"]))} '
        f'· {escape(ev["by"])} · {t("render.notif_fa", t=_breve(now - datetime.fromisoformat(ev["at"])))}</li>'
        for ev in eventi
    )
    return (f'<details class="notif-log"><summary>{escape(t("render.notif_log_titolo"))}</summary>'
            f'<ul>{righe}</ul></details>')


def _card_aperta(data: dict, voce: dict, now: datetime) -> str:
    return (
        f'<li class="notif-card notif-attenzione" data-node="{escape(voce["node"])}" '
        f'data-interaction="{escape(voce["id"])}">'
        f'<p class="notif-testo">{escape(voce["summary"])}</p>'
        f'<p class="notif-meta"><span class="tag">{escape(voce["node"])}</span>'
        f'<span class="tag urgente">{_scadenza(voce["urgency"])}</span></p>'
        f'{_azioni(voce)}{_log(data, voce, now)}</li>'
    )


def _card_risolta(data: dict, voce: dict, now: datetime) -> str:
    return (
        f'<li class="notif-card notif-chiusa" data-node="{escape(voce["node"])}">'
        f'<p class="notif-testo">{escape(voce["summary"])}</p>'
        f'<p class="notif-meta"><span class="tag">{escape(voce["node"])}</span>'
        f'<span class="tag">{t("render.notif_fa", t=_breve(voce["resolvedAge"]))}</span></p>'
        f'{_log(data, voce, now)}</li>'
    )


def _consegna_fallita(ref: Graph, data: dict, node_id: str) -> str:
    """SS7-ter/3: se l'Interaction aperta su questo nodo ha un canale la cui
    consegna si e' esaurita senza riuscire, la riga lo dice qui. Non si
    cattura NotifyStateError: un notify-state.json corrotto e' una diagnosi
    per chi guarda la dashboard, non un dettaglio da inghiottire in silenzio
    (stesso comportamento di RunStateError, qui sopra). Nessun ritentativo
    ne' coda in piu' (grilling 22): si legge solo cio' che notify.dispatch
    ha gia' concluso."""
    interazione = next((r for r in data.get("interactions", [])
                        if r["nodeId"] == node_id and r["status"] == "open"), None)
    if interazione is None:
        return ""
    stato = notify.NotifyState(ref.notify_state_path, ref.slug)
    falliti = stato.failed_channels(interazione["id"])
    if not falliti:
        return ""
    testo = t("render.notif_consegna_fallita", canale=", ".join(falliti))
    return f'<p class="notif-guasto">{escape(testo)}</p>'


def _in_attesa(ref: Graph, data: dict) -> list[str]:
    """Il run in attesa (contesto, nessuna azione): niente se non c'e' un run
    attivo, o se non e' fermo su 'waiting'. Non si cattura RunStateError: un
    run-state.json corrotto e' una diagnosi per chi guarda la dashboard, non un
    dettaglio da inghiottire in silenzio (stesso comportamento di report.py)."""
    stato = RunState.read(ref.run_state_path)
    if stato is None or stato.get("status") != "waiting":
        return []
    frase = (t("render.notif_run_nodo", nodo=stato["node"]) if stato.get("node")
             else t("render.notif_run_generico"))
    guasto = _consegna_fallita(ref, data, stato["node"]) if stato.get("node") else ""
    return [f'<li class="notif-card notif-contesto"><p class="notif-testo">{escape(frase)}</p>{guasto}</li>']


def _sezione(titolo: str, cards: list[str], vuoto: str) -> str:
    corpo = "".join(cards) or f'<p class="notif-vuoto">{escape(vuoto)}</p>'
    return f'<section class="notif-sezione"><h3>{escape(titolo)}</h3><ul>{corpo}</ul></section>'


def panel(ref: Graph, data: dict, now: datetime | None = None) -> str:
    """Il pannello destro: badge sul numero di card che aspettano una persona,
    poi le tre sezioni. Legge il ledger solo attraverso interactions_view
    (project() per lo stato, events_of() per il log su richiesta), mai
    'interactions' o 'events' a mano."""
    momento = now or datetime.now().astimezone()
    righe = interactions_view.project(data, now=momento)
    aperte = [v for v in righe if v["status"] == "open"]
    risolte_oggi = [v for v in righe if v["status"] != "open"
                    and (momento - v["resolvedAge"]).date() == momento.date()]
    sezioni = (
        render_notif_telegram.blocco(ref)
        + _sezione(t("render.notif_attenzione"), [_card_aperta(data, v, momento) for v in aperte],
                   t("render.notif_attenzione_vuota"))
        + _sezione(t("render.notif_in_attesa"), _in_attesa(ref, data), t("render.notif_in_attesa_vuota"))
        + _sezione(t("render.notif_risolte"), [_card_risolta(data, v, momento) for v in risolte_oggi],
                   t("render.notif_risolte_vuota"))
    )
    badge = f'<span class="badge">{len(aperte)}</span>' if aperte else ""
    return (
        # data-azione-offline/data-pairing-*: gli unici testi che dashboard.js legge
        # dal markup, per disabilitare i bottoni offline ('atlas render', file://
        # senza server) e per lo stato del pairing senza un secondo catalogo lato JS.
        f'<aside class="notifiche" data-azione-offline="{escape(t("render.notif_azione_offline"))}"'
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
        f'</button><div class="notifiche-corpo">{sezioni}</div></aside>'
    )
