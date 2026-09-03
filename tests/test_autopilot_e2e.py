"""Test end-to-end deterministici del runner Autopilot con adapter finti."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SOURCE = Path(__file__).resolve().parent.parent / "payload"


class ScriptedHandle:
    def __init__(self, adapter, context):
        self.adapter = adapter
        self.context = context

    def wait(self):
        outcome = self.adapter.scripts[self.context.node["id"]].pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        if outcome.status == "closed":
            self.adapter.close(self.context)
        return outcome


class ScriptedAdapter:
    def __init__(self, identity, scripts, close):
        self.identity = identity
        self.scripts = {node_id: list(outcomes) for node_id, outcomes in scripts.items()}
        self.close = close
        self.launched = []

    def launch(self, context):
        self.launched.append(context.node["id"])
        return ScriptedHandle(self, context)


class UnavailableAdapter(ScriptedAdapter):
    def __init__(self, identity, scripts, adapters, close):
        super().__init__(identity, scripts, close)
        self.adapters = adapters

    def launch(self, context):
        self.launched.append(context.node["id"])
        raise self.adapters.ProviderUnavailableError("provider offline")


class AutopilotEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / ".atlas"
        shutil.copytree(SOURCE, self.root)
        (self.root / "config.json").write_text('{"project": "prova"}', encoding="utf-8")
        for folder in ("graphs", "scripts"):
            (self.root / folder).mkdir()
        sys.path.insert(0, str(self.root))
        os.environ["ATLAS_ROOT"] = str(self.root)
        for module in [m for m in sys.modules if m == "core" or m.startswith("core.")]:
            del sys.modules[module]
        from core import adapters, claims, config, docs, mutate, retry, store

        self.adapters = adapters
        self.claims = claims
        self.config = config
        self.docs = docs
        self.mutate = mutate
        self.retry = retry
        self.store = store
        self.workspace = config.workspace(self.tmp)
        self.ref = mutate.create_graph(self.workspace, "prova", "Grafo", "Verificare")

    def tearDown(self):
        sys.path.remove(str(self.root))
        os.environ.pop("ATLAS_ROOT", None)
        for module in [m for m in sys.modules if m == "core" or m.startswith("core.")]:
            del sys.modules[module]
        shutil.rmtree(self.tmp)

    def add_nodes(self, scripts, model=None):
        with self.mutate.editing(self.ref) as graph:
            self.mutate.add_branch(graph, "B", "Runner", "#0f766e")
            for node_id in scripts:
                self.mutate.add_node(graph, node_id, node_id, "B", "esegui", model=model)
        self.docs.write_stubs(self.ref, self.store.load(self.ref.json_path))

    def close_node(self, context):
        node_id = context.node["id"]
        ticket = context.run.graph.ticket_path(node_id)
        ticket.write_text(ticket.read_text(encoding="utf-8") + "\nRisposta fake.\n",
                          encoding="utf-8")
        self.claims.close(context.run.graph, node_id, "chiuso da adapter fake", artifacts=[])

    def wait_for(self, handle):
        return handle.wait()

    def risolutore(self):
        """Risponde alla card con cui il runner si ferma: senza, il test attende
        la scadenza dell'Interazione, cioe' un giorno."""
        from core import interactions

        from tests import waiter_risolutore

        return waiter_risolutore(self.ref, self.mutate, interactions)

    def test_retries_timeout_crash_rate_limit_provider_and_ambiguous(self):
        failures = {
            "N01": [TimeoutError("provider timed out"), self.adapters.AgentOutcome("closed")],
            "N02": [self.retry.CrashError("process crashed"), self.adapters.AgentOutcome("closed")],
            "N03": [self.retry.RateLimitError("429 too many requests"), self.adapters.AgentOutcome("closed")],
            "N04": [self.adapters.ProviderUnavailableError("provider offline"), self.adapters.AgentOutcome("closed")],
            "N05": [self.retry.AmbiguousTerminationError("termination is ambiguous"), self.adapters.AgentOutcome("closed")],
        }
        self.add_nodes(failures, model=self.adapters.CLAUDE)
        adapter = ScriptedAdapter(self.adapters.CLAUDE, failures, self.close_node)
        registry = self.adapters.AdapterRegistry([adapter])
        policy = self.retry.RetryPolicy(max_attempts=3, initial_delay=0)

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            result = self.autopilot().start(self.ref, 1, retry_policy=policy).execute(
                self.autopilot().launcher_from_registry(registry), self.wait_for)

        self.assertEqual(tuple(failures), result.terminal_nodes)
        self.assertEqual([node_id for node_id in failures for _ in (0, 1)], adapter.launched)
        self.assertEqual({}, json.loads(self.ref.retry_state_path.read_text())["nodes"])
        events = json.loads(self.ref.run_state_path.read_text())["events"]
        self.assertEqual(
            {"timeout", "crash", "rate-limit", "provider-unavailable", "ambiguous-termination"},
            {event["failure"] for event in events if event["type"] == "attempt-failed"},
        )

    def test_backoff_progressivo_viene_atteso_prima_del_retry(self):
        scripts = {
            "N01": [TimeoutError("timed out"), self.retry.RateLimitError("rate limit"),
                    self.adapters.AgentOutcome("closed")],
        }
        self.add_nodes(scripts, model=self.adapters.CLAUDE)
        adapter = ScriptedAdapter(self.adapters.CLAUDE, scripts, self.close_node)
        registry = self.adapters.AdapterRegistry([adapter])
        policy = self.retry.RetryPolicy(max_attempts=4)
        clock = [100.0]
        waits = []

        def sleeper(seconds):
            waits.append(seconds)
            clock[0] += seconds

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            result = self.autopilot().start(self.ref, 1, retry_policy=policy).execute(
                self.autopilot().launcher_from_registry(registry), self.wait_for,
                now=lambda: clock[0], sleeper=sleeper)

        self.assertEqual(("N01",), result.terminal_nodes)
        self.assertEqual([60.0, 120.0], waits)
        self.assertEqual(["N01", "N01", "N01"], adapter.launched)

    def test_fallback_default_luna_a_claude_e_selezione_esplicita(self):
        scripts = {"N01": [self.adapters.AgentOutcome("closed")]}
        self.add_nodes(scripts)
        luna = UnavailableAdapter(self.adapters.CODEX_LUNA, scripts, self.adapters, self.close_node)
        claude = ScriptedAdapter(self.adapters.CLAUDE, scripts, self.close_node)
        registry = self.adapters.AdapterRegistry([luna, claude])

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            result = self.autopilot().start(self.ref, 1).execute(
                self.autopilot().launcher_from_registry(registry), self.wait_for)

        self.assertEqual(("N01",), result.terminal_nodes)
        self.assertEqual(["N01"], luna.launched)
        self.assertEqual(["N01"], claude.launched)
        events = json.loads(self.ref.run_state_path.read_text())["events"]
        self.assertEqual(1, sum(event["type"] == "fallback" for event in events))
        self.assertEqual(1, sum(event["type"] == "provider-selected"
                                 and event["provider"] == self.adapters.CLAUDE
                                 for event in events))

    def test_terminazione_ambigua_non_dichiara_successo(self):
        scripts = {"N01": [self.adapters.AgentOutcome("ambiguous")]}
        self.add_nodes(scripts, model=self.adapters.CLAUDE)
        adapter = ScriptedAdapter(self.adapters.CLAUDE, scripts, self.close_node)
        registry = self.adapters.AdapterRegistry([adapter])

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}), self.assertRaises(
                self.autopilot().RunnerError):
            self.autopilot().start(
                self.ref, 1, retry_policy=self.retry.RetryPolicy(max_attempts=1, initial_delay=0)
            ).execute(self.autopilot().launcher_from_registry(registry), self.wait_for,
                      interaction_waiter=self.risolutore())

        self.assertEqual("failed", json.loads(self.ref.run_state_path.read_text())["status"])
        self.assertEqual("terminal", json.loads(self.ref.retry_state_path.read_text())[
            "nodes"]["N01"]["status"])
        self.assertEqual("open", self.store.load(self.ref.json_path)["nodes"][0]["status"])

    def autopilot(self):
        from core import autopilot

        return autopilot


if __name__ == "__main__":
    unittest.main()
