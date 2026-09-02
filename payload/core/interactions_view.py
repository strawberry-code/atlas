"""Proiezione di sola lettura del ledger Interaction per la dashboard.

interactions.py e' il motore transazionale del ledger; qui non si scrive
niente, si legge il record cosi' come il lifecycle lo ha gia' lasciato.
Ogni campo esposto viene da un attributo dichiarato del record (status,
summary, createdAt, updatedAt, expiresAt, nodeId, runId, allowedActions), mai
dalla sequenza 'events': quella e' l'audit, rigiocarla per dedurre uno stato
che il record porta gia' esplicito sarebbe ricostruire lo stato dai log.
"""
from __future__ import annotations

from datetime import datetime, timedelta


def project(data: dict, now: datetime | None = None) -> list[dict]:
    """Una riga per Interaction, coi soli dati minimi che la dashboard mostra."""
    momento = now or datetime.now().astimezone()
    return [_project_one(record, momento) for record in data.get("interactions", [])]


def events_of(data: dict, interaction_id: str) -> list[dict]:
    """Il log di audit di una sola Interaction, letto solo su richiesta esplicita
    (il pannello lo mostra dentro un dettaglio richiudibile, mai in una card).

    Distinto da project(): li' 'events' resta intoccato perche' lo stato
    mostrato non si deriva dal log; qui e' proprio il log quel che si chiede."""
    record = next((r for r in data.get("interactions", []) if r["id"] == interaction_id), None)
    return list(record["events"]) if record else []


def _project_one(record: dict, now: datetime) -> dict:
    creato = datetime.fromisoformat(record["createdAt"])
    stato = record["status"]
    return {
        "id": record["id"],
        "node": record["nodeId"],
        "run": record["runId"],
        "status": stato,
        "summary": record["summary"],
        "age": now - creato,
        "urgency": _urgency(record, now) if stato == "open" else None,
        "resolvedAge": _resolved_age(record, now) if stato != "open" else None,
        "allowedActions": [
            {"id": azione["id"], "label": azione["label"]}
            for azione in record["allowedActions"]
        ],
    }


def _urgency(record: dict, now: datetime) -> timedelta:
    """Quanto manca alla scadenza dichiarata; negativo se e' gia' passata.

    Ha senso solo per una card che aspetta ancora un'azione: una volta
    risolta, annullata o scaduta non c'e' piu' nessuna corsa contro il tempo.
    """
    scade = datetime.fromisoformat(record["expiresAt"])
    return scade - now


def _resolved_age(record: dict, now: datetime) -> timedelta:
    """Da quanto la card e' arrivata al suo esito finale (resolved/cancelled/
    expired). Distinto da 'age' (che resta da createdAt): una card aperta
    ieri e chiusa oggi appartiene a 'risolte oggi', non a ieri."""
    risolto = datetime.fromisoformat(record["updatedAt"])
    return now - risolto
