"""Il registro di lavorazione del ticket: chi, quando, cosa ha fatto.

Ogni voce e' un punto elenco sotto '## Lavorazione', nel ticket del nodo:

    - **claude** · 2026-09-21 15:04
      letto il codice del lock, scritto il test che fallisce

La scrive 'atlas log' mentre il nodo e' rivendicato, e 'atlas suspend' ne
scrive una con la nota di sospensione. E' l'unica traccia che sopravvive a un
lavoro interrotto: chi riprende il nodo legge da qui dove si era arrivati, e
'atlas close' rifiuta un ticket che non ne ha nessuna, come gia' rifiuta una
Risposta vuota. La sezione e' testo scritto a mano dopo il marker di chiusura
(docs.MARK_END): qui si appende soltanto, mai si riscrive.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

from .config import ENV_IDENTITY, Graph
from .identity import IGNOTA, nota, session
from .model import node_of
from .store import CLAIMED, StateError, scrivi_atomico, transaction
from .strings import t


def author(ref: Graph, node: dict) -> str:
    """Chi firma la voce: l'identita' dichiarata (ATLAS_IDENTITY o --identity), che
    e' anche il nome del provider lanciato da Autopilot; dentro una sessione Claude
    il nome dell'agente scritto nel claim; altrimenti chi dice 'atlas whoami'.

    Senza identita' dichiarata, se il claim ne porta una dichiarata (diversa dal PID
    che il claim registra comunque), si firma con quella: il lucchetto ha un solo
    detentore, e un subagente che ha preso il nodo con --identity e poi scorda il flag
    su 'log' firmerebbe altrimenti col nome di un altro attore (issue #37)."""
    if dichiarata := os.environ.get(ENV_IDENTITY):
        return dichiarata
    claim = node.get("claim") or {}
    if nota(claim.get("identity")) and claim["identity"] != str(claim.get("pid")):
        return claim["identity"]
    if session()[0] and node.get("assignee"):
        return node["assignee"]
    return ref.workspace.whoami() or node.get("assignee") or IGNOTA


def entry(who: str, when: datetime, text: str) -> str:
    """La voce nel formato del registro: chi e quando sulla prima riga, cosa ha
    fatto rientrato sotto. Righe vuote e spazi ai margini si buttano, cosi' un
    testo incollato da una shell non porta rumore nel ticket."""
    righe = [riga.strip() for riga in text.strip().splitlines() if riga.strip()]
    corpo = "\n".join(f"  {riga}" for riga in righe)
    return f"- **{who}** · {when.strftime('%Y-%m-%d %H:%M')}\n{corpo}\n"


def _sezione(testo: str) -> tuple[int, int] | None:
    """Gli estremi (inizio, fine) del corpo della Lavorazione nel testo del ticket,
    cioe' da dopo la sua intestazione fino all'intestazione successiva o alla fine.
    None se l'intestazione non c'e' piu': un ticket rinominato a mano non si tocca."""
    intestazione = re.search(rf"^{re.escape(t('heading.lavorazione'))}[ \t]*\r?$", testo, re.MULTILINE)
    if not intestazione:
        return None
    prossima = re.search(r"^## ", testo[intestazione.end():], re.MULTILINE)
    fine = intestazione.end() + prossima.start() if prossima else len(testo)
    return intestazione.end(), fine


def written(ref: Graph, node_id: str) -> bool:
    """La Lavorazione contiene testo vero, non solo il commento segnaposto."""
    path = ref.ticket_path(node_id)
    if not path.exists():
        return False
    testo = path.read_text(encoding="utf-8-sig")
    estremi = _sezione(testo)
    if not estremi:
        return False
    corpo = testo[estremi[0]:estremi[1]]
    return bool(re.sub(r"<!--.*?-->", "", corpo, flags=re.S).strip())


def append(ref: Graph, node_id: str, who: str, text: str, when: datetime | None = None) -> Path:
    """Appende una voce in coda alla Lavorazione del ticket, e ne ritorna il path.

    Il ticket deve esistere gia' (lo crea il refresh di ogni comando, 'take'
    compreso) e deve avere ancora la sua intestazione: senza, si dice quale
    file aprire invece di scrivere la voce in un posto a caso.
    """
    path = ref.ticket_path(node_id)
    if not path.exists():
        raise StateError(t("log.ticket_assente", id=node_id, path=path))
    testo = path.read_text(encoding="utf-8-sig")
    estremi = _sezione(testo)
    if not estremi:
        raise StateError(t("log.sezione_assente", heading=t("heading.lavorazione"), path=path))
    inizio, fine = estremi
    corpo = testo[inizio:fine].rstrip()
    voce = entry(who, when or datetime.now().astimezone(), text)
    scrivi_atomico(path, f"{testo[:inizio]}{corpo}\n\n{voce}\n{testo[fine:]}")
    return path


def log(ref: Graph, node_id: str, text: str) -> dict:
    """Il gesto di 'atlas log': una voce nel registro del nodo che si sta lavorando,
    piu' il battito del claim, perche' scrivere cosa si e' fatto e' un segno di
    vita quanto 'progress'. Pretende il nodo rivendicato: fuori dalla lavorazione
    non c'e' niente da registrare, e un nodo sospeso si riprende prima con 'take'."""
    if not isinstance(text, str) or not text.strip():
        raise StateError(t("log.testo_vuoto"))
    with transaction(ref.json_path) as data:
        node = node_of(data, node_id)
        if node["status"] != CLAIMED:
            raise StateError(t("log.non_rivendicato", id=node_id, stato=node["status"]))
        ora = datetime.now().astimezone()
        append(ref, node_id, author(ref, node), text, ora)
        node["claim"]["heartbeat"] = ora.isoformat(timespec="seconds")
        return dict(node)
