"""Ledger atomico delle Interazioni, conservato nel graph.json canonico."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from threading import Condition

from .identity import identity
from .store import StateError


STATUSES = frozenset(("open", "resolved", "cancelled", "expired"))
ACTION_IDS = frozenset(("confirm", "decline", "retry", "cancel", "acknowledge"))
_REQUIRED = frozenset((
    "id", "graph", "runId", "nodeId", "event", "summary", "allowedActions",
    "expiresAt", "idempotencyKey", "status", "createdAt", "updatedAt", "resolution", "events",
))


@dataclass(frozen=True)
class ResolutionEvent:
    """Una risposta gia' scritta nel ledger, non un comando per il runner."""

    graph: str
    run_id: str
    interaction_id: str


_events: dict[tuple[str, str], deque[ResolutionEvent]] = defaultdict(deque)
_events_ready = Condition()


def publish(event: object) -> None:
    """Risveglia chi attende una risposta gia' diventata canonica in Atlas."""
    if not isinstance(event, ResolutionEvent):
        return
    with _events_ready:
        _events[event.graph, event.run_id].append(event)
        _events_ready.notify_all()


def wait_for_resolution(graph: str, run_id: str,
                        timeout: float | None = None) -> ResolutionEvent | None:
    """Attende un evento Atlas, con una scadenza opzionale.

    La coda vive in memoria di processo e la riempie publish, che gira dentro la
    transazione di chi risponde: una risposta scritta nel grafo da un altro
    processo non la vede nessuno qui. Senza scadenza un run AFK che si ferma
    resterebbe appeso per sempre, quindi chi attende dichiara ogni quanto vuole
    tornare a guardare il grafo, e a tempo scaduto riceve None invece di un evento.
    """
    key = (graph, run_id)
    limite = None if timeout is None else time.monotonic() + timeout
    with _events_ready:
        while not _events[key]:
            if limite is None:
                _events_ready.wait()
                continue
            residuo = limite - time.monotonic()
            if residuo <= 0:
                return None
            _events_ready.wait(residuo)
        return _events[key].popleft()


def is_expired(record: dict, now: datetime | None = None) -> bool:
    """Vero se la card e' aperta e la sua scadenza dichiarata e' passata."""
    if record.get("status") != "open":
        return False
    return _as_datetime(record["expiresAt"]) < (now or datetime.now().astimezone())


def _invalid(detail: str) -> StateError:
    return StateError(f"invalid interaction ledger: {detail}")


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _timestamp(value: object) -> bool:
    if not _nonempty(value):
        return False
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


def _as_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _next_id(interactions: list[dict]) -> str:
    numbers = [int(record["id"][1:]) for record in interactions
               if isinstance(record.get("id"), str) and record["id"].startswith("I")
               and record["id"][1:].isdigit()]
    return f"I{max(numbers, default=0) + 1:03d}"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _same_request(record: dict, expected: dict) -> bool:
    return all(record.get(key) == value for key, value in expected.items())


def _open_record(g, interaction_id: str) -> dict:
    try:
        record = next(record for record in g.data.get("interactions", [])
                      if record["id"] == interaction_id)
    except StopIteration:
        raise _invalid(f"interaction does not exist: {interaction_id}") from None
    if record["status"] != "open":
        raise _invalid(f"interaction is not open: {interaction_id}")
    return record


def _finish(record: dict, status: str, stamp: str, resolution: dict | None = None) -> dict:
    record.update(status=status, updatedAt=stamp, resolution=resolution)
    record["events"].append({"at": stamp, "type": status, "by": identity()})
    return record


def open_interaction(g, *, run_id: str, node_id: str, event: str, summary: str,
                     allowed_actions: list[dict], expires_at: str,
                     idempotency_key: str) -> dict:
    """Open one Interaction, or return the exact earlier request with its key.

    Call this inside ``mutate.editing``. The graph transaction serializes the
    idempotency check and append, so a relay retry cannot create another record.
    """
    g.node(node_id)
    requested = {
        "graph": g.slug, "runId": run_id, "nodeId": node_id, "event": event,
        "summary": summary, "allowedActions": allowed_actions, "expiresAt": expires_at,
        "idempotencyKey": idempotency_key,
    }
    interactions = g.data.setdefault("interactions", [])
    matching = next((record for record in interactions
                     if record.get("idempotencyKey") == idempotency_key), None)
    if matching is not None:
        if _same_request(matching, requested):
            return matching
        raise _invalid("idempotency key is already bound to a different request")

    stamp = _now()
    record = {
        "id": _next_id(interactions), **requested, "status": "open",
        "createdAt": stamp, "updatedAt": stamp, "resolution": None,
        "events": [{"at": stamp, "type": "opened", "by": identity()}],
    }
    interactions.append(record)
    return record


def resolve_interaction(g, interaction_id: str, action_id: str) -> dict:
    """Apply exactly one declared action without changing the graph itself."""
    record = _open_record(g, interaction_id)
    try:
        action = next(action for action in record["allowedActions"] if action["id"] == action_id)
    except StopIteration:
        raise _invalid(f"action is not allowed for interaction: {interaction_id}") from None
    stamp = _now()
    resolved = _finish(record, "resolved", stamp,
                       {"action": action["id"], "effect": action["effect"]})
    g.after_commit(ResolutionEvent(g.slug, resolved["runId"], resolved["id"]))
    return resolved


def cancel_interaction(g, interaction_id: str) -> dict:
    """Cancel an open Interaction without accepting a free-form instruction."""
    return _finish(_open_record(g, interaction_id), "cancelled", _now())


def expire_interactions(g) -> list[dict]:
    """Expire every still-open Interaction whose declared deadline has passed."""
    stamp = _now()
    current = _as_datetime(stamp)
    expired = []
    for record in g.data.get("interactions", []):
        if record["status"] == "open" and _as_datetime(record["expiresAt"]) < current:
            expired.append(_finish(record, "expired", stamp))
    return expired


def validate_interactions(data: dict) -> None:
    """Validate the canonical ledger before graph.json is atomically replaced."""
    records = data.get("interactions", [])
    if not isinstance(records, list):
        raise _invalid("interactions is not a list")
    node_ids = {node["id"] for node in data["nodes"]}
    ids: set[str] = set()
    keys: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != _REQUIRED:
            raise _invalid("record has unexpected fields")
        if not _nonempty(record["id"]) or record["id"] in ids:
            raise _invalid("id is missing or duplicated")
        ids.add(record["id"])
        if record["graph"] != data["meta"].get("slug"):
            raise _invalid("graph context does not match this graph")
        if not _nonempty(record["runId"]) or record["nodeId"] not in node_ids:
            raise _invalid("run or node context is invalid")
        if any(not _nonempty(record[field]) for field in ("event", "summary", "idempotencyKey")):
            raise _invalid("event, summary and idempotency key are required")
        if record["idempotencyKey"] in keys:
            raise _invalid("idempotency key is duplicated")
        keys.add(record["idempotencyKey"])
        if record["status"] not in STATUSES:
            raise _invalid("status is invalid")
        if not _timestamp(record["createdAt"]) or not _timestamp(record["updatedAt"]):
            raise _invalid("timestamps must be timezone-aware ISO-8601 values")
        if not _timestamp(record["expiresAt"]):
            raise _invalid("expiry is required")
        actions = record["allowedActions"]
        if not isinstance(actions, list) or not 1 <= len(actions) <= 2:
            raise _invalid("one or two allowed actions are required")
        action_ids = [action.get("id") for action in actions if isinstance(action, dict)]
        if (len(action_ids) != len(actions) or len(set(action_ids)) != len(actions)
                or any(action_id not in ACTION_IDS for action_id in action_ids)
                or any(set(action) != {"id", "label", "effect"}
                       or not _nonempty(action["label"]) or not _nonempty(action["effect"])
                       for action in actions)):
            raise _invalid("allowed actions are invalid")
        events = record["events"]
        if (not isinstance(events, list) or not events
                or any(not isinstance(item, dict) or set(item) != {"at", "type", "by"}
                       or not _timestamp(item["at"]) or not _nonempty(item["type"])
                       or not _nonempty(item["by"]) for item in events)):
            raise _invalid("audit events are invalid")
        event_types = [item["type"] for item in events]
        if (event_types[0] != "opened" or record["createdAt"] != events[0]["at"]
                or record["updatedAt"] != events[-1]["at"]):
            raise _invalid("audit timestamps or opening event are invalid")
        terminal = record["status"]
        if terminal == "open":
            if record["resolution"] is not None or event_types != ["opened"]:
                raise _invalid("open interaction has a terminal result")
        elif terminal == "resolved":
            resolution = record["resolution"]
            if (not isinstance(resolution, dict)
                    or set(resolution) != {"action", "effect"}
                    or not any(action["id"] == resolution["action"]
                               and action["effect"] == resolution["effect"] for action in actions)
                    or event_types != ["opened", "resolved"]):
                raise _invalid("resolution is not an allowed audited action")
        elif record["resolution"] is not None or event_types != ["opened", terminal]:
            raise _invalid("terminal interaction audit is invalid")
