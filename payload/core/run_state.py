"""Ledger persistente per osservare una singola esecuzione Autopilot."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from .store import StateError, scrivi_atomico


RunStatus = Literal["active", "waiting", "failed", "blocked", "completed"]
TERMINAL_STATUSES = frozenset(("failed", "blocked", "completed"))


class RunStateError(StateError):
    """Stato persistente del run assente, corrotto o incompatibile."""


def _timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="seconds")


class RunState:
    """Snapshot atomico e cronologia degli eventi di un run.

    Il ledger non contiene handle o processi: dopo un'interruzione descrive cio'
    che era accaduto, ma non autorizza il runner a riprendere un agente.
    """

    VERSION = 1

    def __init__(self, path: Path, graph_slug: str, run_id: str | None = None):
        self.path = Path(path)
        self.graph_slug = graph_slug
        existing = self.read(self.path)
        resumable = existing and existing.get("status") not in TERMINAL_STATUSES
        self.run_id = run_id or (existing["run_id"] if resumable else uuid.uuid4().hex[:12])
        self._data: dict | None = None

    @property
    def started(self) -> bool:
        return self._data is not None

    @property
    def data(self) -> dict:
        if self._data is None:
            raise RunStateError("run state has not started")
        return self._data

    def start(self, parallelism: int, frontier: list[str], now: float) -> bool:
        existing = self.read(self.path)
        if existing and existing.get("run_id") == self.run_id:
            self._data = existing
            return False
        stamp = _timestamp(now)
        self._data = {
            "version": self.VERSION,
            "graph": self.graph_slug,
            "run_id": self.run_id,
            "parallelism": parallelism,
            "status": "active",
            "reason": None,
            "started_at": stamp,
            "updated_at": stamp,
            "node": None,
            "provider": None,
            "attempt": None,
            "failure": None,
            "next_at": None,
            "frontier": list(frontier),
            "blockers": [],
            "events": [],
        }
        self.event("run-started", now, frontier=list(frontier), status="active")
        return True

    def event(self, event_type: str, now: float, status: RunStatus | None = None,
              **fields: object) -> None:
        """Registra un evento e aggiorna lo snapshot con i suoi campi utili."""
        data = self.data
        event = {"at": _timestamp(now), "type": event_type}
        if status is not None:
            event["status"] = status
        event.update(fields)
        data["events"].append(event)
        if status is not None:
            data["status"] = status
        for key in ("reason", "node", "provider", "attempt", "failure", "next_at",
                    "frontier", "blockers"):
            if key in fields:
                data[key] = fields[key]
        data["updated_at"] = event["at"]
        self._save()

    def snapshot(self) -> dict:
        return json.loads(json.dumps(self.data))

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        scrivi_atomico(self.path, json.dumps(self.data, ensure_ascii=False, indent=2) + "\n")

    @classmethod
    def read(cls, path: Path) -> dict | None:
        path = Path(path)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as errore:
            raise RunStateError(f"cannot read run state {path}: {errore}") from errore
        required = ("parallelism", "started_at", "updated_at", "frontier", "blockers")
        if (not isinstance(data, dict) or data.get("version") != cls.VERSION
                or any(key not in data for key in required)
                or not isinstance(data.get("graph"), str)
                or not isinstance(data.get("run_id"), str)
                or data.get("status") not in ("active", "waiting", "failed", "blocked", "completed")
                or not isinstance(data.get("events"), list)
                or not isinstance(data.get("frontier"), list)
                or not isinstance(data.get("blockers"), list)):
            raise RunStateError(f"invalid run state {path}")
        return data
