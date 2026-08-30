"""Entry point e ciclo bounded per una singola esecuzione di Automata."""
from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from . import claims
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
from .model import blocked, claimed, frontier, is_done, node_of
from .retry import RETRYABLE_FAILURES, RetryPolicy, RetryState, classify_failure
from .run_state import RunState
from .store import StateError, load, read_transaction
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
                sleeper: Callable[[float], None] = time.sleep) -> RunResult:
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
        return execute(self, launcher, wait_for, now, sleeper)


def start(graph: Graph, parallelism: object, retry_policy: RetryPolicy | None = None,
          retry_state_path=None, run_state_path=None) -> Run:
    """Crea un run dopo aver validato il limite richiesto dall'utente."""
    if type(parallelism) is not int or parallelism <= 0:
        raise ValueError(t("automata.parallelism_invalid"))
    state = RetryState(retry_state_path or graph.retry_state_path, graph.slug)
    run_state = RunState(run_state_path or graph.run_state_path, graph.slug)
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
        raise argparse.ArgumentTypeError(t("automata.parallelism_invalid")) from errore
    if parallelism <= 0:
        raise argparse.ArgumentTypeError(t("automata.parallelism_invalid"))
    return parallelism


def execute(run: Run, launcher: Launcher, wait_for: Waiter | None = None,
            now: Callable[[], float] = time.time,
            sleeper: Callable[[float], None] = time.sleep) -> RunResult:
    """Esegue il run e rende persistente anche ogni terminazione diagnostica."""
    data = load(run.graph.json_path)
    nuovo = run.run_state.start(run.parallelism, [node["id"] for node in frontier(data)], now())
    if not nuovo and run.run_state.data["status"] == "completed":
        return RunResult(())
    if not nuovo:
        _event(run, "run-resumed", status="active", reason="previous run state recovered",
               node=None, provider=None, attempt=None, failure=None, next_at=None)
    _frontier_event(run, data, now())
    try:
        return _execute(run, launcher, wait_for, now, sleeper)
    except RunnerError as errore:
        status = "blocked" if "run bloccato" in str(errore) else "failed"
        _event(run, "run-blocked" if status == "blocked" else "run-failed",
               status=status, reason=str(errore))
        raise


def _execute(run: Run, launcher: Launcher, wait_for: Waiter | None = None,
             now: Callable[[], float] = time.time,
             sleeper: Callable[[float], None] = time.sleep) -> RunResult:
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
            if candidato["mode"] != "AFK":
                raise RunnerError(t("automata.hitl", id=candidato["id"]))
            if candidato["id"] in run._started and not run.retry_state.pending(candidato["id"]):
                raise RunnerError(t("automata.already_started", id=candidato["id"]))

            nodo = claims.claim(run.graph, candidato["id"])
            run._started.add(nodo["id"])
            _event(run, "node-claimed", node=nodo["id"], status="active")
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
                _gestisci_fallimento(run, node_id, tentativo, errore, now())
                continue
            failure = (classify_failure(osservazione)
                       if _is_agent_outcome(osservazione) or isinstance(osservazione, BaseException)
                       else None)
            if failure is not None:
                _gestisci_fallimento(run, node_id, tentativo, osservazione, now())
                continue
            if osservazione is not None and not _is_agent_outcome(osservazione):
                _nuovi_eventi(_eventi_da_attesa(osservazione), eventi_visti)

            with read_transaction(run.graph.json_path) as data:
                osservato = node_of(data, node_id)
            if not is_done(osservato):
                # Una ClosureEvent non e' un esito dell'adapter: senza una
                # chiusura Atlas resta il guardrail di B04, non un'autorizzazione
                # implicita a rilanciare il lavoro.
                raise RunnerError(t("automata.not_terminal", id=node_id,
                                     status=osservato["status"]))
            run.retry_state.complete(node_id)
            _event(run, "node-closed", node=node_id, attempt=tentativo, status="active")
            _frontier_event(run, load(run.graph.json_path), now())
            if node_id not in terminali:
                terminali.append(node_id)
            continue

        if prossimo := run.retry_state.next_at():
            _event(run, "backoff-waiting", status="waiting", next_at=prossimo,
                   reason="retry backoff")
            sleeper(max(0.0, prossimo - now()))
            continue
        if presi := claimed(data):
            _event(run, "active-claims", status="waiting",
                   reason=f"active claims: {', '.join(n['id'] for n in presi)}")
            raise RunnerError(t("automata.active_claims", ids=", ".join(n["id"] for n in presi)))
        if falliti := [node_id for node_id in run.retry_state.records()
                       if run.retry_state.terminal(node_id)]:
            raise RunnerError(t("automata.retry_exhausted", ids=", ".join(falliti)))
        if aperti := blocked(data):
            _frontier_event(run, data, now(), status="blocked",
                            reason=f"residual blockers: {', '.join(n['id'] for n in aperti)}")
            raise RunnerError(t("automata.blocked", ids=", ".join(n["id"] for n in aperti)))
        if not all(is_done(n) for n in data["nodes"]):
            raise RunnerError(t("automata.invalid_termination"))
        _frontier_event(run, data, now())
        _event(run, "run-completed", status="completed", reason="valid termination",
               node=None, provider=None, attempt=None, failure=None, next_at=None)
        return RunResult(tuple(terminali))


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
    delay = (run.retry_policy.delay_for(tentativo)
             if failure in RETRYABLE_FAILURES and run.retry_policy.can_retry(tentativo)
             else None)
    dettaglio = getattr(valore, "detail", None) or str(valore) or None
    run.retry_state.record_failure(node_id, tentativo, failure, dettaglio, timestamp, delay)
    run.log.append(f"retry-classified node={node_id} class={failure} attempt={tentativo}")
    _event(run, "attempt-failed", node=node_id, attempt=tentativo, failure=failure,
           reason=dettaglio, status="active" if delay is not None else "failed")
    claims.release(run.graph, node_id)
    if delay is None:
        raise RunnerError(t("automata.retry_exhausted", ids=node_id))
    run.log.append(f"retry-scheduled node={node_id} attempt={tentativo} delay={delay:g}")
    _event(run, "backoff-scheduled", node=node_id, attempt=tentativo,
           failure=failure, next_at=timestamp + delay, status="waiting")


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
            raise RunnerError(t("automata.retry_active", id=node["id"]))
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
             if run.retry_policy.can_retry(attempt) else None)
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
        raise RunnerError(t("automata.adapter_outcome", id=node_id,
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
