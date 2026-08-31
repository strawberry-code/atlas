"""Retry bounded e stato durevole del run Automata.

Il ledger contiene solo il tentativo del nodo e il prossimo istante utile. Non
salva il processo agente: dopo un riavvio il claim Atlas resta la sola prova che
un agente possa essere ancora vivo.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .adapters import (AgentOutcome, ProviderUnavailableError, coda_diagnostica,
                       provider_indisponibile)
from .store import StateError, scrivi_atomico


FailureKind = Literal[
    "timeout", "crash", "rate-limit", "provider-unavailable",
    "ambiguous-termination", "permanent-error",
]

RETRYABLE_FAILURES = frozenset({
    "timeout", "crash", "rate-limit", "provider-unavailable", "ambiguous-termination",
})


class CrashError(RuntimeError):
    """Il processo agente e' terminato senza un esito affidabile."""


class RateLimitError(RuntimeError):
    """Il provider ha imposto un limite temporaneo alle richieste."""


class AmbiguousTerminationError(RuntimeError):
    """Il runner non puo' stabilire se il lavoro agente sia terminato."""


class PermanentError(RuntimeError):
    """Il lavoro non puo' riuscire con un nuovo tentativo identico."""


def _da_dettaglio(dettaglio: str | None) -> FailureKind:
    # Si guarda la coda dell'output, non il testo intero: prima dell'errore c'e'
    # l'eco del prompt, cioe' la domanda del nodo, e una firma cercata li' dentro
    # classifica il lavoro invece del guasto (vedi adapters.coda_diagnostica).
    testo = coda_diagnostica(dettaglio)
    if provider_indisponibile(dettaglio) and not any(
            parola in testo for parola in ("429", "rate limit", "rate-limit", "too many requests")):
        return "provider-unavailable"
    if any(parola in testo for parola in ("429", "rate limit", "rate-limit", "too many requests")):
        return "rate-limit"
    if "timeout" in testo or "timed out" in testo:
        return "timeout"
    if any(parola in testo for parola in ("provider unavailable", "provider-unavailable", "provider offline")):
        return "provider-unavailable"
    if any(parola in testo for parola in ("ambiguous", "unknown termination", "terminazione ambigua")):
        return "ambiguous-termination"
    if any(parola in testo for parola in (
        "permanent", "invalid", "unsupported", "unauthorized", "forbidden", "not found",
        "authentication", "autenticazione", "permanente",
    )):
        return "permanent-error"
    return "crash"


def classify_failure(value: object) -> FailureKind | None:
    """Classifica un esito o un'eccezione senza eseguire diagnostica ulteriore."""
    if isinstance(value, AgentOutcome) or (
        value.__class__.__name__ == "AgentOutcome"
        and hasattr(value, "status")
        and hasattr(value, "detail")
    ):
        if value.status == "closed":
            return None
        if value.status == "ambiguous":
            return "ambiguous-termination"
        if value.status == "permanent-error":
            return "permanent-error"
        if value.status in ("timeout", "crash", "rate-limit", "provider-unavailable"):
            return value.status
        return _da_dettaglio(value.detail)
    if isinstance(value, TimeoutError):
        return "timeout"
    if isinstance(value, ProviderUnavailableError):
        return "provider-unavailable"
    if isinstance(value, RateLimitError):
        return "rate-limit"
    if isinstance(value, AmbiguousTerminationError):
        return "ambiguous-termination"
    if isinstance(value, PermanentError):
        return "permanent-error"
    if isinstance(value, CrashError):
        return "crash"
    if isinstance(value, BaseException):
        return _da_dettaglio(str(value))
    return "ambiguous-termination"


@dataclass(frozen=True)
class RetryPolicy:
    """Limite e backoff esponenziale, con cap esplicito a un'ora."""

    max_attempts: int = 8
    initial_delay: float = 60.0
    multiplier: float = 2.0
    max_delay: float = 3600.0
    ambiguous_attempts: int = 2

    def __post_init__(self) -> None:
        if type(self.max_attempts) is not int or self.max_attempts <= 0:
            raise ValueError("max_attempts must be a positive integer")
        if type(self.ambiguous_attempts) is not int or self.ambiguous_attempts <= 0:
            raise ValueError("ambiguous_attempts must be a positive integer")
        if self.initial_delay < 0 or self.multiplier < 1 or self.max_delay < 0:
            raise ValueError("retry delays must be non-negative and multiplier at least one")

    def delay_for(self, failed_attempt: int) -> float:
        if type(failed_attempt) is not int or failed_attempt <= 0:
            raise ValueError("failed_attempt must be a positive integer")
        return min(self.max_delay, self.initial_delay * self.multiplier ** (failed_attempt - 1))

    def can_retry(self, attempt: int, failure: FailureKind | None = None) -> bool:
        """Il budget del tentativo, con un tetto piu' stretto per l'ambiguo.

        Un agente che esce pulito senza chiudere il nodo non e' un guasto passeggero
        come un timeout o un 429: rilanciarlo per l'intero budget brucia la quota del
        provider per riottenere la stessa indecisione, e lascia il run appeso per ore
        su un nodo che nessun tentativo identico chiudera'. Due tentativi bastano a
        coprire il caso davvero transitorio.
        """
        tetto = (min(self.ambiguous_attempts, self.max_attempts)
                 if failure == "ambiguous-termination" else self.max_attempts)
        return attempt < tetto


class RetryStateError(StateError):
    """Ledger assente o non leggibile."""


class RetryState:
    """Ledger JSON atomico per i tentativi non ancora terminali."""

    VERSION = 1

    def __init__(self, path: Path, graph_slug: str):
        self.path = Path(path)
        self.graph_slug = graph_slug
        self._data = self._read()

    def _read(self) -> dict:
        if not self.path.is_file():
            return {"version": self.VERSION, "graph": self.graph_slug, "nodes": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as errore:
            raise RetryStateError(f"cannot read retry state {self.path}: {errore}") from errore
        if (not isinstance(data, dict) or data.get("version") != self.VERSION
                or data.get("graph") != self.graph_slug or not isinstance(data.get("nodes"), dict)):
            raise RetryStateError(f"invalid retry state {self.path}")
        return data

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        scrivi_atomico(self.path, json.dumps(self._data, ensure_ascii=False, indent=2) + "\n")

    def record(self, node_id: str) -> dict | None:
        value = self._data["nodes"].get(node_id)
        return dict(value) if isinstance(value, Mapping) else None

    def records(self) -> dict[str, dict]:
        return {node_id: dict(record) for node_id, record in self._data["nodes"].items()}

    def begin(self, node_id: str, now: float) -> int:
        previous = self.record(node_id)
        if previous and previous.get("status") == "terminal":
            raise RetryStateError(f"retry for {node_id} is permanently exhausted")
        attempt = int(previous["attempt"]) + 1 if previous else 1
        self._data["nodes"][node_id] = {
            "attempt": attempt,
            "status": "active",
            "started_at": now,
        }
        self._save()
        return attempt

    def record_failure(self, node_id: str, attempt: int, failure: FailureKind,
                       detail: str | None, now: float, delay: float | None) -> None:
        next_at = now + delay if delay is not None else None
        self._data["nodes"][node_id] = {
            "attempt": attempt,
            "status": "pending" if next_at is not None else "terminal",
            "failure": failure,
            "detail": detail,
            "failed_at": now,
            "next_at": next_at,
        }
        self._save()

    def complete(self, node_id: str) -> None:
        self._data["nodes"].pop(node_id, None)
        self._save()

    def active(self, node_id: str) -> bool:
        record = self.record(node_id)
        return bool(record and record.get("status") == "active")

    def pending(self, node_id: str) -> bool:
        record = self.record(node_id)
        return bool(record and record.get("status") == "pending")

    def due(self, node_id: str, now: float) -> bool:
        record = self.record(node_id)
        return not record or record.get("status") != "pending" or float(record["next_at"]) <= now

    def next_at(self) -> float | None:
        dates = [float(record["next_at"]) for record in self._data["nodes"].values()
                 if record.get("status") == "pending" and record.get("next_at") is not None]
        return min(dates) if dates else None

    def terminal(self, node_id: str) -> bool:
        record = self.record(node_id)
        return bool(record and record.get("status") == "terminal")
