"""Presidia il confine estensibile fra Automata e i provider agente."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "payload"))

from core import adapters  # noqa: E402


class Handle:
    def wait(self):
        return adapters.AgentOutcome("closed")


class RecordingAdapter:
    def __init__(self, identity):
        self.identity = identity
        self.context = None

    def launch(self, context):
        self.context = context
        return Handle()


class AdapterRegistryTest(unittest.TestCase):
    def test_identities_minime_previste(self):
        self.assertEqual(
            {
                "codex-luna": "Codex Luna",
                "claude": "Claude Sonnet",
                "gemini": "Gemini",
                "code-terra": "Code Terra",
            },
            adapters.IDENTITIES,
        )

    def test_adapter_configurabile_si_lancia_con_contesto_afk(self):
        adapter = RecordingAdapter(adapters.CODEX_LUNA)
        registry = adapters.AdapterRegistry([adapter])
        run = mock.sentinel.run
        node = {"id": "N01", "mode": "AFK"}

        handle = registry.launcher(adapters.CODEX_LUNA)(run, node)

        self.assertIsInstance(handle, Handle)
        self.assertIs(run, adapter.context.run)
        self.assertIs(node, adapter.context.node)
        self.assertEqual(True, adapter.context.policy.afk)
        self.assertEqual(False, adapter.context.policy.sandbox)
        self.assertEqual(True, adapter.context.policy.bypass_permissions)
        self.assertEqual("closed", handle.wait().status)

    def test_provider_nuovo_non_richiede_modifiche_al_registry(self):
        adapter = RecordingAdapter("provider-futuro")
        registry = adapters.AdapterRegistry()

        registry.register(adapter)

        self.assertEqual(("provider-futuro",), registry.identities())
        self.assertIs(adapter, registry.get("provider-futuro"))

    def test_identita_non_configurata_e_duplicata_sono_rifiutate(self):
        adapter = RecordingAdapter(adapters.CLAUDE)
        registry = adapters.AdapterRegistry([adapter])

        with self.assertRaises(adapters.AdapterRegistryError):
            registry.get(adapters.GEMINI)
        with self.assertRaises(adapters.AdapterRegistryError):
            registry.register(RecordingAdapter(adapters.CLAUDE))
        with self.assertRaises(adapters.AdapterRegistryError):
            registry.register(RecordingAdapter("  "))
        with self.assertRaises(adapters.AdapterRegistryError):
            registry.register(RecordingAdapter(" future "))

    def test_policy_non_puo_disattivare_i_vincoli_afk(self):
        for policy in (
            {"afk": False},
            {"sandbox": True},
            {"bypass_permissions": False},
        ):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                adapters.LaunchPolicy(**policy)

    def test_esito_accetta_solo_i_tre_stati_osservabili(self):
        with self.assertRaises(ValueError):
            adapters.AgentOutcome("unknown")

    def test_runner_traduce_chiusura_e_rifiuta_esiti_non_terminali(self):
        from core import automata

        class ClosedHandle:
            def wait(self):
                return adapters.AgentOutcome("closed")

        class FailedHandle:
            def wait(self):
                return adapters.AgentOutcome("error", "process exited")

        self.assertEqual(
            (automata.ClosureEvent("N01"),),
            automata._wait(ClosedHandle(), None, "N01"),
        )
        with self.assertRaises(automata.RunnerError):
            automata._wait(FailedHandle(), None, "N01")


if __name__ == "__main__":
    unittest.main()
