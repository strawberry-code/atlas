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
HMAC che D06 verifica al tap. Il relay instrada per installazione (A05, SS4-bis),
non per progetto: 'deliver' apre la linea con l'identita' di questa macchina
(relay_identity.carica_o_crea, A01), la stessa che apre il tunnel in autopilot.py.

Il messaggio nomina il progetto col titolo umano scritto da chi ha creato il
grafo, mai con lo slug (SS7-bis/14 di docs/atlas-relay-design.md): il relay non
lo conserva, viaggia solo dentro il testo di passaggio. Porta il minimo che
serve a decidere, titolo del nodo e azioni ammesse, mai il ticket ne' un path
(SS5), nella lingua del progetto (grilling 34, stessa scelta di autopilot._card).
'graph' e' l'istantanea del grafo.json passata da serve_notify.py: qui non si
riapre una transazione propria.

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

from . import capability, relay_client, relay_identity
from .channels import ChannelRegistry
from .retry import PermanentError
from .strings import t

IDENTITY = "telegram"

_CHIAVE_EVENTO = {
    "gate-required": "notify_telegram.evento_gate_required",
    "decision-required": "notify_telegram.evento_decision_required",
    "run-stopped": "notify_telegram.evento_run_stopped",
    "run-ended": "notify_telegram.evento_run_ended",
    "human-needed": "notify_telegram.evento_human_needed",
}


def _etichetta(evento: str) -> str:
    chiave = _CHIAVE_EVENTO.get(evento)
    return t(chiave) if chiave else evento


def _titolo_nodo(graph: Mapping[str, object], node_id: str) -> str:
    for node in graph.get("nodes", []):
        if node["id"] == node_id:
            return str(node["title"])
    return node_id  # difensivo: un'Interaction valida punta sempre a un nodo del suo grafo


def _testo(interaction: Mapping[str, object], graph: Mapping[str, object]) -> str:
    """'graph' porta 'meta.title', mai lo slug (SS7-bis/14): se manca e' un
    grafo malformato, e si vede come guasto di consegna invece che regredire
    in silenzio a un identificativo che la decisione vieta di mostrare."""
    etichetta = _etichetta(str(interaction["event"]))
    titolo_progetto = str(graph["meta"]["title"])
    titolo_nodo = _titolo_nodo(graph, str(interaction["nodeId"]))
    return f"{titolo_progetto} · {titolo_nodo} · {etichetta}\n\n{interaction['summary']}"


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
    relay_client.invia_messaggio. 'graph' e' l'istantanea del grafo.json che
    serve_notify.py passa per costruire il testo (titolo del progetto e del
    nodo): senza iniezione e' vuoto, coerente con un canale mai usato fuori
    da 'avvisa'."""

    identity = IDENTITY

    def __init__(self, env: Mapping[str, str] | None = None, sender=None,
                graph: Mapping[str, object] | None = None) -> None:
        self._env = env if env is not None else os.environ
        self._sender = sender or relay_client.invia_messaggio
        self._graph = graph if graph is not None else {}

    def deliver(self, interaction: Mapping[str, object]) -> None:
        config = relay_client.da_ambiente(self._env)
        chiave = capability.da_ambiente(self._env)
        if config is None or chiave is None:
            raise PermanentError(
                "Telegram relay is not configured on this machine: cannot deliver")
        installazione = relay_identity.carica_o_crea(env=self._env)
        self._sender(config, installazione.installation_id, _testo(interaction, self._graph),
                     _bottoni(interaction, chiave))


def registry(channel: TelegramChannel | None = None) -> ChannelRegistry:
    return ChannelRegistry((channel or TelegramChannel(),))
