"""Trasforma Interazioni aperte in consegne verso i canali registrati.

interactions.py decide gia' quali eventi meritano una card (A02, A05): una
Interaction esiste solo perche' serve una decisione, un run si e' fermato o e'
arrivato END. Qui non si riapre quella scelta: si limita a farla arrivare, una
volta per canale, con un budget di tentativi che non lascia un canale rotto
rilanciare all'infinito.

Il silenzio e' nell'esito, non nel codice: una consegna ancora in backoff
('pending') non merita attenzione, e' un successo intermedio del retry. Una
consegna riuscita o esaurita ('delivered'/'failed') e' invece il solo momento
in cui la persona e' stata raggiunta o rischia di non esserlo mai: DeliveryOutcome
lo dichiara esplicitamente con 'escalate', cosi' chi chiama non deve rileggere
lo stato per saperlo.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .channels import ChannelRegistry
from .retry import RETRYABLE_FAILURES, FailureKind, RetryPolicy, classify_failure
from .store import StateError, scrivi_atomico

DeliveryStatus = Literal["delivered", "pending", "failed"]


@dataclass(frozen=True)
class Delivery:
    """Una consegna dovuta adesso: un'interazione verso un canale, al tentativo N."""

    interaction_id: str
    channel: str
    attempt: int


@dataclass(frozen=True)
class DeliveryOutcome:
    """Esito registrato di una consegna gia' tentata."""

    interaction_id: str
    channel: str
    status: DeliveryStatus
    escalate: bool
    detail: str | None = None


class NotifyStateError(StateError):
    """Ledger delle consegne assente, illeggibile o incompatibile."""


def _key(interaction_id: str, channel: str) -> str:
    return f"{interaction_id}::{channel}"


class NotifyState:
    """Ledger JSON atomico degli esiti di consegna, per interazione e canale.

    A differenza del retry-state di Autopilot, qui il successo va ricordato per
    sempre: e' la sola memoria che impedisce, dopo un riavvio, di consegnare di
    nuovo una card gia' arrivata sullo stesso canale.
    """

    VERSION = 1

    def __init__(self, path: Path, graph_slug: str):
        self.path = Path(path)
        self.graph_slug = graph_slug
        self._data = self._read()

    def _read(self) -> dict:
        if not self.path.is_file():
            return {"version": self.VERSION, "graph": self.graph_slug, "deliveries": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as errore:
            raise NotifyStateError(f"cannot read notify state {self.path}: {errore}") from errore
        if (not isinstance(data, dict) or data.get("version") != self.VERSION
                or data.get("graph") != self.graph_slug or not isinstance(data.get("deliveries"), dict)):
            raise NotifyStateError(f"invalid notify state {self.path}")
        return data

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        scrivi_atomico(self.path, json.dumps(self._data, ensure_ascii=False, indent=2) + "\n")

    def record(self, key: str) -> dict | None:
        value = self._data["deliveries"].get(key)
        return dict(value) if isinstance(value, dict) else None

    def attempt_number(self, key: str) -> int:
        record = self.record(key)
        return int(record["attempt"]) + 1 if record else 1

    def due(self, key: str, now: float) -> bool:
        """Vero per una consegna mai tentata, o il cui backoff e' scaduto."""
        record = self.record(key)
        if record is None:
            return True
        if record["status"] != "pending":
            return False
        return float(record["next_at"]) <= now

    def succeed(self, key: str, attempt: int, now: float) -> None:
        self._data["deliveries"][key] = {"status": "delivered", "attempt": attempt, "at": now}
        self._save()

    def fail(self, key: str, attempt: int, failure: FailureKind, detail: str | None,
             now: float, delay: float | None) -> None:
        next_at = now + delay if delay is not None else None
        self._data["deliveries"][key] = {
            "status": "pending" if next_at is not None else "failed",
            "attempt": attempt, "failure": failure, "detail": detail,
            "at": now, "next_at": next_at,
        }
        self._save()

    def failed_channels(self, interaction_id: str) -> list[str]:
        """I canali su cui la consegna di questa Interaction si e' esaurita
        senza riuscire ('failed'): la sola lettura che serve alla dashboard
        per dire che il silenzio ha una causa (SS7-ter/3), senza aprire un
        nuovo giro di retry oltre a quello che dispatch() ha gia' concluso."""
        prefisso = f"{interaction_id}::"
        return sorted(
            chiave[len(prefisso):] for chiave, record in self._data["deliveries"].items()
            if chiave.startswith(prefisso) and record.get("status") == "failed"
        )


def plan(data: dict, state: NotifyState, channels: Iterable[str], now: float) -> list[Delivery]:
    """Le consegne dovute adesso per ogni Interaction ancora aperta.

    Una volta risolta, annullata o scaduta l'Interazione ha gia' raggiunto il
    suo esito per un'altra via (risposta diretta, scadenza): consegnarla ancora
    sarebbe rumore su una decisione che non serve piu' prendere.
    """
    dovute = []
    for record in data.get("interactions", []):
        if record["status"] != "open":
            continue
        for channel in channels:
            key = _key(record["id"], channel)
            if state.due(key, now):
                dovute.append(Delivery(record["id"], channel, state.attempt_number(key)))
    return dovute


def dispatch(data: dict, deliveries: Iterable[Delivery], registry: ChannelRegistry,
            state: NotifyState, policy: RetryPolicy, now: float) -> list[DeliveryOutcome]:
    """Esegue ogni consegna dovuta e ne registra l'esito, con dedup e retry bounded.

    'escalate' e' vero solo quando la consegna e' arrivata o si e' esaurita:
    un tentativo ancora in backoff resta silenzioso, e' il successo intermedio
    del retry di cui parla il contratto, non un esito da mostrare a nessuno.
    """
    by_id = {record["id"]: record for record in data.get("interactions", [])}
    esiti = []
    for consegna in deliveries:
        record = by_id.get(consegna.interaction_id)
        if record is None:
            continue
        key = _key(consegna.interaction_id, consegna.channel)
        channel = registry.get(consegna.channel)
        try:
            channel.deliver(record)
        except Exception as errore:
            guasto = classify_failure(errore)
            ritentabile = guasto in RETRYABLE_FAILURES and policy.can_retry(consegna.attempt, guasto)
            ritardo = policy.delay_for(consegna.attempt) if ritentabile else None
            state.fail(key, consegna.attempt, guasto, str(errore), now, ritardo)
            esiti.append(DeliveryOutcome(
                consegna.interaction_id, consegna.channel,
                "pending" if ritardo is not None else "failed",
                escalate=ritardo is None, detail=str(errore)))
            continue
        state.succeed(key, consegna.attempt, now)
        esiti.append(DeliveryOutcome(consegna.interaction_id, consegna.channel,
                                     "delivered", escalate=True, detail=None))
    return esiti
