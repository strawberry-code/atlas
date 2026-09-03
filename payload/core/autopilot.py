"""Entry point e ciclo bounded per una singola esecuzione di Autopilot."""
from __future__ import annotations

import argparse
import os
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import (capability, claims, docs, interactions, mutate, relay_client,
              relay_identity, render, telegram_actions, telegram_status, telegram_view)
from .adapters import (
    DEFAULT_MODEL,
    FALLBACK_MODEL,
    AdapterRegistry,
    AdapterRegistryError,
    AgentOutcome,
    LaunchContext,
    ProviderUnavailableError,
)
from .config import Graph
from .model import blocked, claimed, frontier, is_done, istante, node_of, waiting_human
from .retry import (RETRYABLE_FAILURES, AmbiguousTerminationError, RetryPolicy,
                    RetryState, SurrenderedError, classify_failure)
from .run_state import RunState
from .store import CLAIMED, StateError, load, read_transaction
from .strings import t


Launcher = Callable[["Run", dict], object]
RunLogger = Callable[[str], None]


@dataclass(frozen=True)
class ClosureEvent:
    """Notifica non autorevole che un nodo potrebbe essere terminale.

    L'evento sveglia il runner, ma non porta lo stato: la decisione resta la
    rilettura atomica di Atlas. Un evento per un nodo gia' visto e' quindi un
    duplicato o un ritardo e non produce lavoro.
    """

    node_id: str


Waiter = Callable[[object], ClosureEvent | tuple[ClosureEvent, ...] | AgentOutcome | None]
InteractionWaiter = Callable[[str, str, float | None], "interactions.ResolutionEvent | None"]

# Ogni quanto il runner smette di aspettare l'evento e torna a guardare il grafo.
# Il canale in-process resta quello che lo sveglia subito; questa e' la rete di
# sicurezza per una risposta arrivata da un altro processo, che quel canale non
# vede, e per una card che nessuno raccoglie.
RILETTURA_INTERAZIONE = 30.0


class RunnerError(StateError):
    """Il ciclo non puo' avanzare o dichiarare una terminazione valida."""


@dataclass(frozen=True)
class RunResult:
    """Esito del ciclo, ricostruito solo dallo stato terminale di Atlas."""

    terminal_nodes: tuple[str, ...]


@dataclass(frozen=True)
class Run:
    """Configurazione del run e accesso ai ledger persistenti."""

    graph: Graph
    parallelism: int
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    retry_state: RetryState | None = field(default=None, repr=False, compare=False)
    run_state: RunState | None = field(default=None, repr=False, compare=False)
    _started: set[str] = field(default_factory=set, init=False, repr=False, compare=False)
    log: list[str] = field(default_factory=list, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.retry_state is None:
            object.__setattr__(self, "retry_state",
                               RetryState(self.graph.retry_state_path, self.graph.slug))
        if self.run_state is None:
            object.__setattr__(self, "run_state",
                               RunState(self.graph.run_state_path, self.graph.slug))

    @property
    def serial(self) -> bool:
        """Indica esplicitamente il caso in cui il parallelismo e' seriale."""
        return self.parallelism == 1

    def execute(self, launcher: Launcher, wait_for: Waiter | None = None,
                now: Callable[[], float] = time.time,
                sleeper: Callable[[float], None] = time.sleep,
                interaction_waiter: InteractionWaiter | None = None) -> RunResult:
        """Esegue il ciclo bounded della frontiera Atlas.

        Il runner riempie gli slot disponibili fino a ``parallelism`` e conserva gli
        handle in ordine di avvio. Attende il primo attivo prima di rileggere la
        frontiera e riempire lo slot liberato: cosi' il caso 1 resta strettamente
        seriale, mentre un valore maggiore permette lavoro sovrapposto senza mai
        superare il limite. Il waiter puo' restituire una o piu' ClosureEvent, ma
        gli eventi sono solo notifiche: la chiusura si accetta soltanto da Atlas.

        Il launcher e' una primitiva, non un adapter o un provider. Riceve il run e
        il nodo gia' rivendicato e puo' restituire un handle. La chiusura resta
        registrata dalle primitive Atlas usate dal lavoro lanciato; dopo ogni attesa
        il grafo viene riletto prima di scegliere altro lavoro.
        """
        return execute(self, launcher, wait_for, now, sleeper, interaction_waiter)


def start(graph: Graph, parallelism: object, retry_policy: RetryPolicy | None = None,
          retry_state_path=None, run_state_path=None) -> Run:
    """Crea un run dopo aver validato il limite richiesto dall'utente."""
    if type(parallelism) is not int or parallelism <= 0:
        raise ValueError(t("autopilot.parallelism_invalid"))
    # L'ordine conta: RunState decide se questa e' una ripresa o un run nuovo, e
    # il ledger dei tentativi deve saperlo per non spendere il budget di un altro.
    run_state = RunState(run_state_path or graph.run_state_path, graph.slug)
    state = RetryState(retry_state_path or graph.retry_state_path, graph.slug,
                       run_id=run_state.run_id)
    return Run(graph=graph, parallelism=parallelism,
               retry_policy=retry_policy or RetryPolicy(), retry_state=state,
               run_state=run_state)


def launcher_from_registry(registry: AdapterRegistry, logger: RunLogger | None = None) -> Launcher:
    """Deriva un launcher dal registry, con un fallback singolo per il default.

    Il log appartiene al Run e non al grafo: descrive questa esecuzione senza
    introdurre uno stato persistente prima del nodo dedicato alla diagnostica.
    """
    def write_log(run: Run, entry: str) -> None:
        run.log.append(entry)
        if logger is not None:
            logger(entry)

    def select(run: Run, node: dict, identity: str, source: str) -> None:
        write_log(run, f"model-selected node={node['id']} model={identity} source={source}")
        _event(run, "provider-selected", node=node["id"], provider=identity, source=source)

    def fallback(run: Run, node: dict) -> object:
        write_log(
            run,
            f"model-fallback node={node['id']} from={DEFAULT_MODEL} "
            f"to={FALLBACK_MODEL} reason=provider-unavailable",
        )
        _event(run, "fallback", node=node["id"], provider=FALLBACK_MODEL,
               from_provider=DEFAULT_MODEL, reason="provider-unavailable")
        try:
            adapter = registry.get(FALLBACK_MODEL)
        except AdapterRegistryError as errore:
            write_log(
                run,
                f"model-fallback-rejected node={node['id']} model={FALLBACK_MODEL} "
                "reason=provider-unavailable",
            )
            raise AdapterRegistryError(
                f"node {node['id']} cannot use fallback model {FALLBACK_MODEL!r}: "
                "adapter is not configured"
            ) from errore
        select(run, node, FALLBACK_MODEL, "fallback")
        # Il lucchetto resta intestato al provider di default, che l'aveva preso
        # il runner prima di sapere del fallback. Riscriverlo qui vorrebbe dire
        # far toccare il grafo al launcher, che sceglie e lancia e basta: chi ha
        # lavorato davvero lo dicono l'evento fallback nel ledger e closedBy sul
        # nodo, scritto dall'agente che chiude.
        return adapter.launch(LaunchContext(run=run, node=node))

    def launch(run: Run, node: dict) -> object:
        defaulted = node.get("model") is None or node.get("model") == ""
        try:
            resolution = registry.resolve(node)
        except AdapterRegistryError as errore:
            if defaulted:
                select(run, node, DEFAULT_MODEL, "default")
                return fallback(run, node)
            write_log(run, f"model-rejected node={node['id']} detail={errore}")
            raise
        source = "default" if resolution.defaulted else "explicit"
        select(run, node, resolution.identity, source)
        try:
            handle = resolution.adapter.launch(LaunchContext(run=run, node=node))
        except ProviderUnavailableError:
            if not resolution.defaulted:
                raise
            return fallback(run, node)
        if not resolution.defaulted:
            return handle
        return _FallbackHandle(handle, lambda: fallback(run, node))

    def identity_for(node: dict) -> str | None:
        """L'identita' che l'agente avra', risolta senza lanciare niente.

        Il runner rivendica il nodo prima del lancio e deve scrivere nel lucchetto
        chi ci lavorera' davvero. Un nodo irrisolvibile non ha ancora un'identita'
        credibile: il claim resta quello del processo che lo prende, e il launch
        alzera' o passera' dal fallback come prima.
        """
        try:
            return registry.resolve(node).identity
        except AdapterRegistryError:
            return None

    launch.identity_for = identity_for
    return launch


class _FallbackHandle:
    """Osserva Luna e delega una sola volta al fallback se il provider manca."""

    def __init__(self, primary: object, fallback: Callable[[], object]) -> None:
        self._primary = primary
        self._fallback = fallback

    def wait(self) -> object:
        try:
            outcome = self._primary.wait()
        except ProviderUnavailableError:
            return self._fallback().wait()
        if _is_agent_outcome(outcome) and outcome.status == "provider-unavailable":
            return self._fallback().wait()
        return outcome


def parse_parallelism(value: str) -> int:
    """Converte il valore CLI e rifiuta ogni limite non intero o non positivo."""
    try:
        parallelism = int(value)
    except (TypeError, ValueError) as errore:
        raise argparse.ArgumentTypeError(t("autopilot.parallelism_invalid")) from errore
    if parallelism <= 0:
        raise argparse.ArgumentTypeError(t("autopilot.parallelism_invalid"))
    return parallelism


def execute(run: Run, launcher: Launcher, wait_for: Waiter | None = None,
            now: Callable[[], float] = time.time,
            sleeper: Callable[[float], None] = time.sleep,
            interaction_waiter: InteractionWaiter | None = None) -> RunResult:
    """Esegue il run e rende persistente anche ogni terminazione diagnostica."""
    data = load(run.graph.json_path)
    nuovo = run.run_state.start(run.parallelism, [node["id"] for node in frontier(data)], now())
    if not nuovo and run.run_state.data["status"] == "completed":
        return RunResult(())
    if not nuovo:
        _event(run, "run-resumed", status="active", reason="previous run state recovered",
               node=None, provider=None, attempt=None, failure=None, next_at=None)
    _frontier_event(run, data, now())
    fermo, tunnel = _avvia_tunnel_telegram(run)
    try:
        return _execute(run, launcher, wait_for, now, sleeper, interaction_waiter)
    except RunnerError as errore:
        # H05: una pausa su una persona non e' un fallimento del run, e non deve
        # leggersi come tale su dashboard e run-log. Stesso riconoscimento, gia'
        # fragile, con cui 'run bloccato' evita la stessa etichetta sbagliata.
        status = ("blocked" if "run bloccato" in str(errore)
                            or "in attesa di una persona" in str(errore) else "failed")
        _event(run, "run-blocked" if status == "blocked" else "run-failed",
               status=status, reason=str(errore))
        raise
    finally:
        _ferma_tunnel_telegram(fermo, tunnel)


def _avvia_tunnel_telegram(run: Run) -> tuple[threading.Event | None, threading.Thread | None]:
    """Apre il tunnel D03 per questa sessione (D06) se il relay e la chiave
    delle capability (D01) sono entrambi configurati nell'ambiente;
    altrimenti il run procede come sempre, senza Telegram. La linea si apre
    sotto l'identita' di questa installazione (A05, SS4-bis), non sotto il
    grafo: 'carica_o_crea' la genera al primo utilizzo su questa macchina.
    Gira in un thread demone: non deve mai impedire al processo di uscire."""
    config = relay_client.configurazione(os.environ)
    chiave = capability.da_ambiente(os.environ)
    if config is None or chiave is None:
        return None, None
    installazione = relay_identity.carica_o_crea()
    fermo = threading.Event()
    on_event = _combina_on_event(
        telegram_actions.gestore(run.graph, run.run_state.run_id, chiave, config),
        telegram_status.gestore(run.graph, installazione.installation_id, config),
        telegram_view.gestore(run.graph, installazione.installation_id, config),
    )
    thread = threading.Thread(
        target=relay_client.esegui,
        args=(config, installazione.installation_id, on_event, fermo),
        daemon=True,
    )
    thread.start()
    return fermo, thread


def _combina_on_event(*gestori: relay_client.OnEvent) -> relay_client.OnEvent:
    """Un solo on_event per il tunnel D03, che prova ogni gestore iniettato:
    telegram_actions risolve un tap (evento 'callback'), telegram_status
    risponde ai tre comandi di stato (evento 'message', D01), telegram_view
    risponde a '/view' con una foto o la pagina alleggerita (evento
    'message', D02). Ognuno ignora da solo cio' che non e' il proprio tipo o
    testo, quindi comporli qui non duplica nessuna decisione: e' lo stesso
    principio di 'admin_decision' nel relay, un solo slot che prova piu'
    confini in sequenza."""
    def _on_event(evento: Mapping[str, object]) -> None:
        for gestore in gestori:
            gestore(evento)
    return _on_event


def _ferma_tunnel_telegram(fermo: threading.Event | None, thread: threading.Thread | None) -> None:
    if fermo is None:
        return
    fermo.set()
    thread.join(timeout=5.0)


def _execute(run: Run, launcher: Launcher, wait_for: Waiter | None = None,
             now: Callable[[], float] = time.time,
             sleeper: Callable[[float], None] = time.sleep,
             interaction_waiter: InteractionWaiter | None = None) -> RunResult:
    """Esegue il run con retry persistenti senza uscire dalla frontiera Atlas."""
    terminali: list[str] = []
    attivi: list[tuple[str, object, int]] = []
    eventi_visti: set[str] = set()
    _riconcilia_retry(run, now())
    while True:
        data = load(run.graph.json_path)
        while len(attivi) < run.parallelism:
            candidati = [n for n in frontier(data)
                         if not run.retry_state.terminal(n["id"])
                         and run.retry_state.due(n["id"], now())]
            if not candidati:
                break
            candidato = candidati[0]
            if candidato["mode"] != "AFK" or candidato["type"] == "gate":
                event = "gate-required" if candidato["type"] == "gate" else "decision-required"
                _attendi_interazione(run, candidato, event, interaction_waiter, now())
                raise RunnerError(t("autopilot.hitl", id=candidato["id"]))
            if candidato["id"] in run._started and not run.retry_state.pending(candidato["id"]):
                raise RunnerError(t("autopilot.already_started", id=candidato["id"]))

            previsto = _identita_prevista(launcher, candidato)
            nodo = claims.claim(run.graph, candidato["id"], assignee=previsto,
                                on_behalf_of=previsto)
            run._started.add(nodo["id"])
            _event(run, "node-claimed", node=nodo["id"], status="active")
            # La dashboard si rigenera alla chiusura di un nodo, cioe' quando il
            # successivo non e' ancora rivendicato: senza questa riga il nodo in
            # lavorazione non compare mai come tale, e chi guarda vede il run
            # fermo sulla frontiera mentre un agente ci sta lavorando sopra.
            render.write(run.graph, load(run.graph.json_path))
            tentativo = run.retry_state.begin(nodo["id"], now())
            _event(run, "attempt-started", node=nodo["id"], attempt=tentativo,
                   status="active", reason=None, failure=None, next_at=None)
            try:
                handle = launcher(run, nodo)
            except Exception as errore:
                _gestisci_fallimento(run, nodo["id"], tentativo, errore, now())
                data = load(run.graph.json_path)
                continue
            attivi.append((nodo["id"], handle, tentativo))
            data = load(run.graph.json_path)

        if attivi:
            node_id, handle, tentativo = attivi.pop(0)
            _event(run, "attempt-waiting", node=node_id, attempt=tentativo,
                   status="waiting")
            try:
                osservazione = _raw_wait(handle, wait_for)
            except Exception as errore:
                osservazione = errore
            if _e_notifica(osservazione):
                _nuovi_eventi(_eventi_da_attesa(osservazione), eventi_visti)

            # Atlas si consulta prima dell'esito del processo, in entrambi i versi:
            # un exit status zero non chiude niente da solo (il guardrail di B04),
            # e un'uscita storta non cancella una chiusura che il grafo ha gia'
            # registrato. Il lavoro fatto non si butta per come e' morto il figlio.
            with read_transaction(run.graph.json_path) as data:
                osservato = node_of(data, node_id)
            if not is_done(osservato):
                if interactions.has_open(data, node_id, "human-needed"):
                    # H01/3, H05: l'agente ha dichiarato che la decisione non gli
                    # spetta, non che ha fallito. claims.ask_human ha gia' rilasciato
                    # il lucchetto: qui si chiude solo il tentativo, senza spendere
                    # budget retry ne' scrivere un guasto che non c'e' stato.
                    run.retry_state.complete(node_id)
                    _event(run, "node-waiting-human", node=node_id, attempt=tentativo,
                           status="active", reason="human-needed interaction open")
                    continue
                # Il nodo indeciso e' un guasto del nodo, non del run: passa dal
                # budget retry, che rilascia il lucchetto prima di riprovare, e il
                # resto della frontiera continua ad avanzare.
                _gestisci_fallimento(run, node_id, tentativo,
                                     _guasto(run, node_id, osservato, osservazione, data), now())
                continue
            run.retry_state.complete(node_id)
            _event(run, "node-closed", node=node_id, attempt=tentativo, status="active")
            _frontier_event(run, load(run.graph.json_path), now())
            if node_id not in terminali:
                terminali.append(node_id)
            continue

        # Un backoff pendente non giustifica un'attesa se il grafo e' gia' finito:
        # il ledger dei tentativi conserva il nodo che ha fallito, e se nel
        # frattempo quel nodo lo chiude qualcun altro (una sessione umana, un
        # recupero a mano) il risveglio non troverebbe piu' niente da fare. Senza
        # questa guardia il run resta vivo a ciclare su un orario passato, con il
        # grafo completo e nessuno che se ne accorge.
        if (prossimo := run.retry_state.next_at()) and not all(is_done(n) for n in data["nodes"]):
            _event(run, "backoff-waiting", status="waiting", next_at=prossimo,
                   reason="retry backoff")
            sleeper(max(0.0, prossimo - now()))
            continue
        if presi := claimed(data):
            _event(run, "active-claims", status="waiting",
                   reason=f"active claims: {', '.join(n['id'] for n in presi)}")
            raise RunnerError(t("autopilot.active_claims", ids=", ".join(n["id"] for n in presi)))
        if falliti := [node_id for node_id in run.retry_state.records()
                       if run.retry_state.terminal(node_id)]:
            _attendi_interazione(run, node_of(data, falliti[0]), "run-stopped",
                                 interaction_waiter, now(), ", ".join(falliti))
            raise RunnerError(t("autopilot.retry_exhausted", ids=", ".join(falliti),
                                path=run.graph.retry_state_path))
        if aperti := blocked(data):
            _frontier_event(run, data, now(), status="blocked",
                            reason=f"residual blockers: {', '.join(n['id'] for n in aperti)}")
            _attendi_interazione(run, aperti[0], "run-stopped", interaction_waiter, now(),
                                 ", ".join(n["id"] for n in aperti))
            raise RunnerError(t("autopilot.blocked", ids=", ".join(n["id"] for n in aperti)))
        if in_attesa := waiting_human(data):
            # H01/3, H05: non e' un guasto ne' un arco non chiuso, e la card che lo
            # spiega esiste gia' (claims.ask_human l'ha aperta quando l'ha
            # dichiarato): il run si ferma qui senza aprirne una seconda e senza
            # cadere nel verdetto generico sotto, che descriverebbe un'attesa
            # legittima come uno stato invalido.
            raise RunnerError(t("autopilot.waiting_human",
                                ids=", ".join(n["id"] for n in in_attesa)))
        if not all(is_done(n) for n in data["nodes"]):
            raise RunnerError(t("autopilot.invalid_termination"))
        _frontier_event(run, data, now())
        if any(node["id"] == "END" for node in data["nodes"]):
            _apri_interazione(run, node_of(data, "END"), "run-ended", now())
        _event(run, "run-completed", status="completed", reason="valid termination",
               node=None, provider=None, attempt=None, failure=None, next_at=None)
        return RunResult(tuple(terminali))


# Quanto resta aperta una card, secondo cosa chiede a chi la legge. La finestra
# lunga (SCADENZA_DECISIONE) vive in interactions.py: da H05 anche claims.ask_human
# ne apre una con la stessa attesa, e un valore solo evita due copie da tenere
# allineate a mano.
SCADENZA_GUASTO = timedelta(minutes=15)
SCADENZA_DECISIONE = interactions.SCADENZA_DECISIONE


def _scadenza(timestamp: float, event: str) -> str:
    """La finestra di una card dipende da cosa chiede.

    Una decisione umana puo' aspettare la giornata di chi deve prenderla. Un
    avviso di guasto no: il run e' gia' finito e la card dice solo cosa e'
    successo, quindi un run notturno che nessuno sta guardando deve poter chiudere
    in fretta invece di tenere occupato un terminale fino al giorno dopo. Finche'
    il canale che avvisa una persona non esiste, la finestra lunga e' tempo in cui
    non succede niente.
    """
    durata = SCADENZA_GUASTO if event == "run-stopped" else SCADENZA_DECISIONE
    return (datetime.fromtimestamp(timestamp).astimezone().replace(microsecond=0)
            + durata).isoformat()


def _card(event: str, node: dict, detail: str | None = None) -> tuple[str, list[dict]]:
    """Il testo e le azioni sono nella lingua del progetto (grilling 34 di
    docs/atlas-relay-design.md), letta da t(): stessa lingua di pannello e
    ticket, coerente con cio' che poi il canale Telegram (B01) mostra."""
    if event == "run-ended":
        return (t("autopilot.card_run_ended", title=node["title"]),
                [{"id": "acknowledge", "label": t("autopilot.action_acknowledge"), "effect": "acknowledged"}])
    if event == "run-stopped":
        return (t("autopilot.card_run_stopped", detail=detail or node["id"]), [
            {"id": "retry", "label": t("autopilot.action_retry"), "effect": "retry"},
            {"id": "cancel", "label": t("autopilot.action_cancel"), "effect": "cancel"},
        ])
    return (t("autopilot.card_decision_required", node=node["id"]), [
        {"id": "confirm", "label": t("autopilot.action_confirm"), "effect": "resume"},
        {"id": "decline", "label": t("autopilot.action_decline"), "effect": "cancel"},
    ])


def _apri_interazione(run: Run, node: dict, event: str, timestamp: float,
                      detail: str | None = None) -> dict:
    """Scrive la card nella stessa sorgente di verita' che svegliera' il run."""
    summary, actions = _card(event, node, detail)
    with mutate.editing(run.graph) as graph:
        return interactions.open_interaction(
            graph, run_id=run.run_state.run_id, node_id=node["id"], event=event,
            summary=summary, allowed_actions=actions, expires_at=_scadenza(timestamp, event),
            idempotency_key=f"{run.run_state.run_id}:{node['id']}:{event}")


def _attendi_interazione(run: Run, node: dict, event: str,
                         waiter: InteractionWaiter | None, timestamp: float,
                         detail: str | None = None) -> dict:
    """Sospende il solo runner finche' Atlas conferma una risposta, o la card scade.

    L'evento in-process e' la via veloce, ma non l'unica possibile: la coda vive
    in memoria di questo processo, quindi una risposta data dalla dashboard o da
    un altro comando non la pubblicherebbe nessuno qui. Perche' un run AFK non
    resti appeso per sempre su una domanda che nessuno vede, l'attesa torna a
    guardare il grafo a intervalli e si arrende alla scadenza dichiarata nella
    card, che il modello prevede fin dalla sua apertura.
    """
    card = _apri_interazione(run, node, event, timestamp, detail)
    _event(run, "interaction-opened", status="waiting", node=node["id"],
           reason=event, interaction=card["id"])
    wait = waiter or interactions.wait_for_resolution
    while True:
        ricevuto = wait(run.graph.slug, run.run_state.run_id, RILETTURA_INTERAZIONE)
        if ricevuto is not None and ricevuto.interaction_id != card["id"]:
            continue                       # un'altra card: non e' la nostra risposta
        record = _card_corrente(run, card["id"])
        if record["status"] != "open":
            break
        if interactions.is_expired(record):
            record = _scadi_interazione(run, card["id"])
            break
    if record["status"] == "resolved":
        _event(run, "interaction-resolved", status="active", node=node["id"],
               reason=record["resolution"]["effect"], interaction=card["id"])
    else:
        _event(run, "interaction-closed", status="active", node=node["id"],
               reason=record["status"], interaction=card["id"])
    return record


def _card_corrente(run: Run, interaction_id: str) -> dict:
    """Lo stato della card secondo il grafo, non secondo la coda degli eventi."""
    with read_transaction(run.graph.json_path) as data:
        return next(item for item in data["interactions"] if item["id"] == interaction_id)


def _scadi_interazione(run: Run, interaction_id: str) -> dict:
    """Chiude la card che nessuno ha raccolto entro la sua scadenza."""
    with mutate.editing(run.graph) as graph:
        interactions.expire_interactions(graph)
    return _card_corrente(run, interaction_id)


def _raw_wait(handle: object, wait_for: Waiter | None) -> object:
    """Attende una volta lasciando all'integrazione la classificazione dell'esito."""
    if wait_for is not None:
        return wait_for(handle)
    attesa = getattr(handle, "wait", None)
    return attesa() if callable(attesa) else None


def _is_agent_outcome(value: object) -> bool:
    """Riconosce un outcome anche dopo un reload del modulo in un processo host."""
    return isinstance(value, AgentOutcome) or (
        value.__class__.__name__ == "AgentOutcome"
        and hasattr(value, "status")
        and hasattr(value, "detail")
    )


def _eventi_da_attesa(osservazione: object) -> tuple[ClosureEvent, ...]:
    if isinstance(osservazione, ClosureEvent):
        return (osservazione,)
    return tuple(osservazione)


def _gestisci_fallimento(run: Run, node_id: str, tentativo: int, valore: object,
                         timestamp: float) -> None:
    failure = classify_failure(valore) or "ambiguous-termination"
    # Un tentativo puo' fallire dopo che il lavoro e' stato fatto e scritto: basta
    # che l'agente muoia fra l'ultima riga del ticket e la chiusura del nodo, e in
    # questo repo lo fa anche un hook di fine sessione che va storto. Rilanciarlo
    # come un crash o un'ambiguita' qualunque rifa' da capo un lavoro che c'e' gia':
    # e' successo per cinque tentativi di fila sullo stesso nodo (run del
    # 2026-09-03). Qui il dubbio non c'e': la risposta e' leggibile, quindi non e'
    # piu' un guasto da cui si puo' sperare un esito diverso al tentativo dopo, e
    # diventa terminale al primo colpo come una resa, ma distinguibile da essa nel
    # ledger perche' non e' stata una scelta dell'agente.
    ha_gia_risposto = docs.answer_written(run.graph, node_id)
    if ha_gia_risposto and failure in RETRYABLE_FAILURES:
        failure = "orphaned-answer"
    delay = (run.retry_policy.delay_for(tentativo)
             if failure in RETRYABLE_FAILURES and run.retry_policy.can_retry(tentativo, failure)
             else None)
    dettaglio = getattr(valore, "detail", None) or str(valore) or None
    run.retry_state.record_failure(node_id, tentativo, failure, dettaglio, timestamp, delay)
    run.log.append(f"retry-classified node={node_id} class={failure} attempt={tentativo}")
    _event(run, "attempt-failed", node=node_id, attempt=tentativo, failure=failure,
           reason=dettaglio, status="active")
    if ha_gia_risposto:
        _event(run, "work-not-lost", node=node_id, attempt=tentativo, failure=failure,
               status="active",
               reason="ticket answer already written: recover it instead of redoing the work")
    _rilascia_se_tenuto(run, node_id)
    if delay is None:
        # Il budget del nodo e' finito, non quello del run: fermare qui l'intero
        # ciclo abbandonava rami interi che non dipendevano da questo nodo. Il
        # nodo resta terminale nel ledger dei retry, quindi non verra' ripreso, e
        # il verdetto finale lo pronuncia il ciclo quando non c'e' piu' altro da
        # fare, nominando tutti i nodi esauriti invece del primo.
        run.log.append(f"retry-exhausted node={node_id} class={failure}")
        _event(run, "node-exhausted", node=node_id, attempt=tentativo, failure=failure,
               reason=dettaglio, status="active")
        return
    run.log.append(f"retry-scheduled node={node_id} attempt={tentativo} delay={delay:g}")
    _event(run, "backoff-scheduled", node=node_id, attempt=tentativo,
           failure=failure, next_at=timestamp + delay, status="waiting")


def _e_notifica(osservazione: object) -> bool:
    """Vero per le sole ClosureEvent: un esito o un'eccezione non sono notifiche."""
    return (osservazione is not None and not _is_agent_outcome(osservazione)
            and not isinstance(osservazione, BaseException))


def _guasto(run: Run, node_id: str, osservato: dict, osservazione: object, data: dict) -> object:
    """Il valore da classificare quando Atlas non mostra il nodo terminale.

    La resa (H01/2, H04) si controlla per prima: e' un esito che l'agente ha gia'
    dichiarato scrivendo in data['surrenders'], non una diagnosi da dedurre
    dall'output del processo, e senza questa precedenza rientrava fra i guasti
    testuali e finiva classificata 'ambiguous-termination'. Un esito che parla
    gia' da se' (un'eccezione, un outcome che non e' 'closed') si classifica per
    quello che e'. Restano il successo dichiarato e la notifica senza chiusura:
    li' il processo e' finito bene e il lavoro non c'e', che e' una terminazione
    ambigua e non un guasto del run.
    """
    if (resa := _resa_recente(run, data, node_id)) is not None:
        return SurrenderedError(f"{resa['reason']}: {resa['detail']}")
    if isinstance(osservazione, BaseException) or (
            _is_agent_outcome(osservazione) and osservazione.status != "closed"):
        return osservazione
    return AmbiguousTerminationError(
        t("autopilot.not_terminal", id=node_id, status=osservato["status"])
        + _ultima_parola(osservazione))


def _resa_recente(run: Run, data: dict, node_id: str) -> dict | None:
    """L'ultima resa dichiarata per questo nodo dentro il tentativo in corso.

    Una resa di un run precedente, gia' esaurita e mai ripulita da data['surrenders']
    (e' un ledger append-only, H01), non deve rientrare su un nuovo tentativo dello
    stesso nodo: si guarda solo cio' che e' arrivato dopo l'inizio di QUESTO
    tentativo, lo stesso istante che retry_state gia' registra in 'started_at'.
    """
    record = run.retry_state.record(node_id)
    # started_at ha precisione al microsecondo (time.time()), l'ISO di una resa solo
    # al secondo (timespec='seconds', come ogni timestamp del grafo): confrontarli
    # senza troncare fa apparire 'prima dell'inizio' una resa arrivata un istante
    # dopo begin() ma dentro lo stesso secondo di orologio.
    inizio = float(int(record["started_at"])) if record else 0.0
    for resa in reversed(data.get("surrenders", [])):
        if resa["node"] != node_id:
            continue
        quando = istante(resa["at"])
        if quando is not None and quando.timestamp() >= inizio:
            return resa
    return None


def _rilascia_se_tenuto(run: Run, node_id: str) -> None:
    """Molla il lucchetto solo se c'e' ancora da mollare.

    Un agente puo' aver rilasciato il nodo da solo prima di uscire, e release alza
    su un nodo non rivendicato: quell'eccezione uscirebbe dal ciclo come un guasto
    del run mentre descrive esattamente lo stato che ci serve. Gli altri errori di
    release, come una ref remota che non si libera, restano errori.
    """
    if node_of(load(run.graph.json_path), node_id)["status"] == CLAIMED:
        claims.release(run.graph, node_id)


def _identita_prevista(launcher: Launcher, node: dict) -> str | None:
    """L'identita' che l'agente avra' quando partira', se il launcher sa dirla.

    Il lucchetto si prende prima del lancio: senza questa domanda il claim
    porterebbe l'identita' del runner, e il figlio troverebbe il proprio nodo
    tenuto da uno sconosciuto. Un launcher che non la espone (un'integrazione
    custom, i test) resta valido e il claim torna a essere quello di chi lo prende.
    """
    dichiara = getattr(launcher, "identity_for", None)
    return dichiara(node) if callable(dichiara) else None


def _ultima_parola(osservazione: object, limite: int = 400) -> str:
    """La coda di cio' che l'agente ha detto, per far diagnosticare dal ledger.

    Senza, il motivo per cui un nodo non si e' chiuso resta solo nei log del
    provider, che il ledger non sa nemmeno dove siano: e' la differenza fra
    leggere 'ha chiesto un'autorizzazione' e dover ricostruire un run a mano.
    """
    detail = getattr(osservazione, "detail", None)
    if not detail:
        return ""
    testo = " ".join(str(detail).split())
    return ": " + (testo if len(testo) <= limite else "..." + testo[-limite:])


def _riconcilia_retry(run: Run, timestamp: float) -> None:
    """Riconcilia claim e tentativi senza rilanciare un agente ancora vivo."""
    data = load(run.graph.json_path)
    agent = run.graph.workspace.config["agent"]
    for node in claimed(data):
        record = run.retry_state.record(node["id"])
        stato = claims.claim_state(node, agent)
        if stato == "live":
            _event(run, "claim-live", node=node["id"], status="waiting",
                   reason="existing agent is still alive")
            raise RunnerError(t("autopilot.retry_active", id=node["id"]))
        claims.release(run.graph, node["id"])
        _event(run, "claim-reconciled", node=node["id"], status="active",
               reason=f"stale claim: {stato}")
        if record is None:
            attempt = run.retry_state.begin(node["id"], timestamp)
            _record_reconciled_crash(run, node["id"], attempt, timestamp)
        elif record.get("status") == "active":
            _record_reconciled_crash(run, node["id"], int(record["attempt"]), timestamp)

    for node_id, record in run.retry_state.records().items():
        if record.get("status") not in ("active", "pending"):
            continue
        data = load(run.graph.json_path)
        node = node_of(data, node_id)
        if is_done(node):
            run.retry_state.complete(node_id)
            _event(run, "node-reconciled-closed", node=node_id,
                   attempt=record.get("attempt"), status="active",
                   reason="Atlas closed node while runner was stopped")
            continue
        if record.get("status") == "active":
            tentativo = int(record["attempt"])
            _record_reconciled_crash(run, node_id, tentativo, timestamp)


def _record_reconciled_crash(run: Run, node_id: str, attempt: int,
                             timestamp: float) -> None:
    """Registra una perdita di processo e conserva il budget retry."""
    delay = (run.retry_policy.delay_for(attempt)
             if run.retry_policy.can_retry(attempt, "crash") else None)
    run.retry_state.record_failure(node_id, attempt, "crash",
                                   "previous run stopped during attempt",
                                   timestamp, delay)
    _event(run, "attempt-reconciled", node=node_id, attempt=attempt,
           failure="crash", status="waiting" if delay is not None else "failed")


def _event(run: Run, event_type: str, **fields: object) -> None:
    """Scrive nel ledger solo dopo l'avvio effettivo del run."""
    if not run.run_state.started:
        return
    timestamp = fields.pop("at", time.time())
    run.run_state.event(event_type, timestamp, **fields)


def _frontier_event(run: Run, data: dict, timestamp: float, status=None, reason=None) -> None:
    blockers = [{"node": node["id"],
                 "blocked_by": [dependency for dependency in node["blockedBy"]
                                if not is_done(node_of(data, dependency))]}
                for node in blocked(data)]
    _event(run, "frontier-updated", at=timestamp, status=status, reason=reason,
           frontier=[node["id"] for node in frontier(data)], blockers=blockers)


def _wait(handle: object, wait_for: Waiter | None, node_id: str) -> tuple[ClosureEvent, ...]:
    """Attende il lavoro e normalizza le notifiche senza conoscere il provider."""
    if wait_for is not None:
        evento = wait_for(handle)
    else:
        attesa = getattr(handle, "wait", None)
        evento = attesa() if callable(attesa) else None
    if _is_agent_outcome(evento):
        if evento.status == "closed":
            return (ClosureEvent(node_id),)
        dettaglio = evento.detail or "nessun dettaglio"
        raise RunnerError(t("autopilot.adapter_outcome", id=node_id,
                            status=evento.status, detail=dettaglio))
    if evento is None:
        return ()
    if isinstance(evento, ClosureEvent):
        return (evento,)
    return tuple(evento)


def _nuovi_eventi(eventi: tuple[ClosureEvent, ...], visti: set[str]) -> tuple[ClosureEvent, ...]:
    """Scarta duplicati e ritardi senza usarli per autorizzare un avvio."""
    nuovi = tuple(evento for evento in eventi if evento.node_id not in visti)
    visti.update(evento.node_id for evento in nuovi)
    return nuovi
