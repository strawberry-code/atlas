"""Chi e' l'agente che sta parlando, e se e' ancora vivo.

Spezzato da claims.py, che governa il ciclo di vita del lucchetto (prendere,
mollare, chiudere): qui c'e' solo l'anagrafica, cioe' come ci si identifica e
come si accerta che il processo dietro un lucchetto esista ancora. Sono due
lavori diversi, e questo si porta dietro le differenze fra POSIX e Windows.
"""
from __future__ import annotations

import os
import subprocess
import sys

from .config import ENV_IDENTITY


def session() -> tuple[int | None, str | None]:
    """Identita' della sessione agente che ospita il comando, se c'e'."""
    pid = os.environ.get("CLAUDE_PID")
    return (int(pid) if pid and pid.isdigit() else None,
            os.environ.get("CLAUDE_CODE_SESSION_ID"))


IGNOTA = "?"   # nessun segnale d'ambiente dice chi siamo


def identity() -> str:
    """Chi tiene davvero il lucchetto: sovrascrivibile via ATLAS_IDENTITY, altrimenti il PID.

    I subagent di una stessa sessione Claude condividono lo stesso CLAUDE_PID: senza
    un'identita' esplicita, il tetto di claim per sessione e i conflitti di chiusura
    li tratterebbero come un solo attore anche quando lavorano nodi diversi in parallelo.
    """
    if sovrascritta := os.environ.get(ENV_IDENTITY):
        return sovrascritta
    pid, _ = session()
    return str(pid) if pid else IGNOTA


def nota(chi: str | None) -> bool:
    """Un'identita' serve solo se distingue: IGNOTA vuol dire 'non lo so', e due
    'non lo so' non sono la stessa persona."""
    return bool(chi) and chi != IGNOTA


def e_mio(node: dict) -> bool:
    """Vero se il lucchetto e' dimostrabilmente nostro.

    Fuori da una sessione Claude, e senza ATLAS_IDENTITY, nessuno sa chi sia il
    processo corrente. Confrontare due IGNOTA e concludere 'sono io' spegneva la
    mutua esclusione proprio dove serve di piu', cioe' hook, cron e shell nude:
    due agenti diversi si vedevano restituire 'nodo rivendicato' sullo stesso
    nodo, uno dei due rinfrescando il lucchetto dell'altro. Nel dubbio si risponde
    di no, che al massimo costa un --force o un ATLAS_IDENTITY dichiarato.
    """
    return mio_come(node, identity())


def mio_come(node: dict, me: str) -> bool:
    """Come e_mio, ma per un'identita' dichiarata invece di quella dell'ambiente.

    Automata rivendica un nodo per conto del provider che sta per lanciare, quindi
    l'identita' da confrontare non e' quella del processo che chiama.
    """
    return nota(me) and holder(node).get("identity") == me


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
