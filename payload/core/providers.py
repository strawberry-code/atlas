"""Processi figli concreti che rispettano il contratto AFK di Autopilot."""
from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence

from . import claims
from .adapters import (AgentHandle, AgentOutcome, LaunchContext, LaunchPolicy,
                       ProviderUnavailableError, provider_indisponibile,
                       CODEX_LUNA, CLAUDE, CODE_TERRA, GEMINI)
from .config import Graph
from .model import node_of
from .store import load


PROMPT = "{prompt}"

# Tetto di durata di un singolo tentativo. Senza, il runner aspetta all'infinito
# che il figlio termini: un agente che resta vivo senza lavorare (una risposta che
# non arriva, un turno chiuso in attesa di una notifica che nessuno mandera') tiene
# il nodo rivendicato e ferma il run, e la sola diagnosi possibile e' che nessuno
# scrive piu' niente. Il numero viene dai tempi veri di un run completo: i nodi
# chiusi con successo stanno fra 5 e 49 minuti, quello appeso e' rimasto in piedi
# 442 minuti. Novanta minuti lasciano il doppio abbondante del massimo osservato e
# tagliano comunque il caso patologico. Superato il tetto il tentativo diventa un
# fallimento come gli altri, quindi passa dal budget dei retry e rilascia il nodo.
# Resta l'ultima difesa, per l'agente che non dichiara mai un passo (vedi sotto).
TIMEOUT_TENTATIVO_SECONDI = 90 * 60

# Ogni quanto l'attesa si interrompe per guardare l'avanzamento dichiarato (H01/4,
# claims.progress) invece di restare bloccata sul tetto assoluto in un colpo solo.
FETTA_ATTESA_SECONDI = 60

# Silenzio massimo tollerato da un agente che ha gia' dichiarato almeno un passo di
# avanzamento prima di essere considerato fermo e ucciso. I nodi legittimi del run
# del 2026-09-03 sono durati in tutto fra 5 e 49 minuti: un'ora lascia margine sopra
# il piu' lungo nodo osservato per un agente che pensa a lungo su un solo passo (un
# test lento durante 'verifying', per esempio), restando comunque un terzo sotto il
# tetto assoluto. Un agente che non ha mai chiamato 'atlas progress' non passa da
# questo controllo (claims.silent_for torna None): per lui resta solo il tetto
# assoluto, perche' senza un primo passo dichiarato il silenzio non si distingue da
# un lavoro lecito che non parla.
SILENZIO_AMMESSO_SECONDI = 60 * 60


class ProcessHandle:
    """Handle che drena l'output del figlio e traduce il suo exit status.

    L'attesa e' a fette (H03): ogni fetta finisce con lo stesso TimeoutExpired di
    prima, ma invece di rilanciare comunicate() con lo stesso timeout intero, la
    fetta successiva riparte da dove il tetto assoluto e' rimasto, e nel mezzo si
    guarda se il nodo ha smesso di dichiarare avanzamento. Chiamare comunicate()
    di nuovo dopo un TimeoutExpired e' supportato dalla stdlib apposta per questo:
    nessun byte di stdout/stderr va perso fra una fetta e l'altra.
    """

    def __init__(self, process: subprocess.Popen[str], echo: str | None = None,
                 timeout: float | None = TIMEOUT_TENTATIVO_SECONDI,
                 graph: Graph | None = None, node_id: str | None = None,
                 fetta: float = FETTA_ATTESA_SECONDI,
                 silenzio_ammesso: float = SILENZIO_AMMESSO_SECONDI) -> None:
        self._process = process
        self._echo = echo
        self._timeout = timeout
        self._graph = graph
        self._node_id = node_id
        self._fetta = fetta
        self._silenzio_ammesso = silenzio_ammesso

    def wait(self) -> AgentOutcome:
        trascorso = 0.0
        while True:
            fetta = self._prossima_fetta(trascorso)
            try:
                stdout, stderr = self._process.communicate(timeout=fetta)
                break
            except subprocess.TimeoutExpired:
                trascorso += fetta
                if self._timeout is not None and trascorso >= self._timeout:
                    return self._uccidi(
                        "crash", f"no termination within {self._timeout:.0f}s: killed by the runner")
                fermo = self._silenzio()
                if fermo is not None and fermo >= self._silenzio_ammesso:
                    return self._uccidi(
                        "timeout", f"no progress declared for {fermo:.0f}s: killed by the runner")
                continue
            except OSError as errore:
                return AgentOutcome("ambiguous", str(errore))
        detail = self._senza_eco((stderr or stdout or "").strip()) or None
        if self._process.returncode == 0:
            return AgentOutcome("closed", detail)
        if self._process.returncode is not None and self._process.returncode < 0:
            return AgentOutcome("crash", detail or f"signal {-self._process.returncode}")
        if provider_indisponibile(detail):
            # Il processo e' partito ed e' uscito male, ma non per il lavoro: la
            # quota e' finita o mancano le credenziali. E' l'unico exit status
            # storto che deve valere come provider assente, perche' e' quello che
            # fa scattare il fallback invece di otto rilanci identici.
            return AgentOutcome("provider-unavailable", detail)
        return AgentOutcome("error", detail or f"exit status {self._process.returncode}")

    def _prossima_fetta(self, trascorso: float) -> float | None:
        """La durata della prossima comunicate(): la fetta piena, o solo quanto
        resta al tetto assoluto se e' meno di una fetta intera."""
        if self._timeout is None:
            return self._fetta
        return max(0.0, min(self._fetta, self._timeout - trascorso))

    def _silenzio(self) -> float | None:
        """Da quanti secondi il nodo non dichiara un passo, o None se non lo si
        puo' sapere (nessun grafo da guardare, o claims.silent_for non lo sa dire):
        in entrambi i casi il tetto assoluto resta l'unica difesa. Una lettura del
        grafo che fallisce a meta' fetta non deve uccidere un lavoro legittimo per
        un guasto suo, quindi vale anch'essa come 'non lo so'."""
        if self._graph is None or self._node_id is None:
            return None
        try:
            fermo = claims.silent_for(node_of(load(self._graph.json_path), self._node_id))
        except Exception:
            return None
        return fermo.total_seconds() if fermo is not None else None

    def _uccidi(self, status: str, motivo: str) -> AgentOutcome:
        # Kill e non terminate, perche' un processo che non risponde nemmeno al
        # segnale gentile lascerebbe il nodo rivendicato un'altra volta.
        self._process.kill()
        self._process.communicate()
        return AgentOutcome(status, motivo)

    def _senza_eco(self, uscita: str) -> str:
        """Toglie dall'output l'eco del prompt che gli abbiamo dato noi.

        Un CLI agentico ristampa il briefing prima di lavorare, e il briefing
        contiene la domanda del nodo: lasciarcelo vuol dire cercare le firme di
        guasto dentro il ticket, e un nodo che parla di rate limit passerebbe per
        un provider a quota finita. L'eco lo riconosciamo esattamente, perche' e'
        la stringa che abbiamo passato in argv.
        """
        return uscita.replace(self._echo, " ") if self._echo else uscita


class SubprocessAdapter:
    """Lancia un provider con argv, ambiente e stdin non interattivi."""

    def __init__(self, identity: str, command: Sequence[str],
                 environment: Mapping[str, str] | None = None) -> None:
        if not isinstance(identity, str) or not identity or "\x00" in identity:
            raise ValueError("provider identity must be a non-empty string without NUL")
        if not isinstance(command, Sequence) or isinstance(command, (str, bytes)):
            raise TypeError("provider command must be a sequence of argv strings")
        if not command or any(not isinstance(arg, str) or not arg or "\x00" in arg for arg in command):
            raise ValueError("provider command must contain non-empty argv strings")
        if environment is not None and any(
                not isinstance(key, str) or not isinstance(value, str)
                or "\x00" in key or "\x00" in value
                for key, value in environment.items()):
            raise ValueError("provider environment must contain string values without NUL")
        self.identity = identity
        self.command = tuple(command)
        self.environment = dict(environment or {})

    def launch(self, context: LaunchContext) -> AgentHandle:
        _validate_policy(context.policy)
        argv = _render_argv(self.command, context)
        environment = _environment(self.identity, context, self.environment)
        try:
            process = subprocess.Popen(
                argv,
                cwd=context.run.graph.workspace.project_root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
                start_new_session=True,
            )
        except OSError as errore:
            raise ProviderUnavailableError(
                f"provider {self.identity!r} could not be started: {errore}"
            ) from errore
        return ProcessHandle(process, echo=_prompt(context),
                            graph=context.run.graph, node_id=str(context.node["id"]))


ProcessAdapter = SubprocessAdapter


def codex_adapter(executable: str = "codex") -> SubprocessAdapter:
    """Configura Codex in exec mode, senza sandbox ne' approvazioni."""
    return SubprocessAdapter(
        CODEX_LUNA,
        (executable, "exec", "--dangerously-bypass-approvals-and-sandbox", PROMPT),
    )


def claude_adapter(executable: str = "claude") -> SubprocessAdapter:
    """Configura Claude in print mode, con bypass esplicito dei permessi."""
    return SubprocessAdapter(
        CLAUDE,
        (executable, "--print", "--dangerously-skip-permissions", "--model", "sonnet", PROMPT),
    )


def gemini_adapter(executable: str = "gemini") -> SubprocessAdapter:
    """Configura Gemini in headless mode, fuori sandbox e in yolo mode."""
    return SubprocessAdapter(
        GEMINI,
        (executable, "--prompt", PROMPT, "--sandbox=false", "--yolo", "--skip-trust"),
    )


def code_terra_adapter(command: Sequence[str]) -> SubprocessAdapter:
    """Configura Code Terra con la sua argv non interattiva gia' approvata."""
    return SubprocessAdapter(CODE_TERRA, command)


def _validate_policy(policy: LaunchPolicy) -> None:
    if (type(policy.afk) is not bool or type(policy.sandbox) is not bool
            or type(policy.bypass_permissions) is not bool
            or not policy.afk or policy.sandbox or not policy.bypass_permissions):
        raise ValueError("Autopilot providers must run AFK outside the sandbox with bypass permissions")


def _render_argv(command: Sequence[str], context: LaunchContext) -> list[str]:
    values = {
        "prompt": _prompt(context),
        "node_id": str(context.node["id"]),
        "graph": context.run.graph.slug,
        "root": str(context.run.graph.workspace.project_root),
    }
    rendered = [_replace_placeholders(argument, values) for argument in command]
    if any("\x00" in argument for argument in rendered):
        raise ValueError("provider argv cannot contain NUL")
    return rendered


def _replace_placeholders(argument: str, values: Mapping[str, str]) -> str:
    rendered = argument
    for name, value in values.items():
        rendered = rendered.replace("{" + name + "}", value)
    return rendered


def _prompt(context: LaunchContext) -> str:
    """Il briefing del figlio: il nodo e' gia' suo, e non c'e' nessuno da interrogare.

    Il lucchetto lo ha gia' preso il runner, con l'identita' di questo provider:
    ordinare qui un 'atlas take' chiedeva all'agente di prendere un nodo che
    risultava gia' preso, e la scelta fra rubare il lucchetto e fermarsi restava
    sua. Fermarsi in AFK vuol dire un run morto su una domanda che nessuno
    leggera', quindi il divieto di chiedere conferma e' parte del briefing.
    """
    node_id = str(context.node["id"])
    question = str(context.node.get("question", ""))
    ticket = context.run.graph.ticket_path(node_id)
    return (
        f"Work only on Atlas node {node_id} in graph {context.run.graph.slug}. "
        f"The runner already claimed {node_id} for you: do not run 'atlas take' or "
        f"'atlas release' on it, the node is yours. Read {ticket}, do the work, write "
        f"the Answer section of the ticket, then close the node with "
        f"'atlas close {node_id} -s \"<summary>\"', adding '--artefatti <path>' once per "
        f"file if Atlas asks you to declare them. While you work, call "
        f"'atlas progress {node_id} <PASSO> [\"<nota>\"]' every time you reach a new step, "
        f"PASSO one of investigating, implementing, verifying, writing-answer, blocked: it is "
        f"cheap, call it often, it is what tells the runner you are still working instead of "
        f"stuck. If the node has no valid answer in this run, run "
        f"'atlas give-up {node_id} --motivo <MOTIVO> -d \"<dettaglio>\"', MOTIVO one of "
        f"infeasible, missing-resource, blocked-environment, needs-redesign, instead of forcing "
        f"a wrong answer: it is terminal for this attempt, never retried. If the next step is a "
        f"decision that is not yours to make, run 'atlas ask-human {node_id} -q \"<proposta>\"' "
        f"with a yes/no proposal instead of guessing or stalling silently: it suspends the node "
        f"without counting as a failure. You are running unattended: never stop to ask for "
        f"confirmation or authorization outside of ask-human, decide and finish the work. "
        f"Node question: {question}"
    )


def _environment(identity: str, context: LaunchContext,
                 overrides: Mapping[str, str]) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(overrides)
    environment.update({
        "ATLAS_ROOT": str(context.run.graph.workspace.root),
        "ATLAS_GRAPH": context.run.graph.slug,
        "ATLAS_IDENTITY": identity,
        "ATLAS_AUTOPILOT_NODE": str(context.node["id"]),
    })
    return environment
