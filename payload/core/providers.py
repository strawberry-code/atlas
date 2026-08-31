"""Processi figli concreti che rispettano il contratto AFK di Automata."""
from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence

from .adapters import (AgentHandle, AgentOutcome, LaunchContext, LaunchPolicy,
                       ProviderUnavailableError, CODEX_LUNA, CLAUDE, CODE_TERRA,
                       GEMINI)


PROMPT = "{prompt}"


class ProcessHandle:
    """Handle che drena l'output del figlio e traduce il suo exit status."""

    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._process = process

    def wait(self) -> AgentOutcome:
        try:
            stdout, stderr = self._process.communicate()
        except OSError as errore:
            return AgentOutcome("ambiguous", str(errore))
        detail = (stderr or stdout or "").strip() or None
        if self._process.returncode == 0:
            return AgentOutcome("closed", detail)
        if self._process.returncode is not None and self._process.returncode < 0:
            return AgentOutcome("crash", detail or f"signal {-self._process.returncode}")
        return AgentOutcome("error", detail or f"exit status {self._process.returncode}")


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
        return ProcessHandle(process)


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
        raise ValueError("Automata providers must run AFK outside the sandbox with bypass permissions")


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
        f"file if Atlas asks you to declare them. You are running unattended: never "
        f"stop to ask for confirmation or authorization, decide and finish the work. "
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
        "ATLAS_AUTOMATA_NODE": str(context.node["id"]),
    })
    return environment
