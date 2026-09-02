"""Pairing Telegram one-tap dal pannello Notifiche (D05): il client chiede al
relay un codice monouso e il link t.me da aprire. L'utente non inserisce mai
token bot, chat ID, hostname o file di configurazione: tutto cio' che serve
(base URL e bearer del relay) e' gia' l'ambiente dichiarato per il tunnel
(D03, relay_client.da_ambiente) - 'atlas serve' lo rilegge a ogni richiesta,
niente di nuovo da configurare nel progetto.

Spezzato da serve.py per la stessa ragione di serve_actions.py: qui c'e' solo
il pairing, la' resta il resto del server. Il bearer del relay non lascia mai
questo processo: il browser parla solo con 'atlas serve' su 127.0.0.1, mai
direttamente col relay.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from urllib.parse import quote

from . import relay_client
from .config import Graph

PERCORSO_AVVIA = "/pairing/telegram"
PERCORSO_STATO = "/pairing/telegram/status"


def _ambiente(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return env if env is not None else os.environ


def avvia(ref: Graph, env: Mapping[str, str] | None = None,
          opener=urllib.request.urlopen) -> tuple[int, dict]:
    """POST /pairing/telegram: chiede al relay un codice monouso per questo
    progetto. 503 se il relay non e' configurato in questo ambiente (stesso
    gate del tunnel D03), 502 se il relay non risponde o rifiuta la richiesta
    (non ancora deployato, pairing disattivato, bearer scaduto...)."""
    config = relay_client.da_ambiente(_ambiente(env))
    if config is None:
        return 503, {"ok": False}
    richiesta = urllib.request.Request(
        f"{config.base_url.rstrip('/')}/pairing",
        data=json.dumps({"graph": ref.slug}).encode("utf-8"),
        headers={"Authorization": f"Bearer {config.token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(richiesta, timeout=10) as risposta:
            if risposta.status != 200:
                return 502, {"ok": False}
            corpo = json.loads(risposta.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return 502, {"ok": False}
    return 200, {"ok": True, "url": corpo.get("url"), "code": corpo.get("code"),
                 "expiresAt": corpo.get("expiresAt")}


def stato(codice: str, env: Mapping[str, str] | None = None,
          opener=urllib.request.urlopen) -> tuple[int, dict]:
    """GET /pairing/telegram/status?code=...: il pannello lo interroga a
    intervalli finche' l'utente non conferma su Telegram o il codice non
    scade. Il bearer resta lato server: il browser non lo vede mai."""
    config = relay_client.da_ambiente(_ambiente(env))
    if config is None:
        return 503, {"ok": False}
    if not codice:
        return 400, {"ok": False}
    richiesta = urllib.request.Request(
        f"{config.base_url.rstrip('/')}/pairing?code={quote(codice)}",
        headers={"Authorization": f"Bearer {config.token}"},
    )
    try:
        with opener(richiesta, timeout=10) as risposta:
            if risposta.status != 200:
                return 502, {"ok": False}
            corpo = json.loads(risposta.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return 502, {"ok": False}
    return 200, {"ok": True, "status": corpo.get("status")}
