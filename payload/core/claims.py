"""Protocollo del lucchetto: prendere un nodo, mollarlo, chiuderlo.

Il claim e' un lucchetto, non un post-it. Chi lo prende ci lascia PID e id di sessione,
e un lucchetto e' orfano quando quel processo non esiste piu': la liveness e' il criterio,
il tempo trascorso e' solo un secondo segnale per la sessione viva ma abbandonata.
Chi siamo e chi e' ancora vivo lo dice identity.py.

Da L02 il claim porta anche host e lease_until: la liveness di un claim remoto non si
verifica col PID (e' un processo di un'altra macchina), quindi diventa un lease a tempo
che ogni lettore confronta col proprio orologio. Il PID resta la lente del holder
locale, il lease quella dei lettori remoti.
"""
from __future__ import annotations

import os
import re
import socket
import time
from datetime import datetime, timedelta

from . import docs, gitscan, interactions, worklog
from .config import ENV_HOST, Graph
from .editor import editing
from .identity import alive, e_mio, holder, identity, mio_come, nota, session
from .model import by_id, fingerprint, is_done, istante, node_of, claimed
from .run_state import RunState
from .store import CLAIMED, CLOSED, OPEN, SUSPENDED, WORKABLE, StateError, load, transaction
from .strings import t


def _host() -> str:
    """Il nome di questa macchina: identifica il holder nei claim.
    Sovrascrivibile via ATLAS_HOST, come ATLAS_IDENTITY per l'agente."""
    return os.environ.get(ENV_HOST) or socket.gethostname()


def _adesso() -> datetime:
    return datetime.now().astimezone()


def _lease_until(ttl: int) -> str:
    """La scadenza di un claim: ISO assoluto con secondi, come lo parla graph.json."""
    return (_adesso() + timedelta(seconds=ttl)).isoformat(timespec="seconds")


def _epoch_da_iso(testo: str | None) -> int | None:
    """L'expiry di un claim resa confrontabile, o None se non si legge."""
    letto = istante(testo)
    return int(letto.timestamp()) if letto else None


def _fresco(scadenza: int | None) -> bool:
    """Vero se un'expiry (epoch) e' ancora nel futuro. Un'expiry assente vale come
    fresco: nel dubbio si lascia lavorare chi tiene, mai lo si dichiara morto (L02)."""
    return scadenza is None or scadenza > int(time.time())


def _mio(node: dict) -> bool:
    """Il claim e' dimostrabilmente nostro: stessa macchina e stessa identita'.

    e_mio da solo confronta l'identita', ma due macchine con la stessa ATLAS_IDENTITY
    si rinfrescerebbero i lucchetti a vicenda: deve combaciare anche il host. Un claim
    senza host (scritto prima del lease) e' locale per costruzione e resta nostro.
    """
    return _mio_come(node, identity())


def _mio_come(node: dict, me: str) -> bool:
    """_mio per un'identita' dichiarata: stessa identita' e stessa macchina.

    Il host deve combaciare come in _mio, altrimenti due macchine che rivendicano
    per conto dello stesso provider si rinfrescherebbero il lucchetto a vicenda.
    """
    if not mio_come(node, me):
        return False
    host_claim = holder(node).get("host")
    return host_claim is None or host_claim == _host()


def held_since(node: dict) -> timedelta | None:
    stamp = holder(node).get("at")
    return datetime.now().astimezone() - datetime.fromisoformat(stamp) if stamp else None


def heartbeat_since(node: dict) -> timedelta | None:
    """Come held_since, ma dal battito piu' recente invece che dalla presa iniziale:
    e' il segnale giusto per capire se un lucchetto e' fermo, non da quanto e' aperto."""
    stamp = holder(node).get("heartbeat") or holder(node).get("at")
    return datetime.now().astimezone() - datetime.fromisoformat(stamp) if stamp else None


def silent_for(node: dict) -> timedelta | None:
    """Da quanto un nodo che ha gia' dichiarato almeno un passo (H01/4, progress())
    non ne dichiara uno nuovo. None se non ne ha mai dichiarato uno: senza un primo
    passo il silenzio non si distingue da un lavoro lecito che non parla, e chi
    chiama (H03) deve restare col solo tetto assoluto a difesa in quel caso."""
    if not holder(node).get("progress"):
        return None
    return heartbeat_since(node)


def claim_state(node: dict, agent: dict) -> str:
    """live, dead o idle: come si presenta un nodo rivendicato.

    Per un claim remoto (host diverso dal mio) la liveness non si puo' verificare
    col PID: il lease e' la lente, e non c'e' idle remoto (un processo vivo ma
    quieto non e' osservabile da un'altra macchina). Per un claim locale resta la
    verifica sul PID con l'idle su idle_hours. Un claim remoto senza lease_until
    vale come fresco, mai come morto: nel dubbio si lascia lavorare.

    Un claim preso con on_behalf_of (Autopilot, per conto del provider che lancia)
    non porta il PID di chi lavora davvero (claim() lo scrive a None apposta): la
    verifica sul processo direbbe sempre morto un lucchetto vivo. Il flag
    'delegated' distingue questo caso da un claim normale senza PID noto (per
    esempio preso fuori da Claude Code, senza CLAUDE_PID in ambiente), che resta
    prudentemente 'dead' come prima. Per un claim delegato la lente e' il lease,
    come per un claim remoto."""
    h = holder(node)
    remoto = h.get("host") and h["host"] != _host()
    if remoto or h.get("delegated"):
        return "live" if _fresco(_epoch_da_iso(h.get("lease_until"))) else "dead"
    if not alive(h.get("pid"), agent["process_name"]):
        return "dead"
    quiete = heartbeat_since(node)
    return "idle" if quiete and quiete > timedelta(hours=agent["idle_hours"]) else "live"


def mine(data: dict) -> list[dict]:
    """I nodi che teniamo noi. Con identita' ignota nessun nodo e' dimostrabilmente
    nostro, quindi il tetto per sessione non scatta: e' il verso giusto in cui
    sbagliare, perche' l'alternativa era attribuirci i nodi presi da chiunque altro
    e bloccare un agente per colpa di un suo pari. Il host deve combaciare come per
    il rinnovo: due macchine con la stessa ATLAS_IDENTITY non sono la stessa sessione."""
    if not nota(identity()):
        return []
    return [n for n in data["nodes"] if n["status"] == CLAIMED and _mio(n)]


def _rinnova_locale(node: dict, ttl: int) -> None:
    """Il battito di chi tiene: aggiorna heartbeat e lease_until insieme. Sono un
    solo gesto, perche' separarli creerebbe due liveness che non si parlano."""
    ora = _adesso()
    node["claim"]["heartbeat"] = ora.isoformat(timespec="seconds")
    node["claim"]["lease_until"] = _lease_until(ttl)


_RINNOVO_ANTICIPO = 2   # L06: rinnova quando manca meno di 1/_RINNOVO_ANTICIPO del TTL alla scadenza


def _da_rinnovare(claim: dict, ttl: int) -> bool:
    """Vicino alla scadenza: manca meno della meta' del TTL, o e' gia' scaduto.

    Un claim senza lease_until (scritto prima del lease) si rinnova: e' la
    migrazione che lo mette in pari col modello nuovo. Il confronto usa lease_until,
    la scadenza che i lettori remoti giudicano, non il heartbeat."""
    scadenza = _epoch_da_iso(claim.get("lease_until"))
    if scadenza is None:
        return True
    return scadenza - _adesso().timestamp() <= ttl // _RINNOVO_ANTICIPO


def rinnova_se_necessario(ref: Graph) -> bool:
    """Il battito di chi tiene: rinnova sotto lock i claim nostri col lease vicino
    alla scadenza, e scrive solo se qualcosa e' cambiato.

    E' il rinnovo-su-lettura di L02/L06, chiamato dal dispatcher su ogni comando che
    carica il grafo mentre la sessione lavora. La soglia (meta' del TTL) evita la
    riscrittura a ogni comando: una raffica in sequenza non produce churn, un comando
    ogni TTL tiene vivo il lease. Toca solo i claim dimostrabilmente nostri (_mio),
    mai quelli altrui. Torna True se ha scritto."""
    agent = ref.workspace.config["agent"]
    if not _rinnovo_dovuto(load(ref.json_path), agent):
        return False
    with transaction(ref.json_path) as data:
        return _rinnova_dati(ref, data, agent) > 0


def _rinnovo_dovuto(data: dict, agent: dict) -> bool:
    """Vero se un claim nostro ha il lease vicino alla scadenza: solo allora il
    rinnovo merita di prendere il lock di scrittura."""
    if not nota(identity()):
        return False
    ttl = agent["lease_ttl_seconds"]
    return any(_da_rinnovare(n["claim"], ttl) for n in mine(data))


def _rinnova_dati(ref: Graph, data: dict, agent: dict) -> int:
    """Rinnova i claim nostri vicini alla scadenza sui dati gia' letti. Torna quanti
    ne ha toccati. Chiamata solo dentro transaction: la scrittura avviene qui."""
    if not nota(identity()):
        return 0
    ttl = agent["lease_ttl_seconds"]
    rinnovati = 0
    for node in mine(data):
        if not _da_rinnovare(node["claim"], ttl):
            continue
        _rinnova_locale(node, ttl)
        rinnovati += 1
    return rinnovati


def claim(ref: Graph, node_id: str, assignee: str | None = None, force: bool = False,
          on_behalf_of: str | None = None) -> dict:
    """Prende il lucchetto, o lo rinnova se e' gia' nostro.

    on_behalf_of scrive nel claim l'identita' dell'agente che lavorera' il nodo,
    non quella del processo che lo prende. Serve ad Autopilot, che rivendica prima
    di lanciare il provider: senza, il figlio troverebbe il proprio nodo tenuto da
    uno sconosciuto e dovrebbe scegliere fra rubare il lucchetto e fermarsi, e in
    AFK fermarsi vuol dire un run morto su un nodo che nessuno sta guardando.
    """
    agent = ref.workspace.config["agent"]
    ttl = agent["lease_ttl_seconds"]
    pid, sid = session()
    me = on_behalf_of or identity()
    if on_behalf_of:
        # Il PID e la sessione sono di chi prende il lucchetto, e chi prende non e'
        # chi lavora: scriverli qui creava un claim che si dichiara vivo con il
        # processo sbagliato, e la liveness sul PID e' proprio cio' che impedisce a
        # un altro di chiuderlo. Per un claim preso per conto d'altri la lente resta
        # il lease, che scade da solo se il lavoro non arriva mai.
        pid, sid = None, None
    with transaction(ref.json_path) as data:
        node = node_of(data, node_id)
        if node["status"] == CLAIMED and _mio_come(node, me):
            _rinnova_locale(node, ttl)
            return dict(node)
        index = by_id(data)
        if node["status"] not in WORKABLE:
            raise StateError(t("claim.non_aperto", id=node_id, stato=node["status"]))
        if bloccanti := [d for d in node["blockedBy"] if not is_done(index[d])]:
            if not force:
                raise StateError(t("claim.bloccato", id=node_id, bloccanti=", ".join(bloccanti)))
        if interactions.has_open(data, node_id, "human-needed") and not force:
            # H05: la stessa mutua esclusione con cui claim() gia' rispetta un
            # bloccante non chiuso, applicata alla domanda aperta invece che a un
            # arco. Senza questo, un altro agente (o la stessa persona da un'altra
            # sessione) potrebbe riprendere il nodo mentre la card aspetta ancora
            # un tap, e la risposta arriverebbe su un lavoro gia' ripartito.
            raise StateError(t("claim.in_attesa_di_persona", id=node_id))
        tenuti = [n["id"] for n in mine(data)]
        if len(tenuti) >= agent["max_claims_per_session"] and not force:
            raise StateError(t("claim.tetto", tenuti=", ".join(tenuti),
                               tetto=agent["max_claims_per_session"], primo=tenuti[0]))
        ora = _adesso().isoformat(timespec="seconds")
        node.update(status=CLAIMED, assignee=assignee or agent["default_assignee"],
                    claim={"pid": pid, "session": sid, "identity": me, "host": _host(),
                           "at": ora, "heartbeat": ora, "lease_until": _lease_until(ttl),
                           "delegated": bool(on_behalf_of)})
        # Dopo l'update, non prima: il nodo che l'agente si porta via e' questo, con
        # status e assignee gia' cambiati. L'impronta esclude claim, quindi scriverla
        # li' dentro non la invalida.
        node["claim"]["fingerprint"] = fingerprint(node)
        return dict(node)


PASSI = ("investigating", "implementing", "verifying", "writing-answer", "blocked")


def _nota_progress(testo: str | None) -> str | None:
    """Il testo libero di 'progress': una riga sola, entro 200 caratteri, mai
    interpretata da un programma. Normalizza invece di rifiutare (a capo e spazi
    ripetuti collassati, coda tagliata): il segnale non deve mai fallire per un
    testo scomodo, coerente con lo scopo di poterlo chiamare spesso e a poco costo."""
    if not testo:
        return None
    return " ".join(testo.split())[:200] or None


def progress(ref: Graph, node_id: str, step: str, note: str | None = None) -> dict:
    """Il segnale di avanzamento (H01/4): scrive il passo dichiarato e rinfresca il
    battito dentro il claim gia' esistente, in una transazione leggera come quella
    del rinnovo-su-lettura. Non tocca lease_until (quello segue la sua cadenza in
    rinnova_se_necessario, non ogni chiamata di progress) ne' rigenera ticket,
    mappa o dashboard: e' pensato per costare poco anche chiamato spesso."""
    if step not in PASSI:
        raise StateError(t("progress.passo_invalido", passo=step, elenco=", ".join(PASSI)))
    with transaction(ref.json_path) as data:
        node = node_of(data, node_id)
        if node["status"] != CLAIMED:
            raise StateError(t("progress.non_rivendicato", id=node_id, stato=node["status"]))
        ora = _adesso().isoformat(timespec="seconds")
        node["claim"]["heartbeat"] = ora
        node["claim"]["progress"] = {"step": step, "note": _nota_progress(note), "at": ora}
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


# H01/2: l'elenco chiuso dei motivi di resa. Un programma li confronta uno per uno,
# quindi restano esattamente questi valori finche' un altro nodo del grafo non li cambia.
MOTIVI_RESA = ("infeasible", "missing-resource", "blocked-environment", "needs-redesign")


def _prossimo_id_resa(data: dict) -> str:
    numeri = [int(s["id"][1:]) for s in data.get("surrenders", [])
              if isinstance(s.get("id"), str) and re.fullmatch(r"Y\d+", s["id"])]
    return f"Y{max(numeri, default=0) + 1:03d}"


def give_up(ref: Graph, node_id: str, reason: str, detail: str) -> dict:
    """La resa (H01/2): un esito terminale che l'agente dichiara, mai un guasto.

    Stessa transazione di release() sul lucchetto (CLAUDE -> OPEN), piu' un record
    append-only in data["surrenders"]: e' il canale che autopilot.py intercetta prima
    di classificare il nodo non chiuso come terminazione ambigua (H04). Senza questo
    record la resa rientrava fra i guasti ritentabili e bruciava tentativi identici
    su un esito che l'agente aveva gia' dichiarato definitivo.
    """
    if reason not in MOTIVI_RESA:
        raise StateError(t("give_up.motivo_invalido", motivo=reason,
                           elenco=", ".join(MOTIVI_RESA)))
    if not isinstance(detail, str) or not detail.strip():
        raise StateError(t("give_up.dettaglio_vuoto"))
    with transaction(ref.json_path) as data:
        node = node_of(data, node_id)
        if node["status"] != CLAIMED:
            raise StateError(t("give_up.non_rivendicato", id=node_id, stato=node["status"]))
        data.setdefault("surrenders", []).append({
            "id": _prossimo_id_resa(data), "node": node_id, "reason": reason,
            "detail": detail.strip(), "by": identity(),
            "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        })
        node.update(status=OPEN, assignee=None, claim=None)
        return dict(node)


def suspend(ref: Graph, node_id: str, note: str) -> dict:
    """La sospensione: lavoro parziale congelato nel nodo, non un esito.

    Stessa transazione di release() sul lucchetto, ma il nodo va a SUSPENDED e
    non a OPEN: chi lo trova sulla frontiera sa che nel ticket c'e' gia' del
    lavoro da rileggere prima di ricominciare. La nota e' obbligatoria e finisce
    in due posti, nel ledger 'suspensions' (da cui la mappa e il brief la
    rileggono) e come voce del registro di Lavorazione. Il registro deve avere
    gia' almeno una voce prima della nota: un lavoro parziale di cui il ticket
    non dice niente non e' un lavoro parziale, e' un rilascio (release). La voce
    nel ticket si scrive prima di toccare il nodo: se il ticket manca, il grafo
    resta com'era.
    """
    if not isinstance(note, str) or not note.strip():
        raise StateError(t("suspend.nota_vuota"))
    with transaction(ref.json_path) as data:
        node = node_of(data, node_id)
        if node["status"] != CLAIMED:
            raise StateError(t("suspend.non_rivendicato", id=node_id, stato=node["status"]))
        if not worklog.written(ref, node_id):
            raise StateError(t("suspend.lavorazione_vuota", id=node_id,
                               file=ref.ticket_path(node_id).name))
        chi, ora = worklog.author(ref, node), _adesso()
        worklog.append(ref, node_id, chi, t("log.sospeso", nota=note.strip()), ora)
        data.setdefault("suspensions", []).append({
            "id": node_id, "title": node["title"], "note": note.strip(), "by": chi,
            "at": ora.isoformat(timespec="seconds"),
        })
        node.update(status=SUSPENDED, assignee=None, claim=None)
        return dict(node)


def _run_id_corrente(ref: Graph) -> str:
    """Il campo runId della card (H05): il run-state di Autopilot se un run e'
    vivo su questo grafo, l'identita' di chi chiama per una sessione manuale
    fuori da un run. Solo un'etichetta d'audit: a differenza delle card che il
    runner apre su se stesso (decision-required, run-stopped), qui nessuno resta
    in attesa sul canale in-process che 'runId' aiuta ad appaiare."""
    esistente = RunState.read(ref.run_state_path)
    return esistente["run_id"] if esistente else identity()


def ask_human(ref: Graph, node_id: str, question: str) -> dict:
    """L'esito 'serve una persona' (H01/3, H05): mette il nodo in attesa sopra
    un'Interazione dell'unico ledger che gia' esiste (interactions.py), non un
    canale nuovo. A differenza di give_up non e' terminale: il claim si rilascia
    perche' un lease non deve restare acceso per le ore in cui una persona non ha
    ancora guardato il telefono, ma claim() rifiuta di riprendere il nodo finche'
    la card resta aperta (has_open) e resolve_interaction() la chiude alla
    risposta, riaprendo il nodo alla frontiera.

    Passa da editing() e non dalla transazione leggera di give_up/release: la
    card che open_interaction scrive va validata come ogni altra (validate_
    interactions), e quella validazione gira solo dentro editing().
    """
    if not isinstance(question, str) or not question.strip():
        raise StateError(t("ask_human.domanda_vuota"))
    with editing(ref) as g:
        node = g.node(node_id)
        if node["status"] != CLAIMED:
            raise StateError(t("ask_human.non_rivendicato", id=node_id, stato=node["status"]))
        run_id = _run_id_corrente(ref)
        record = interactions.open_interaction(
            g, run_id=run_id, node_id=node_id, event="human-needed",
            summary=question.strip(),
            allowed_actions=[
                {"id": "confirm", "label": t("autopilot.action_confirm"), "effect": "confirmed"},
                {"id": "decline", "label": t("autopilot.action_decline"), "effect": "declined"},
            ],
            expires_at=(_adesso() + interactions.SCADENZA_DECISIONE).isoformat(timespec="seconds"),
            # Univoca per presa: un nuovo tentativo dello stesso nodo non puo'
            # chiamare ask_human senza riclaimarlo (claim scrive un 'at' fresco),
            # e claim() rifiuta comunque la presa finche' questa card resta aperta.
            idempotency_key=f"{run_id}:{node_id}:human-needed:{node['claim']['at']}")
        node.update(status=OPEN, assignee=None, claim=None)
        return record


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
    # Un rilascio o una sospensione altrui nella finestra dicono la stessa cosa di
    # una chiusura: qualcun altro ha lavorato, e git non sa di chi e' ciascun file.
    for evento in (*data.get("releases", []), *data.get("suspensions", [])):
        if evento.get("id") == node_id:
            continue
        mollato = istante(evento.get("at"))
        if mollato is None or mollato >= da:
            return evento.get("id") or "?"
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


def _avviso_artefatti_non_tracciati(ref: Graph, artifacts: list[str] | None) -> str | None:
    """Avvisa senza bloccare se gli artefatti registrati sono fuori dall'indice Git.

    Il controllo riguarda solo file presenti: un artefatto mancante resta materia di
    doctor. Un progetto senza Git non offre una semantica di tracciamento, quindi non
    va trattato come un errore.
    """
    if not artifacts:
        return None
    root = ref.workspace.project_root
    mancanti = [a for a in artifacts if not (root / a).exists()]
    non_tracciati = [a for a in artifacts
                     if (root / a).exists() and gitscan.tracked(root, a) is False]
    avvisi = []
    if mancanti:
        avvisi.append(t("close.artifacts_mancanti", elenco=", ".join(mancanti)))
    if non_tracciati:
        avvisi.append(t("close.artifacts_non_tracciati", elenco=", ".join(non_tracciati)))
    return "\n".join(avvisi) or None


def _verifica_chiusura(node: dict, node_id: str, agent: dict) -> None:
    """Il nodo si chiude solo se la liveness lo permette, locale o remota.

    Un claim remoto (host diverso dal mio) si chiude a lease scaduto, come un morto
    locale; finche' e' fresco no. Un claim locale resta sul PID. --force bypassa."""
    h = holder(node)
    if h.get("host") and h["host"] != _host():
        if _fresco(_epoch_da_iso(h.get("lease_until"))):
            raise StateError(t("close.remoto_tenuto", id=node_id, host=h["host"]))
        return
    if not e_mio(node) and alive(h.get("pid"), agent["process_name"]):
        raise StateError(t("close.altra_sessione", id=node_id, owner=h.get("identity")))


def close(ref: Graph, node_id: str, summary: str, force: bool = False,
          cost: str | None = None, artifacts: list[str] | None = None) -> tuple[dict, str | None]:
    """Chiude un nodo. Il possesso da parte di una sessione morta non e' un ostacolo.

    Restituisce una tupla (nodo, avviso). Quando la deduzione automatica non e'
    attendibile, la chiusura richiede una dichiarazione esplicita degli artefatti:
    anche una lista vuota significa intenzionalmente 'nessun artefatto'."""
    agent = ref.workspace.config["agent"]
    avviso = None
    if artifacts is None:
        artifacts, avviso = _artefatti(ref, node_id)
        if avviso:
            raise StateError(t("close.artifacts_required", dettaglio=avviso))
        if fuori := gitscan.vicini(ref.workspace.project_root, artifacts or []):
            avviso = t("close.artifacts_fuori_finestra", id=node_id, elenco=", ".join(fuori))
    non_tracciati = _avviso_artefatti_non_tracciati(ref, artifacts)
    if non_tracciati:
        avviso = non_tracciati if avviso is None else avviso + "\n" + non_tracciati
    with transaction(ref.json_path) as data:
        node = node_of(data, node_id)
        if is_done(node):
            raise StateError(t("close.gia_chiuso", id=node_id))
        if not force:
            if node["status"] == CLAIMED:
                _verifica_chiusura(node, node_id, agent)
        if not docs.answer_written(ref, node_id) and not force:
            raise StateError(t("close.risposta_vuota", file=ref.ticket_path(node_id).name))
        if not worklog.written(ref, node_id) and not force:
            raise StateError(t("close.lavorazione_vuota", file=ref.ticket_path(node_id).name))
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
        chiuso = dict(node)
    return chiuso, avviso
