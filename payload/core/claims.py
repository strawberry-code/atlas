"""Protocollo del lucchetto: chi tiene un nodo, se e' ancora vivo, chi puo' chiuderlo.

Il claim e' un lucchetto, non un post-it. Chi lo prende ci lascia PID e id di sessione,
e un lucchetto e' orfano quando quel processo non esiste piu': la liveness e' il criterio,
il tempo trascorso e' solo un secondo segnale per la sessione viva ma abbandonata.
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta

from . import docs
from .config import Graph
from .model import by_id, is_done, node_of
from .store import CLAIMED, CLOSED, OPEN, StateError, transaction


def session() -> tuple[int | None, str | None]:
    """Identita' della sessione agente che ospita il comando, se c'e'."""
    pid = os.environ.get("CLAUDE_PID")
    return (int(pid) if pid and pid.isdigit() else None,
            os.environ.get("CLAUDE_CODE_SESSION_ID"))


def alive(pid: int | None, process_name: str = "claude") -> bool:
    """Vero se il processo esiste ed e' ancora l'agente: copre il riuso del PID."""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # esiste ma non e' nostro: per noi e' vivo
    out = subprocess.run(["ps", "-o", "comm=", "-p", str(pid)],
                         capture_output=True, text=True).stdout
    return process_name in out


def holder(node: dict) -> dict:
    return node.get("claim") or {}


def held_since(node: dict) -> timedelta | None:
    stamp = holder(node).get("at")
    return datetime.now().astimezone() - datetime.fromisoformat(stamp) if stamp else None


def claim_state(node: dict, agent: dict) -> str:
    """live, dead o idle: come si presenta un nodo rivendicato."""
    if not alive(holder(node).get("pid"), agent["process_name"]):
        return "dead"
    held = held_since(node)
    return "idle" if held and held > timedelta(hours=agent["idle_hours"]) else "live"


def mine(data: dict) -> list[dict]:
    pid, _ = session()
    return [n for n in data["nodes"]
            if n["status"] == CLAIMED and holder(n).get("pid") == pid]


def claim(ref: Graph, node_id: str, assignee: str | None = None, force: bool = False) -> dict:
    agent = ref.workspace.config["agent"]
    pid, sid = session()
    with transaction(ref.json_path) as data:
        node = node_of(data, node_id)
        index = by_id(data)
        if node["status"] != OPEN:
            raise StateError(f"{node_id} non è aperto: sta a '{node['status']}'")
        if bloccanti := [d for d in node["blockedBy"] if not is_done(index[d])]:
            if not force:
                raise StateError(f"{node_id} è bloccato da {', '.join(bloccanti)}")
        tenuti = [n["id"] for n in mine(data)]
        if len(tenuti) >= agent["max_claims_per_session"] and not force:
            raise StateError(
                f"questa sessione tiene già {', '.join(tenuti)}: "
                f"il tetto è {agent['max_claims_per_session']} per sessione.\n"
                f"  Rilascia con 'atlas release {tenuti[0]}', apri un'altra sessione,\n"
                f"  oppure forza con --force se sai cosa stai facendo."
            )
        node.update(status=CLAIMED, assignee=assignee or agent["default_assignee"],
                    claim={"pid": pid, "session": sid,
                           "at": datetime.now().astimezone().isoformat(timespec="seconds")})
        return dict(node)


def release(ref: Graph, node_id: str) -> dict:
    with transaction(ref.json_path) as data:
        node = node_of(data, node_id)
        if node["status"] != CLAIMED:
            raise StateError(f"{node_id} non è rivendicato: sta a '{node['status']}'")
        node.update(status=OPEN, assignee=None, claim=None)
        return dict(node)


def close(ref: Graph, node_id: str, summary: str, force: bool = False) -> dict:
    """Chiude un nodo. Il possesso da parte di una sessione morta non e' un ostacolo."""
    agent = ref.workspace.config["agent"]
    pid, _ = session()
    with transaction(ref.json_path) as data:
        node = node_of(data, node_id)
        if is_done(node):
            raise StateError(f"{node_id} è già chiuso")
        owner = holder(node).get("pid")
        if node["status"] == CLAIMED and owner != pid and alive(owner, agent["process_name"]) and not force:
            raise StateError(f"{node_id} è rivendicato da un'altra sessione viva ({owner})")
        if not docs.answer_written(ref, node_id) and not force:
            raise StateError(
                f"la sezione Risposta di {ref.ticket_path(node_id).name} è vuota.\n"
                f"  Scrivila prima di chiudere, oppure usa --force se il nodo\n"
                f"  si chiude senza risposta perché è diventato irrilevante."
            )
        node.update(status=CLOSED, assignee=None, claim=None, answer=summary,
                    closedAt=datetime.now().astimezone().isoformat(timespec="seconds"))
        return dict(node)
