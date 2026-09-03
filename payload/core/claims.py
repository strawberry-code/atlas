"""Protocollo del lucchetto: prendere un nodo, mollarlo, chiuderlo.

Il claim e' un lucchetto, non un post-it. Chi lo prende ci lascia PID e id di sessione,
e un lucchetto e' orfano quando quel processo non esiste piu': la liveness e' il criterio,
il tempo trascorso e' solo un secondo segnale per la sessione viva ma abbandonata.
Chi siamo e chi e' ancora vivo lo dice identity.py.

Da L02 il claim porta anche host e lease_until: la liveness di un claim remoto non si
verifica col PID (e' un processo di un'altra macchina), quindi diventa un lease a tempo
che ogni lettore confronta col proprio orologio. Il PID resta la lente del holder
locale, il lease quella dei lettori remoti. Da L04 il lucchetto remoto si consuma
attraverso l'holder di remotelock.py: se non e' attivo, il percorso e' identico a prima.
"""
from __future__ import annotations

import os
import re
import socket
from datetime import datetime, timedelta

from . import docs, gitscan, interactions, remotelock
from .config import ENV_HOST, Graph
from .editor import editing
from .identity import alive, e_mio, holder, identity, mio_come, nota, session
from .model import by_id, fingerprint, is_done, istante, node_of, claimed
from .remotelock import (ACQUISITO, GARA, NON_SCADUTO, NON_TUO, RETE, TENUTO,
                         fresco, nome_lock, scadenza_epoch)
from .run_state import RunState
from .store import CLAIMED, CLOSED, OPEN, StateError, load, transaction
from .strings import t


def _host() -> str:
    """Il nome di questa macchina: identifica il holder nei claim e nelle ref remote.
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
        return "live" if fresco(_epoch_da_iso(h.get("lease_until"))) else "dead"
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


def _rinnova_remoto(ref: Graph, node_id: str, ttl: int) -> bool:
    """Allunga la ref remota della nostra lock, o rifiuta.

    Il rinnovo tocca solo le nostre lock: una ref fresca di un'altra macchina e'
    di un altro, e risponderebbe comunque NonTuo dal trasporto. Torna True se la
    ref e' confermata (o il trasporto e' spento), False se la rete non risponde:
    il rinnovo degrada invece di alzare, cosi' una lettura non muore su un remote
    irraggiungibile (L07). Una ref altrui fresca o una gara restano errori: sono
    conflitti reali, non un down della rete."""
    esito = remotelock.rinnova(nome_lock(ref, node_id), _host(), scadenza_epoch(ttl))
    if esito.kind in (ACQUISITO, remotelock.DISATTIVO):
        return True
    if esito.kind == NON_TUO:
        raise StateError(t("claim.remoto_tenuto", id=node_id, host=esito.host))
    if esito.kind == RETE:
        return False
    raise StateError(t("claim.remoto_gara", id=node_id))


def _avvisa_rete() -> None:
    """L'avviso unico quando il rinnovo degrada: il remote non risponde.

    Stampare qui e' l'unico canale che arriva a chi usa il CLI senza toccare il
    dispatcher: rinnova_se_necessario e' chiamato da cli che ignora il ritorno,
    e una lettura che degrada deve dirlo, non tacere."""
    print(t("claim.remoto_rete_rinnovo"))


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
    ne ha toccati. Chiamata solo dentro transaction: la scrittura avviene qui.

    Quando la rete non conferma la ref (RETE) il rinnovo locale non parte: allungare
    il lease del grafo fingerebbe una lock che non possiamo dimostrare di tenere, e
    la ref scadrebbe comunque. Si avvisa una volta e si passa al prossimo claim."""
    if not nota(identity()):
        return 0
    ttl = agent["lease_ttl_seconds"]
    rinnovati = 0
    degradato = False
    for node in mine(data):
        if not _da_rinnovare(node["claim"], ttl):
            continue
        if remotelock.attivo() and not _rinnova_remoto(ref, node["id"], ttl):
            degradato = True
            continue
        _rinnova_locale(node, ttl)
        rinnovati += 1
    if degradato:
        _avvisa_rete()
    return rinnovati


def _assicura_remoto(ref: Graph, node_id: str, ttl: int) -> None:
    """Prende la ref remota prima di scrivere il claim locale, o rifiuta.

    La verita' remota sta nella ref: il claim locale si scrive solo se la ref e'
    libera o scaduta. Una lock fresca di un'altra macchina non si prende qui. Un
    errore di trasporto chiude a chiave: senza poter consultare la ref, scrivere
    il claim creerebbe due verita' sullo stesso nodo."""
    nome = nome_lock(ref, node_id)
    scadenza = scadenza_epoch(ttl)
    esito = remotelock.acquire(nome, _host(), scadenza)
    if esito.kind == ACQUISITO:
        return
    if esito.kind == TENUTO:
        if fresco(esito.scadenza):
            raise StateError(t("claim.remoto_tenuto", id=node_id, host=esito.host))
        rubato = remotelock.ruba(nome, _host(), scadenza)
        if rubato.kind == ACQUISITO:
            return
        if rubato.kind == NON_SCADUTO:
            raise StateError(t("claim.remoto_tenuto", id=node_id,
                               host=rubato.host or esito.host))
        if rubato.kind == RETE:
            raise StateError(t("claim.remoto_rete", id=node_id))
        raise StateError(t("claim.remoto_gara", id=node_id))
    if esito.kind == RETE:
        raise StateError(t("claim.remoto_rete", id=node_id))
    raise StateError(t("claim.remoto_gara", id=node_id))


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
            if remotelock.attivo():
                if not _rinnova_remoto(ref, node_id, ttl):
                    # Il nodo e' gia' nostro e la rete non risponde: il reclaim non
                    # crea nessuna verita' nuova, quindi non fallisce. Ma senza la
                    # ref confermata non si allunga nemmeno il lease locale, che
                    # fingerebbe una lock non dimostrabile. Si avvisa e si esce.
                    _avvisa_rete()
                    return dict(node)
            _rinnova_locale(node, ttl)
            return dict(node)
        index = by_id(data)
        if node["status"] != OPEN:
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
        if remotelock.attivo():
            _assicura_remoto(ref, node_id, ttl)
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


def _assicura_rilascio(ref: Graph, node_id: str) -> None:
    """Libera la ref remota prima di riaprire il nodo, o non lo riapre.

    Un nodo che torna OPEN dev'essere prendibile dalle altre macchine: la ref va
    giu', altrimenti la nuova presa remota vedrebbe una lock fresca e rifiuterebbe."""
    esito = remotelock.rilascia(nome_lock(ref, node_id), _host())
    if esito.kind in (ACQUISITO, remotelock.DISATTIVO):
        return
    if esito.kind == NON_TUO:
        raise StateError(t("release.remoto_non_tuo", id=node_id, host=esito.host))
    if esito.kind == RETE:
        raise StateError(t("release.remoto_rete", id=node_id))
    raise StateError(t("release.remoto_gara", id=node_id))


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
        if remotelock.attivo():
            _assicura_rilascio(ref, node_id)
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
        if remotelock.attivo():
            _assicura_rilascio(ref, node_id)
        data.setdefault("surrenders", []).append({
            "id": _prossimo_id_resa(data), "node": node_id, "reason": reason,
            "detail": detail.strip(), "by": identity(),
            "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        })
        node.update(status=OPEN, assignee=None, claim=None)
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
    """L'esito 'serve una persona' (H01/3, H05): sospende il nodo sopra
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
        if remotelock.attivo():
            _assicura_rilascio(ref, node_id)
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


# Il segnale che la rete non ha saputo dire se altre macchine tengono qualcosa:
# _condiviso lo restituisce per far dichiarare gli artefatti in sicurezza (L07).
# Non e' un id di nodo: e' un oggetto sentinella, impossibile da confondere.
_REMOTO_IRRAGGIUNGIBILE = object()


def _condiviso(ref: Graph, data: dict, node_id: str, da: datetime) -> str | object | None:
    """Chi altro ha chiuso o rilasciato un nodo mentre questo era in lavorazione.

    Il controllo sui nodi rivendicati guarda l'istante della chiusura, la deduzione
    guarda la finestra dalla presa in poi: fra i due c'e' spazio per una sessione che
    prende, lavora e chiude tutta dentro la finestra altrui, e il suo lavoro finirebbe
    negli artefatti di chi chiude dopo. Qui si guarda la finestra intera.

    Un timestamp illeggibile (il grafo e' un file versionato, ci finiscono date
    scritte a mano) vale come 'non lo so', e un non-so vale come collisione: meglio
    un campo vuoto e dichiarato di uno pieno di file altrui. Il messaggio nomina il
    nodo, cosi' chi legge sa quale timestamp riparare.

    Da L07, col lucchetto remoto attivo, entra nella finestra anche la verita'
    remota: il grafo locale puo' essere in ritardo di sync, e una ref presa da
    un'altra macchina durante la lavorazione e' una collisione come una chiusura
    locale. Un remote che la rete non sa leggere vale come collisione (_REMOTO_IRRAGGIUNGIBILE).
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
    if remotelock.attivo():
        return _condiviso_remoto(ref, node_id, da)
    return None


def _condiviso_remoto(ref: Graph, node_id: str, da: datetime) -> str | object | None:
    """Una ref remota su un altro nodo presa nella finestra e' una collisione.

    La ref non dice quando e' stata presa, dice quando scade: la presa si stima con
    scadenza - TTL, che per una ref mai rinnovata e' la presa vera e per una rinnovata
    e' l'ultimo contatto (comunque dentro la finestra se >= da). Una ref che la rete
    non sa leggere vale come collisione: non posso escludere che altri abbiano
    lavorato, e meglio un campo vuoto e dichiarato. La ref del nodo che si sta
    chiudendo non conta: la sta liberando la chiusura. Col trasporto spento la
    finestra e' quella di oggi, senza remoto.
    """
    ttl = ref.workspace.config["agent"]["lease_ttl_seconds"]
    soglia = da.timestamp()
    mio_host = _host()
    prefisso = ref.slug + "/"
    try:
        letto = remotelock.elenca()
    except Exception:
        return _REMOTO_IRRAGGIUNGIBILE          # un trasporto che alza invece di rispondere
    if not isinstance(letto, list):
        return _REMOTO_IRRAGGIUNGIBILE          # RETE: non so = collisione
    for esito in letto:
        nome = esito.nome or ""
        if not nome.startswith(prefisso):
            continue
        id_remoto = nome[len(prefisso):]
        if id_remoto == node_id or esito.host == mio_host:
            continue
        if esito.scadenza is None:
            return id_remoto                    # scadenza ignota: non si puo' escludere
        if esito.scadenza - ttl >= soglia:
            return id_remoto
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
        if altro := _condiviso(ref, data, node_id, inizio):
            if altro is _REMOTO_IRRAGGIUNGIBILE:
                return None, t("close.artifacts_remoto_rete")
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
    mancanti = [a for a in artifacts if not (root / a).is_file()]
    non_tracciati = [a for a in artifacts
                     if (root / a).is_file() and gitscan.tracked(root, a) is False]
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
        if fresco(_epoch_da_iso(h.get("lease_until"))):
            raise StateError(t("close.remoto_tenuto", id=node_id, host=h["host"]))
        return
    if not e_mio(node) and alive(h.get("pid"), agent["process_name"]):
        raise StateError(t("close.altra_sessione", id=node_id, owner=h.get("identity")))


def _consulta_ref_close(ref: Graph, node_id: str) -> None:
    """La ref remota non deve dire 'tenuta da un altro, fresca' mentre si chiude.

    Copre il caso in cui il grafo locale e' in ritardo sulla sync: il nodo puo'
    risultare non rivendicato qui, ma un'altra macchina lo sta lavorando. La ref e'
    la verita' di acquisizione, e se e' fresca e altrui la chiusura creerebbe due
    verita'. Se la ref e' nostra, scaduta o assente, la chiusura prosegue."""
    esito = remotelock.stato(nome_lock(ref, node_id))
    if esito.kind == RETE:
        raise StateError(t("close.remoto_rete", id=node_id))
    if esito.kind == TENUTO and esito.host != _host() and fresco(esito.scadenza):
        raise StateError(t("close.remoto_tenuto", id=node_id, host=esito.host))


def _libera_ref_close(ref: Graph, node_id: str, avviso: str | None) -> str | None:
    """Molla la ref di un nodo chiuso, senza far fallire la chiusura.

    Il nodo e' ormai chiuso: una ref rimasta appesa scade da sola e non crea due
    verita'. Se la rete non risponde lo si dice nell'avviso invece di bloccare."""
    esito = remotelock.rilascia(nome_lock(ref, node_id), _host())
    if esito.kind != RETE:
        return avviso
    msg = t("close.remoto_rete_rilascio", id=node_id)
    return msg if avviso is None else avviso + "\n" + msg


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
            if remotelock.attivo():
                _consulta_ref_close(ref, node_id)
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
        chiuso = dict(node)
    if remotelock.attivo():
        avviso = _libera_ref_close(ref, node_id, avviso)
    return chiuso, avviso
