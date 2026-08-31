"""Ledger atomico delle Interazioni, conservato nel graph.json canonico."""
from __future__ import annotations

from datetime import datetime

from .identity import identity
from .store import StateError


STATUSES = frozenset(("open", "resolved", "cancelled", "expired"))
ACTION_IDS = frozenset(("confirm", "decline", "retry", "cancel", "acknowledge"))
_REQUIRED = frozenset((
    "id", "graph", "runId", "nodeId", "event", "summary", "allowedActions",
    "expiresAt", "idempotencyKey", "status", "createdAt", "updatedAt", "resolution", "events",
))


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


def _next_id(interactions: list[dict]) -> str:
    numbers = [int(record["id"][1:]) for record in interactions
               if isinstance(record.get("id"), str) and record["id"].startswith("I")
               and record["id"][1:].isdigit()]
    return f"I{max(numbers, default=0) + 1:03d}"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _same_request(record: dict, expected: dict) -> bool:
    return all(record.get(key) == value for key, value in expected.items())


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
        if record["resolution"] is not None and not isinstance(record["resolution"], dict):
            raise _invalid("resolution is not an object")
        events = record["events"]
        if (not isinstance(events, list) or not events
                or any(not isinstance(item, dict) or set(item) != {"at", "type", "by"}
                       or not _timestamp(item["at"]) or not _nonempty(item["type"])
                       or not _nonempty(item["by"]) for item in events)):
            raise _invalid("audit events are invalid")
