"""Confine provider-agnostic fra Automata e un processo agente.

Il registry contiene gli adapter gia' configurati e risolve l'identita' richiesta.
La politica del contesto rende esplicito il contratto AFK del provider; il
provider resta responsabile di realizzarlo.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    from .automata import Run


CODEX_LUNA = "codex-luna"
CLAUDE = "claude"
GEMINI = "gemini"
CODE_TERRA = "code-terra"
DEFAULT_MODEL = CODEX_LUNA
FALLBACK_MODEL = CLAUDE

IDENTITIES = {
    CODEX_LUNA: "Codex Luna",
    CLAUDE: "Claude Sonnet",
    GEMINI: "Gemini",
    CODE_TERRA: "Code Terra",
}

OutcomeStatus = Literal[
    "closed", "error", "ambiguous", "provider-unavailable", "timeout", "crash",
    "rate-limit", "permanent-error",
]


class ProviderUnavailableError(RuntimeError):
    """Il provider non puo' accettare o proseguire il lavoro richiesto."""


@dataclass(frozen=True)
class AgentOutcome:
    """Esito osservabile della terminazione di un agente."""

    status: OutcomeStatus
    detail: str | None = None

    def __post_init__(self) -> None:
        if self.status not in ("closed", "error", "ambiguous", "provider-unavailable",
                               "timeout", "crash", "rate-limit", "permanent-error"):
            raise ValueError(f"unknown agent outcome: {self.status}")


@dataclass(frozen=True)
class LaunchPolicy:
    """Vincoli comuni a ogni processo lanciato da Automata."""

    afk: bool = True
    sandbox: bool = False
    bypass_permissions: bool = True

    def __post_init__(self) -> None:
        if (type(self.afk) is not bool or type(self.sandbox) is not bool
                or type(self.bypass_permissions) is not bool
                or not self.afk or self.sandbox or not self.bypass_permissions):
            raise ValueError("Automata adapters must run AFK outside the sandbox with bypass permissions")


@dataclass(frozen=True)
class LaunchContext:
    """Dati che un adapter riceve per un singolo nodo e run."""

    run: "Run"
    node: Mapping[str, object]
    policy: LaunchPolicy = field(default_factory=LaunchPolicy)


@runtime_checkable
class AgentHandle(Protocol):
    """Handle opaco che osserva la terminazione del processo agente."""

    def wait(self) -> AgentOutcome: ...


@runtime_checkable
class AgentAdapter(Protocol):
    """Adapter provider-specifico consumato dal registry, non dal runner."""

    identity: str

    def launch(self, context: LaunchContext) -> AgentHandle: ...


class AdapterRegistryError(ValueError):
    """Configurazione del registry non valida o identita' non disponibile."""


@dataclass(frozen=True)
class ModelResolution:
    """Identita' e adapter scelti per un nodo, senza cambiare il nodo."""

    identity: str
    adapter: AgentAdapter
    requested: str | None
    defaulted: bool


class AdapterRegistry:
    """Registro in memoria di adapter scelti esplicitamente dall'esecuzione."""

    def __init__(self, adapters: Iterable[AgentAdapter] = ()) -> None:
        self._adapters: dict[str, AgentAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: AgentAdapter) -> None:
        """Registra un adapter sotto la propria identita', una sola volta."""
        identity = adapter.identity
        if not isinstance(identity, str) or not identity or identity != identity.strip():
            raise AdapterRegistryError("adapter identity must be non-empty")
        if identity in self._adapters:
            raise AdapterRegistryError(f"adapter identity already registered: {identity}")
        self._adapters[identity] = adapter

    def get(self, identity: str) -> AgentAdapter:
        """Restituisce solo l'adapter esplicitamente configurato."""
        try:
            return self._adapters[identity]
        except KeyError:
            raise AdapterRegistryError(f"adapter identity is not configured: {identity}") from None

    def resolve(self, node: Mapping[str, object]) -> ModelResolution:
        """Risolvi il modello del nodo verso un adapter gia' registrato.

        L'assenza della chiave e la stringa vuota sono l'unico default implicito.
        Un modello esplicito resta un'identita' esatta: accettare alias qui
        renderebbe la selezione meno deterministica e nasconderebbe errori di
        configurazione nel grafo.
        """
        requested = node.get("model")
        node_id = node.get("id", "?")
        defaulted = requested is None or requested == ""
        if defaulted:
            identity = DEFAULT_MODEL
        elif not isinstance(requested, str) or not requested.strip():
            raise AdapterRegistryError(
                f"node {node_id} has invalid model {requested!r}: expected a non-empty registry identity")
        else:
            identity = requested

        try:
            adapter = self.get(identity)
        except AdapterRegistryError as errore:
            configured = ", ".join(self.identities()) or "(none)"
            if defaulted:
                raise AdapterRegistryError(
                    f"node {node_id} uses default model {identity!r} (Codex Luna), "
                    f"but no adapter is configured; configured identities: {configured}") from errore
            raise AdapterRegistryError(
                f"node {node_id} requests unknown model {identity!r}; "
                f"configured identities: {configured}") from errore
        return ModelResolution(identity, adapter, requested if isinstance(requested, str) else None, defaulted)

    def identities(self) -> tuple[str, ...]:
        """Identita' configurate, in ordine stabile."""
        return tuple(sorted(self._adapters))

    def launcher(self, identity: str) -> Callable[["Run", Mapping[str, object]], AgentHandle]:
        """Crea il launcher generico che Automata puo' usare per un'identita' scelta."""
        adapter = self.get(identity)

        def launch(run: "Run", node: Mapping[str, object]) -> AgentHandle:
            return adapter.launch(LaunchContext(run=run, node=node))

        return launch
