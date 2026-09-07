"""Le card del pannello destro, vista Notifiche: bucketing di attenzione/attesa/
risolte, azioni al massimo due per card, log di audit su richiesta.

Spezzato da render_notifiche.py (S11) perche' da quando quel file assembla
anche il contenitore condiviso con la vista Nodo (toggle, selettore, le due
viste) erano due lavori nello stesso file: qui resta solo il rendering delle
singole card e la loro segmentazione in sezioni, la' l'assemblaggio del
pannello.

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
"""
from __future__ import annotations

from datetime import datetime, timedelta
from html import escape

from . import interactions_view, notify
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
    # La prima azione e' sempre quella che fa avanzare (retry/confirm/acknowledge:
    # vedi autopilot._card e claims.chiedi_umano), le altre sono un rifiuto
    # (cancel/decline): '.btn-primary' nera piena per la prima, '.btn-ghost' per
    # il resto, cosi' 'Riprova' e 'Annulla' non sono piu' lo stesso bottone due
    # volte (Q03/Q002).
    bottoni = "".join(
        f'<button type="button" class="{"btn-primary" if i == 0 else "btn-primary btn-ghost"}" '
        f'data-interaction="{escape(voce["id"])}" '
        f'data-action="{escape(azione["id"])}">{escape(azione["label"])}</button>'
        for i, azione in enumerate(voce["allowedActions"])
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
    # 'scaduta' e' un segnale in piu' sullo stesso tag, non un secondo stato:
    # una scadenza gia' passata conta come errore (--down), una che si
    # avvicina resta un avviso (--warn). Il colore porta l'informazione che
    # il testo gia' dice a parole, non la ripete come decoro.
    classe_tag = "tag urgente scaduta" if voce["urgency"].total_seconds() < 0 else "tag urgente"
    return (
        f'<li class="notif-card notif-attenzione" data-node="{escape(voce["node"])}" '
        f'data-interaction="{escape(voce["id"])}">'
        f'<p class="notif-testo">{escape(voce["summary"])}</p>'
        f'<p class="notif-meta"><span class="tag">{escape(voce["node"])}</span>'
        f'<span class="{classe_tag}">{_scadenza(voce["urgency"])}</span></p>'
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
    # chip-state error (Grafite): stesso segnale semantico di un canale rotto,
    # non un colore inventato apposta per questa riga.
    return (f'<p class="notif-guasto"><span class="chip-state error">'
            f'<i class="chip-state-dot"></i>{escape(testo)}</span></p>')


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


def sezioni(ref: Graph, data: dict, righe: list[dict], momento: datetime) -> tuple[str, int]:
    """Le tre sezioni della vista Notifiche, e il numero di card aperte per il
    badge di render_notifiche.panel() (che non le riconta da solo)."""
    aperte = [v for v in righe if v["status"] == "open"]
    risolte_oggi = [v for v in righe if v["status"] != "open"
                    and (momento - v["resolvedAge"]).date() == momento.date()]
    html = (
        _sezione(t("render.notif_attenzione"), [_card_aperta(data, v, momento) for v in aperte],
                 t("render.notif_attenzione_vuota"))
        + _sezione(t("render.notif_in_attesa"), _in_attesa(ref, data), t("render.notif_in_attesa_vuota"))
        + _sezione(t("render.notif_risolte"), [_card_risolta(data, v, momento) for v in risolte_oggi],
                   t("render.notif_risolte_vuota"))
    )
    return html, len(aperte)
