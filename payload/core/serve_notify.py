"""Avviso di sistema ed email quando la dashboard servita vede una nuova
Interazione aperta (C02/C03): la stessa ronda che spinge il reload al browser
(serve._watch) prova anche i canali del coordinatore (C01) che non chiedono
setup nel progetto. 'notify.plan' con NotifyState come unica memoria e' cio'
che impedisce di riproporre una consegna gia' arrivata o esaurita a ogni giro
della ronda: e' lo stesso presidio che tiene fuori il rumore ripetuto del
reload SSE (vedi render_notifiche per il pannello, notify.py per il ledger).

Un guasto qui (grafo momentaneamente illeggibile, notify-state corrotto) resta
un canale in piu' che manca, non un motivo per fermare il server: la
dashboard continua a funzionare col solo pannello.
"""
from __future__ import annotations

import json
import os
import time

from . import capability, notify, notify_himalaya, notify_local, notify_telegram, relay_client
from .channels import ChannelRegistry
from .config import Graph, leggi_json
from .retry import RetryPolicy
from .store import StateError, read_transaction

_POLICY = RetryPolicy()

PERCORSO_TOGGLE = "/notify/telegram/toggle"


def telegram_abilitato(ref: Graph) -> bool:
    """La levetta per progetto di SS7-ter/1 (ribalta la decisione 30): accesa
    finche' nessuno la spegne. Letta dal config gia' unito ai default, cosi'
    un config.json senza la chiave 'notify' resta acceso."""
    return bool(ref.workspace.config.get("notify", {}).get("telegram_enabled", True))


def alterna_telegram(ref: Graph) -> tuple[int, dict]:
    """POST /notify/telegram/toggle: capovolge la levetta e la scrive nel
    config.json del progetto, mai a mano (SS7-ter/1), preservando ogni altra
    chiave. Nessun cambio a graph.json: il pannello si aggiorna da JS con la
    risposta, senza aspettare un reload SSE che qui non arriverebbe mai."""
    path = ref.workspace.root / "config.json"
    dati = leggi_json(path) if path.is_file() else {}
    nuovo = not telegram_abilitato(ref)
    notifica = dict(dati.get("notify", {}))
    notifica["telegram_enabled"] = nuovo
    dati["notify"] = notifica
    path.write_text(json.dumps(dati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 200, {"ok": True, "enabled": nuovo}


def _canali_attivi(ref: Graph) -> tuple[str, ...]:
    """'local' e' sempre attivo (C02, nessuna configurazione richiesta);
    'himalaya' solo se un destinatario e' configurato sulla macchina
    (ATLAS_HIMALAYA_TO); 'telegram' solo se il relay (D03) e la capability
    (D01) sono entrambi configurati, e la levetta di questo progetto e'
    accesa (SS7-ter/1). Senza, pianificarlo produrrebbe solo un guasto
    permanente e silenzioso a ogni Interaction (avvisa() scarta l'esito di
    dispatch(), nessuno leggerebbe mai quel 'failed')."""
    canali = [notify_local.IDENTITY]
    if os.environ.get(notify_himalaya.ENV_TO):
        canali.append(notify_himalaya.IDENTITY)
    if (relay_client.configurazione(os.environ) is not None
            and capability.da_ambiente(os.environ) is not None and telegram_abilitato(ref)):
        canali.append(notify_telegram.IDENTITY)
    return tuple(canali)


def _registro_predefinito(data: dict) -> ChannelRegistry:
    """'data' e' l'istantanea del grafo appena letta da 'avvisa': solo il
    canale Telegram la usa, per nominare il progetto col suo titolo umano
    invece che con lo slug (SS7-bis/14)."""
    return ChannelRegistry((notify_local.DesktopChannel(), notify_himalaya.HimalayaChannel(),
                            notify_telegram.TelegramChannel(graph=data)))


def avvisa(ref: Graph, registro: ChannelRegistry | None = None) -> None:
    """'registro' e' il punto di iniezione dei test: di default sono i canali
    veri (notify_local, notify_himalaya, notify_telegram), cosi' il chiamante
    di produzione non deve mai passarlo esplicitamente."""
    try:
        with read_transaction(ref.json_path) as data:
            stato = notify.NotifyState(ref.notify_state_path, ref.slug)
            dovute = notify.plan(data, stato, _canali_attivi(ref), time.time())
            if dovute:
                notify.dispatch(data, dovute, registro or _registro_predefinito(data),
                                stato, _POLICY, time.time())
    except StateError:
        pass
