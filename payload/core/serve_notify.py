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

import os
import time

from . import notify, notify_himalaya, notify_local
from .channels import ChannelRegistry
from .config import Graph
from .retry import RetryPolicy
from .store import StateError, read_transaction

_POLICY = RetryPolicy()


def _canali_attivi() -> tuple[str, ...]:
    """'local' e' sempre attivo (C02, nessuna configurazione richiesta);
    'himalaya' solo se un destinatario e' configurato sulla macchina
    (ATLAS_HIMALAYA_TO): senza, pianificarlo produrrebbe solo un guasto
    permanente e silenzioso a ogni Interaction (avvisa() scarta l'esito di
    dispatch(), nessuno leggerebbe mai quel 'failed')."""
    canali = [notify_local.IDENTITY]
    if os.environ.get(notify_himalaya.ENV_TO):
        canali.append(notify_himalaya.IDENTITY)
    return tuple(canali)


def _registro_predefinito() -> ChannelRegistry:
    return ChannelRegistry((notify_local.DesktopChannel(), notify_himalaya.HimalayaChannel()))


def avvisa(ref: Graph, registro: ChannelRegistry | None = None) -> None:
    """'registro' e' il punto di iniezione dei test: di default sono i canali
    veri (notify_local, notify_himalaya), cosi' il chiamante di produzione non
    deve mai passarlo esplicitamente."""
    try:
        with read_transaction(ref.json_path) as data:
            stato = notify.NotifyState(ref.notify_state_path, ref.slug)
            dovute = notify.plan(data, stato, _canali_attivi(), time.time())
            if dovute:
                notify.dispatch(data, dovute, registro or _registro_predefinito(),
                                stato, _POLICY, time.time())
    except StateError:
        pass
