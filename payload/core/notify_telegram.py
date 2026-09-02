"""Canale Telegram in uscita (D07): il deliver iniziale di un'Interazione
aperta come messaggio con un bottone per azione ammessa, l'ultimo miglio che
D01 aveva progettato e D06 sa gia' risolvere ma che nessun canale emetteva
ancora (gap segnalato in fog da D06: 'capability.emetti esiste ma nessuno lo
chiama fuori dai test').

Passa dal coordinatore notifiche (C01) come ogni altro canale: 'deliver' e'
l'unico confine, niente di specifico per Telegram trapela in notify.py. Usa
il tunnel D03 (relay_client.TunnelConfig/da_ambiente, relay_client.
invia_messaggio) per il trasporto e la capability D01 (capability.emetti) per
autorizzare ogni bottone: un jti fresco e monouso per azione, la stessa firma
HMAC che D06 verifica al tap. Il relay risolve il chat_id dal graph (D07,
l'inverso di pairing.progetto_di): il client non conosce mai un chat_id, solo
il progetto a cui appartiene.

A differenza di relay_client.aggiorna_messaggio (best-effort, D06: la
transazione Atlas e' gia' commessa quando parte), qui il fallimento deve
risalire a notify.dispatch: un progetto non ancora appaiato o un relay non
deployato (A01) sono guasti di questo canale, non del grafo, ma vanno
registrati nel ledger di consegna (NotifyState) per non riprovare
all'infinito ne' fingere una consegna che non c'e' stata.
"""
from __future__ import annotations

import os
from collections.abc import Mapping

from . import capability, relay_client
from .channels import ChannelRegistry
from .retry import PermanentError

IDENTITY = "telegram"

_ETICHETTA_EVENTO = {
    "gate-required": "conferma richiesta",
    "decision-required": "decisione richiesta",
    "run-stopped": "run fermo",
    "run-ended": "run terminato",
}


def _testo(interaction: Mapping[str, object]) -> str:
    etichetta = _ETICHETTA_EVENTO.get(str(interaction.get("event")), str(interaction.get("event")))
    return f"Atlas · {interaction['nodeId']} · {etichetta}\n\n{interaction['summary']}"


def _bottoni(interaction: Mapping[str, object], chiave: str) -> list[tuple[str, str]]:
    return [
        (azione["label"], capability.emetti(
            chiave, graph=str(interaction["graph"]), run_id=str(interaction["runId"]),
            interaction_id=str(interaction["id"]), action_id=azione["id"],
            exp=str(interaction["expiresAt"])))
        for azione in interaction.get("allowedActions", [])
    ]


class TelegramChannel:
    """'env' e 'sender' sono i punti di iniezione dei test, come 'runner'
    negli altri canali: di default legge l'ambiente vero e invia davvero via
    relay_client.invia_messaggio."""

    identity = IDENTITY

    def __init__(self, env: Mapping[str, str] | None = None, sender=None) -> None:
        self._env = env if env is not None else os.environ
        self._sender = sender or relay_client.invia_messaggio

    def deliver(self, interaction: Mapping[str, object]) -> None:
        config = relay_client.da_ambiente(self._env)
        chiave = capability.da_ambiente(self._env)
        if config is None or chiave is None:
            raise PermanentError(
                "Telegram relay is not configured on this machine: cannot deliver")
        self._sender(config, str(interaction["graph"]), _testo(interaction),
                     _bottoni(interaction, chiave))


def registry(channel: TelegramChannel | None = None) -> ChannelRegistry:
    return ChannelRegistry((channel or TelegramChannel(),))
