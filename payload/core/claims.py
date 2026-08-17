"""Protocollo del lucchetto: prendere un nodo, mollarlo, chiuderlo.

Il claim e' un lucchetto, non un post-it. Chi lo prende ci lascia PID e id di sessione,
e un lucchetto e' orfano quando quel processo non esiste piu': la liveness e' il criterio,
il tempo trascorso e' solo un secondo segnale per la sessione viva ma abbandonata.
Chi siamo e chi e' ancora vivo lo dice identity.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from . import docs, gitscan
from .config import Graph
from .identity import alive, e_mio, holder, identity, nota, session
from .model import by_id, fingerprint, is_done, istante, node_of, claimed
from .store import CLAIMED, CLOSED, OPEN, StateError, load, transaction
from .strings import t


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
    """I nodi che teniamo noi. Con identita' ignota nessun nodo e' dimostrabilmente
    nostro, quindi il tetto per sessione non scatta: e' il verso giusto in cui
    sbagliare, perche' l'alternativa era attribuirci i nodi presi da chiunque altro
    e bloccare un agente per colpa di un suo pari."""
    if not nota(identity()):
        return []
    return [n for n in data["nodes"] if n["status"] == CLAIMED and e_mio(n)]


def claim(ref: Graph, node_id: str, assignee: str | None = None, force: bool = False) -> dict:
    agent = ref.workspace.config["agent"]
    pid, sid = session()
    me = identity()
    with transaction(ref.json_path) as data:
        node = node_of(data, node_id)
        if node["status"] == CLAIMED and e_mio(node):
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
        # Dopo l'update, non prima: il nodo che l'agente si porta via e' questo, con
        # status e assignee gia' cambiati. L'impronta esclude claim, quindi scriverla
        # li' dentro non la invalida.
        node["claim"]["fingerprint"] = fingerprint(node)
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


def _condiviso(data: dict, node_id: str, da: datetime) -> str | None:
    """Chi altro ha chiuso o rilasciato un nodo mentre questo era in lavorazione.

    Il controllo sui nodi rivendicati guarda l'istante della chiusura, la deduzione
    guarda la finestra dalla presa in poi: fra i due c'e' spazio per una sessione che
    prende, lavora e chiude tutta dentro la finestra altrui, e il suo lavoro finirebbe
    negli artefatti di chi chiude dopo. Qui si guarda la finestra intera.

    Un timestamp illeggibile (il grafo e' un file versionato, ci finiscono date
    scritte a mano) vale come 'non lo so', e un non-so vale come collisione: meglio
    un campo vuoto e dichiarato di uno pieno di file altrui. Il messaggio nomina il
    nodo, cosi' chi legge sa quale timestamp riparare.
    """
    for nodo in data["nodes"]:
        if nodo["id"] == node_id or not nodo.get("closedAt"):
            continue
        chiuso = istante(nodo["closedAt"])
        if chiuso is None or chiuso >= da:
            return nodo["id"]
    for rilascio in data.get("releases", []):
        if rilascio.get("id") == node_id:
            continue
        mollato = istante(rilascio.get("at"))
        if mollato is None or mollato >= da:
            return rilascio.get("id") or "?"
    return None


def _artefatti(ref: Graph, node_id: str) -> tuple[list[str] | None, str | None]:
    """Cosa ha toccato la sessione secondo git, piu' l'eventuale avviso di rinuncia.

    Gira FUORI dalla transazione perche' lancia due processi git: su questo repo sono
    24 ms, quattro volte la scrittura del grafo, e su un monorepo diventano secondi in
    cui ogni altro agente resta in coda. Su Windows sarebbe pure peggio, perche'
    msvcrt.locking non attende all'infinito ma molla dopo dieci secondi.

    Legge il grafo senza lock, quindi puo' vedere un istante di presa vecchio di
    millisecondi: e' una fotografia del working tree, non un dato transazionale, e
    un errore di quell'ordine non cambia quali file risultano toccati.
    """
    data = load(ref.json_path)
    if [n for n in claimed(data) if n["id"] != node_id]:
        return None, t("close.artifacts_non_dedotti")
    preso = holder(node_of(data, node_id)).get("at")
    # Senza presa non c'e' finestra da guardare: la deduzione e' gia' su tutto il
    # working tree e restringerla al lavoro di questa sessione non e' possibile.
    if preso:
        inizio = istante(preso)
        if inizio is None:
            return None, t("close.artifacts_presa_illeggibile", id=node_id, at=preso)
        if altro := _condiviso(data, node_id, inizio):
            return None, t("close.artifacts_finestra_condivisa", altro=altro)
    return gitscan.touched(ref.workspace.project_root, preso) or None, None


def close(ref: Graph, node_id: str, summary: str, force: bool = False,
          cost: str | None = None, artifacts: list[str] | None = None) -> tuple[dict, str | None]:
    """Chiude un nodo. Il possesso da parte di una sessione morta non e' un ostacolo.

    Restituisce una tupla (nodo, avviso) dove avviso e' None se la deduzione degli
    artefatti e' avvenuta regolarmente, oppure un messaggio di avvertimento se e'
    stata saltata perche' piu' nodi sono in lavorazione insieme."""
    agent = ref.workspace.config["agent"]
    avviso = None
    if artifacts is None:
        artifacts, avviso = _artefatti(ref, node_id)
    with transaction(ref.json_path) as data:
        node = node_of(data, node_id)
        if is_done(node):
            raise StateError(t("close.gia_chiuso", id=node_id))
        owner = holder(node).get("identity")
        owner_pid = holder(node).get("pid")
        if node["status"] == CLAIMED and not e_mio(node) and alive(owner_pid, agent["process_name"]) and not force:
            raise StateError(t("close.altra_sessione", id=node_id, owner=owner))
        if not docs.answer_written(ref, node_id) and not force:
            raise StateError(t("close.risposta_vuota", file=ref.ticket_path(node_id).name))
        # Un'impronta che non torna vuol dire che il nodo e' cambiato dopo la presa:
        # la scrittura entrerebbe pulita, ma la sintesi che sta arrivando e' stata
        # decisa guardando un nodo diverso. Assente sui claim presi prima della 0.7.0.
        atteso = holder(node).get("fingerprint")
        if atteso and atteso != fingerprint(node) and not force:
            raise StateError(t("close.premessa_scaduta", id=node_id))
        node.update(status=CLOSED, assignee=None, claim=None, answer=summary, cost=cost,
                    closedBy=identity(),
                    closedAt=datetime.now().astimezone().isoformat(timespec="seconds"))
        if artifacts is not None:
            node["artifacts"] = list(artifacts)
        return dict(node), avviso
