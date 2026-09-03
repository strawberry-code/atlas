"""Pairing Telegram one-tap dal pannello Notifiche (D05): il client chiede al
relay un codice monouso e il link t.me da aprire. L'utente non inserisce mai
token bot, chat ID, hostname o file di configurazione: tutto cio' che serve
(base URL e bearer del relay) e' gia' l'ambiente dichiarato per il tunnel
(D03, relay_client.da_ambiente) - 'atlas serve' lo rilegge a ogni richiesta,
niente di nuovo da configurare nel progetto.

Il gesto e' per macchina, non per progetto (A04, grilling 9): il codice
monouso appaia l'installazione di questa macchina alla chat, non il grafo
aperto in questo momento nella dashboard. L'identita' che viaggia nel corpo
della richiesta e' quella di relay_identity (A01), la stessa per tutti i
progetti presenti e futuri di questa macchina.

Spezzato da serve.py per la stessa ragione di serve_actions.py: qui c'e' solo
il pairing, la' resta il resto del server. Il bearer del relay non lascia mai
questo processo: il browser parla solo con 'atlas serve' su 127.0.0.1, mai
direttamente col relay.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from urllib.parse import quote

from . import relay_client, relay_identity

PERCORSO_AVVIA = "/pairing/telegram"
PERCORSO_STATO = "/pairing/telegram/status"


def _ambiente(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return env if env is not None else os.environ


def avvia(env: Mapping[str, str] | None = None,
          opener=urllib.request.urlopen) -> tuple[int, dict]:
    """POST /pairing/telegram: chiede al relay un codice monouso per questa
    installazione. 503 se il relay non e' configurato in questo ambiente
    (stesso gate del tunnel D03), 502 se il relay non risponde o rifiuta la
    richiesta (non ancora deployato, pairing disattivato, bearer scaduto...)."""
    ambiente = _ambiente(env)
    config = relay_client.configurazione(ambiente)
    if config is None:
        # 'motivo' e' un valore codificato, non prosa: il pannello ci sceglie il
        # testo da mostrare. Senza, il browser vedeva un errore solo e diceva
        # 'riprova' anche a chi non ha un relay configurato, cioe' a chi
        # riprovando fallira' per sempre.
        return 503, {"ok": False, "motivo": "relay-non-configurato"}
    installazione = relay_identity.carica_o_crea(env=ambiente)
    richiesta = urllib.request.Request(
        f"{config.base_url.rstrip('/')}/pairing",
        data=json.dumps({"installation": installazione.installation_id}).encode("utf-8"),
        headers={"Authorization": f"Bearer {config.token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(richiesta, timeout=10) as risposta:
            if risposta.status != 200:
                return 502, {"ok": False, "motivo": "relay-non-risponde"}
            corpo = json.loads(risposta.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return 502, {"ok": False, "motivo": "relay-non-risponde"}
    return 200, {"ok": True, "url": corpo.get("url"), "code": corpo.get("code"),
                 "expiresAt": corpo.get("expiresAt")}


def collegato(env: Mapping[str, str] | None = None,
              opener=urllib.request.urlopen) -> bool:
    """Questa installazione risulta gia' collegata a una chat Telegram?

    Il pannello lo chiede a ogni apertura: senza, mostrava il bottone 'collega
    Telegram' anche a chi si era gia' collegato, e l'unico modo di sapere com'era
    andata era leggere lo stato sul server. Un relay non configurato o che non
    risponde vale come 'non collegato': e' l'unica risposta onesta quando non si
    puo' chiedere, e non fa sparire il bottone a chi ne ha bisogno."""
    ambiente = _ambiente(env)
    config = relay_client.configurazione(ambiente)
    if config is None:
        return False
    installazione = relay_identity.carica_o_crea(env=ambiente)
    url = (f"{config.base_url.rstrip('/')}/pairing"
           f"?installation={urllib.parse.quote(installazione.installation_id)}")
    richiesta = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {config.token}"}, method="GET")
    try:
        with opener(richiesta, timeout=5) as risposta:
            if risposta.status != 200:
                return False
            return bool(json.loads(risposta.read().decode("utf-8")).get("paired"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


def stato(codice: str, env: Mapping[str, str] | None = None,
          opener=urllib.request.urlopen) -> tuple[int, dict]:
    """GET /pairing/telegram/status?code=...: il pannello lo interroga a
    intervalli finche' l'utente non conferma su Telegram o il codice non
    scade. Il bearer resta lato server: il browser non lo vede mai."""
    config = relay_client.configurazione(_ambiente(env))
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
                return 502, {"ok": False, "motivo": "relay-non-risponde"}
            corpo = json.loads(risposta.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return 502, {"ok": False, "motivo": "relay-non-risponde"}
    return 200, {"ok": True, "status": corpo.get("status")}
