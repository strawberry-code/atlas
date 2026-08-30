"""Letture condivise del ledger delle domande."""
from __future__ import annotations

from datetime import datetime, timedelta


QUESTION_AGE = timedelta(hours=24)


def open_questions(data: dict) -> list[dict]:
    return [q for q in data.get("questions", []) if q.get("status") == "open"]


def aged_questions(data: dict, now: datetime | None = None) -> list[dict]:
    momento = now or datetime.now().astimezone()
    return [q for q in open_questions(data) if _is_aged(q, momento)]


def _is_aged(question: dict, now: datetime) -> bool:
    try:
        asked = datetime.fromisoformat(question["askedAt"])
    except (KeyError, TypeError, ValueError):
        return False
    if asked.tzinfo is None:
        asked = asked.astimezone()
    return now - asked >= QUESTION_AGE
