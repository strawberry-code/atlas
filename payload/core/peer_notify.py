"""Avviso peer 'qualcosa e' cambiato' (E01, docs/atlas-relay-design.md
SS11-bis): l'unico compito e' dire al relay 'ho chiuso un pezzo di questo
progetto', mai cosa. POST /peers/notify con il solo codice opaco del
progetto (project_code.py) e l'installation_id di chi avvisa: il relay
risolve da se' chi altro condivide quel codice e li avvisa, senza che questo
modulo sappia chi sono ne' debba saperlo.

Chiamato da 'atlas close' (cli.py), sempre best-effort come
relay_client.aggiorna_messaggio: un relay non configurato, non raggiungibile
o senza pairing non deve mai far fallire una chiusura di nodo, che resta
un'operazione locale e offline per costruzione.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping

from . import project_code, relay_client, relay_identity
from .config import Workspace

TIMEOUT_SECONDI = 5.0   # breve: non deve far percepire lenta una chiusura di nodo


def avvisa(ws: Workspace, env: Mapping[str, str] | None = None,
          opener=urllib.request.urlopen) -> None:
    """Nessun ritorno da controllare: il fallimento e' un fatto del canale
    Telegram (relay non deployato, progetto non ancora appaiato), non del
    grafo."""
    ambiente = env if env is not None else os.environ
    config = relay_client.da_ambiente(ambiente)
    if config is None:
        return
    codice = project_code.carica_o_crea(ws)
    installazione = relay_identity.carica_o_crea(env=ambiente)
    corpo = json.dumps({"projectCode": codice,
                        "installation": installazione.installation_id}).encode("utf-8")
    richiesta = urllib.request.Request(
        f"{config.base_url.rstrip('/')}/peers/notify",
        data=corpo, method="POST",
        headers={"Authorization": f"Bearer {config.token}", "Content-Type": "application/json"},
    )
    try:
        with opener(richiesta, timeout=TIMEOUT_SECONDI):
            pass
    except (OSError, urllib.error.URLError):
        pass
