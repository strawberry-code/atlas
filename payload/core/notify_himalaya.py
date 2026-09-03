"""Canale Himalaya (email): alert ed escalation via un profilo Himalaya gia'
configurato sulla macchina che esegue Atlas (client CLI, non una libreria di
terze parti: zero dipendenze come il resto del motore). A differenza del
canale locale (C02) il messaggio sopravvive a chi non ha 'atlas serve'
aperto: e' il canale pensato per raggiungere una persona lontana dallo
schermo, non un duplicato del pannello.

Vincoli del ticket: solo invio. Questo modulo non chiama mai un comando che
legga la mailbox (niente 'himalaya envelope ...', 'himalaya message read
...') e non interpreta risposte: none arrivano al chiamante. Account e
destinatario vivono in ATLAS_HIMALAYA_ACCOUNT/ATLAS_HIMALAYA_TO, mai in un
file del progetto: sono locali alla macchina che invia, come il profilo
Himalaya stesso, e finire nel grafo versionato li esporrebbe a chiunque
clona il progetto. Account assente = usa il default gia' configurato in
Himalaya; destinatario assente = guasto permanente, dichiarato nel
messaggio, mai un tentativo di indovinarlo.
"""
from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from email.message import EmailMessage

from .channels import ChannelRegistry
from .retry import PermanentError

IDENTITY = "himalaya"
ENV_ACCOUNT = "ATLAS_HIMALAYA_ACCOUNT"
ENV_TO = "ATLAS_HIMALAYA_TO"

_ETICHETTA_EVENTO = {
    "gate-required": "conferma richiesta",
    "decision-required": "decisione richiesta",
    "run-stopped": "run fermo",
    "run-ended": "run terminato",
    "human-needed": "serve una persona",
}


def _messaggio(interaction: Mapping[str, object], destinatario: str) -> bytes:
    etichetta = _ETICHETTA_EVENTO.get(str(interaction.get("event")), str(interaction.get("event")))
    azioni = ", ".join(azione["label"] for azione in interaction.get("allowedActions", []))
    msg = EmailMessage()
    msg["Subject"] = f"Atlas · {interaction['nodeId']} · {etichetta}"
    msg["To"] = destinatario
    corpo = (
        f"{interaction['summary']}\n\n"
        f"Nodo: {interaction['nodeId']}\n"
        f"Run: {interaction.get('runId')}\n"
        f"Scade: {interaction.get('expiresAt')}\n"
    )
    if azioni:
        corpo += f"Azioni possibili: {azioni}\n"
    corpo += "\nRispondi dalla dashboard di Atlas ('atlas serve'): questa casella non viene letta.\n"
    msg.set_content(corpo)
    return msg.as_bytes()


def _argv(account: str | None) -> list[str]:
    argv = ["himalaya", "message", "send"]
    if account:
        argv += ["-a", account]
    return argv


def _esegui(argv: list[str], messaggio: bytes) -> None:
    try:
        esito = subprocess.run(argv, input=messaggio, capture_output=True, timeout=20)
    except FileNotFoundError as errore:
        # Il binario non e' installato: nessun tentativo futuro lo fara' comparire,
        # e' un guasto permanente come l'utility assente di notify_local.
        raise PermanentError("notify helper not installed: himalaya") from errore
    if esito.returncode != 0:
        dettaglio = esito.stderr.decode("utf-8", "replace").strip() or f"exit {esito.returncode}"
        raise RuntimeError(f"himalaya message send failed: {dettaglio}")


class HimalayaChannel:
    """Consegna un'email via un profilo Himalaya gia' configurato in locale.
    'runner' e' il punto di iniezione dei test, come in notify_local.DesktopChannel."""

    identity = IDENTITY

    def __init__(self, runner=None) -> None:
        self._runner = runner or _esegui

    def deliver(self, interaction: Mapping[str, object]) -> None:
        destinatario = os.environ.get(ENV_TO)
        if not destinatario:
            raise PermanentError(
                f"{ENV_TO} is not set: cannot address the escalation email")
        argv = _argv(os.environ.get(ENV_ACCOUNT))
        self._runner(argv, _messaggio(interaction, destinatario))


def registry(channel: HimalayaChannel | None = None) -> ChannelRegistry:
    return ChannelRegistry((channel or HimalayaChannel(),))
