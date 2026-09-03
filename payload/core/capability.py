"""Capability token del protocollo D01: opaco, monouso, firmato HMAC, con
scadenza. Lo emette e lo verifica sempre e solo il client Atlas (D06): mai il
relay, che lo trasporta come 'callback_data' senza poterlo interpretare, ne'
possiede la chiave per farlo con profitto.

Forma: base64url(payload_json) + '.' + base64url(HMAC-SHA256(payload_json)),
scritto a mano con hmac/hashlib/base64/json/secrets di stdlib (stile JWS
compact, nessuna libreria JWT). Il payload porta solo cio' che serve a
correlare un tap a un'azione: graph, runId, interactionId, actionId, un jti
fresco (il nonce che rende il monouso verificabile) ed exp.

L'autorita' finale sulla scadenza e sull'unicita' resta il ledger (A04:
resolve_interaction porta l'Interaction fuori da 'open' al primo successo):
questo modulo e' solo il controllo economico che scarta un tap palesemente
invalido prima di sfiorare il grafo, piu' la difesa in profondita' del jti
per una redelivery Telegram o un retry del relay.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from collections.abc import Mapping
from datetime import datetime

ENV_KEY = "ATLAS_CAPABILITY_KEY_REF"

_CAMPI = frozenset(("graph", "runId", "interactionId", "actionId", "jti", "exp"))


class CapabilityRejected(ValueError):
    """Token malformato, firma non valida, scaduto o gia' consumato."""


def _b64(dato: bytes) -> str:
    return base64.urlsafe_b64encode(dato).rstrip(b"=").decode("ascii")


def _unb64(testo: str) -> bytes:
    return base64.urlsafe_b64decode(testo + "=" * (-len(testo) % 4))


def _firma(chiave: str, corpo: bytes) -> bytes:
    return hmac.new(chiave.encode("utf-8"), corpo, hashlib.sha256).digest()


def emetti(chiave: str, *, graph: str, run_id: str, interaction_id: str,
           action_id: str, exp: str) -> str:
    """Un token per una sola azione di una sola Interaction. 'exp' e' un
    timestamp ISO-8601 gia' vincolato da chi chiama a restare <= la scadenza
    dell'Interaction (D01): qui si firma soltanto, non si impone quel
    vincolo, che non e' osservabile da questo modulo."""
    payload = {
        "graph": graph, "runId": run_id, "interactionId": interaction_id,
        "actionId": action_id, "jti": secrets.token_urlsafe(16), "exp": exp,
    }
    corpo = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return f"{_b64(corpo)}.{_b64(_firma(chiave, corpo))}"


class ConsumatiJti:
    """jti gia' visti, tenuti solo finche' la loro scadenza non e' passata.

    Potabile per costruzione (un jti scaduto non serve piu' a nessuno): senza
    questo limite un processo Autopilot long-running accumulerebbe un jti per
    ogni tap per sempre.
    """

    def __init__(self) -> None:
        self._scadenza: dict[str, float] = {}

    def consuma(self, jti: str, exp_epoch: float, now_epoch: float) -> bool:
        """Vero la prima volta che si vede questo jti (e lo marca come
        consumato); falso se era gia' stato visto e non ancora potato."""
        scaduti = [chiave for chiave, exp in self._scadenza.items() if exp < now_epoch]
        for chiave in scaduti:
            del self._scadenza[chiave]
        if jti in self._scadenza:
            return False
        self._scadenza[jti] = exp_epoch
        return True


def verifica(chiave: str, token: str, *, consumati: ConsumatiJti,
             now: datetime | None = None) -> Mapping[str, str]:
    """Solleva CapabilityRejected per formato/firma non validi, scadenza
    passata o jti gia' consumato; altrimenti torna il payload verificato."""
    try:
        parte_corpo, parte_firma = token.split(".", 1)
        corpo = _unb64(parte_corpo)
        firma = _unb64(parte_firma)
    except (ValueError, TypeError) as errore:
        raise CapabilityRejected("token malformato") from errore
    if not hmac.compare_digest(firma, _firma(chiave, corpo)):
        raise CapabilityRejected("firma non valida")
    try:
        payload = json.loads(corpo)
    except (json.JSONDecodeError, UnicodeDecodeError) as errore:
        raise CapabilityRejected("payload non decodificabile") from errore
    if not isinstance(payload, dict) or set(payload) != _CAMPI:
        raise CapabilityRejected("payload non valido")
    try:
        scadenza = datetime.fromisoformat(payload["exp"])
    except (TypeError, ValueError) as errore:
        raise CapabilityRejected("scadenza non valida") from errore
    istante = now or datetime.now().astimezone()
    if scadenza < istante:
        raise CapabilityRejected("capability scaduta")
    if not consumati.consuma(payload["jti"], scadenza.timestamp(), istante.timestamp()):
        raise CapabilityRejected("capability gia' consumata")
    return payload


def da_ambiente(env: Mapping[str, str]) -> str | None:
    """None se ATLAS_CAPABILITY_KEY_REF non e' nell'ambiente: stesso gate di
    D01/D03, senza inventare una chiave di comodo."""
    return env.get(ENV_KEY) or None
