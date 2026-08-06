"""Protocollo del lucchetto: chi tiene un nodo, se e' ancora vivo, chi puo' chiuderlo.

Il claim e' un lucchetto, non un post-it. Chi lo prende ci lascia PID e id di sessione,
e un lucchetto e' orfano quando quel processo non esiste piu': la liveness e' il criterio,
il tempo trascorso e' solo un secondo segnale per la sessione viva ma abbandonata.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta

from . import docs, gitscan
from .config import ENV_IDENTITY, Graph
from .model import by_id, is_done, node_of
from .store import CLAIMED, CLOSED, OPEN, StateError, transaction
from .strings import t


def session() -> tuple[int | None, str | None]:
    """Identita' della sessione agente che ospita il comando, se c'e'."""
    pid = os.environ.get("CLAUDE_PID")
    return (int(pid) if pid and pid.isdigit() else None,
            os.environ.get("CLAUDE_CODE_SESSION_ID"))


def identity() -> str:
    """Chi tiene davvero il lucchetto: sovrascrivibile via ATLAS_IDENTITY, altrimenti il PID.

    I subagent di una stessa sessione Claude condividono lo stesso CLAUDE_PID: senza
    un'identita' esplicita, il tetto di claim per sessione e i conflitti di chiusura
    li tratterebbero come un solo attore anche quando lavorano nodi diversi in parallelo.
    """
    if sovrascritta := os.environ.get(ENV_IDENTITY):
        return sovrascritta
    pid, _ = session()
    return str(pid) if pid else "?"


def alive(pid: int | None, process_name: str = "claude") -> bool:
    """Vero se il processo esiste ed e' ancora l'agente: copre il riuso del PID."""
    if not pid:
        return False
    if sys.platform == "win32":
        return _alive_windows(pid, process_name)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # esiste ma non e' nostro: per noi e' vivo
    out = subprocess.run(["ps", "-o", "comm=", "-p", str(pid)],
                         capture_output=True, text=True).stdout
    return process_name in out


def _alive_windows(pid: int, process_name: str) -> bool:
    """os.kill(pid, 0) su Windows non e' un probe: per segnali diversi da CTRL_C/CTRL_BREAK
    la libc chiama TerminateProcess, quindi 'controllare' un pid lo ammazzerebbe davvero.
    tasklist e' l'unica via sicura per sapere se un processo esiste ancora."""
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                         capture_output=True, text=True).stdout
    return process_name.lower() in out.lower()


def holder(node: dict) -> dict:
    return node.get("claim") or {}


def held_since(node: dict) -> timedelta | None:
    stamp = holder(node).get("at")
    return datetime.now().astimezone() - datetime.fromisoformat(stamp) if stamp else None


def heartbeat_since(node: dict) -> timedelta | None:
    """Come held_since, ma dal battito piu' recente invece che dalla presa iniziale:
    e' il segnale giusto per capire se un lucchetto e' fermo, non da quanto e' aperto."""
    stamp = holder(node).get("heartbeat") or holder(node).get("at")
    return datetime.now().astimezone() - datetime.fromisoformat(stamp) if stamp else None


def claim_state(node: dict, agent: dict) -> str:
    """live, dead o idle: come si presenta un nodo rivendicato."""
    if not alive(holder(node).get("pid"), agent["process_name"]):
        return "dead"
    quiete = heartbeat_since(node)
    return "idle" if quiete and quiete > timedelta(hours=agent["idle_hours"]) else "live"


def mine(data: dict) -> list[dict]:
    me = identity()
    return [n for n in data["nodes"]
            if n["status"] == CLAIMED and holder(n).get("identity") == me]


def claim(ref: Graph, node_id: str, assignee: str | None = None, force: bool = False) -> dict:
    agent = ref.workspace.config["agent"]
    pid, sid = session()
    me = identity()
    with transaction(ref.json_path) as data:
        node = node_of(data, node_id)
        if node["status"] == CLAIMED and holder(node).get("identity") == me:
            node["claim"]["heartbeat"] = datetime.now().astimezone().isoformat(timespec="seconds")
            return dict(node)
        index = by_id(data)
        if node["status"] != OPEN:
            raise StateError(t("claim.non_aperto", id=node_id, stato=node["status"]))
        if bloccanti := [d for d in node["blockedBy"] if not is_done(index[d])]:
            if not force:
                raise StateError(t("claim.bloccato", id=node_id, bloccanti=", ".join(bloccanti)))
        tenuti = [n["id"] for n in mine(data)]
        if len(tenuti) >= agent["max_claims_per_session"] and not force:
            raise StateError(t("claim.tetto", tenuti=", ".join(tenuti),
                               tetto=agent["max_claims_per_session"], primo=tenuti[0]))
        ora = datetime.now().astimezone().isoformat(timespec="seconds")
        node.update(status=CLAIMED, assignee=assignee or agent["default_assignee"],
                    claim={"pid": pid, "session": sid, "identity": me, "at": ora, "heartbeat": ora})
        return dict(node)


def release(ref: Graph, node_id: str, reason: str | None = None) -> dict:
    with transaction(ref.json_path) as data:
        node = node_of(data, node_id)
        if node["status"] != CLAIMED:
            raise StateError(t("release.non_rivendicato", id=node_id, stato=node["status"]))
        if reason:
            data.setdefault("releases", []).append({
                "id": node_id, "title": node["title"], "reason": reason,
                "at": datetime.now().astimezone().isoformat(timespec="seconds"),
            })
        node.update(status=OPEN, assignee=None, claim=None)
        return dict(node)


def close(ref: Graph, node_id: str, summary: str, force: bool = False,
          cost: str | None = None, artifacts: list[str] | None = None) -> dict:
    """Chiude un nodo. Il possesso da parte di una sessione morta non e' un ostacolo."""
    agent = ref.workspace.config["agent"]
    pid, _ = session()
    with transaction(ref.json_path) as data:
        node = node_of(data, node_id)
        if is_done(node):
            raise StateError(t("close.gia_chiuso", id=node_id))
        owner = holder(node).get("identity")
        owner_pid = holder(node).get("pid")
        if node["status"] == CLAIMED and owner != identity() and alive(owner_pid, agent["process_name"]) and not force:
            raise StateError(t("close.altra_sessione", id=node_id, owner=owner))
        if not docs.answer_written(ref, node_id) and not force:
            raise StateError(t("close.risposta_vuota", file=ref.ticket_path(node_id).name))
        preso = holder(node).get("at")
        node.update(status=CLOSED, assignee=None, claim=None, answer=summary, cost=cost,
                    closedBy=identity(),
                    closedAt=datetime.now().astimezone().isoformat(timespec="seconds"))
        if artifacts is None:
            artifacts = gitscan.touched(ref.workspace.project_root, preso) or None
        if artifacts is not None:
            node["artifacts"] = list(artifacts)
        return dict(node)
