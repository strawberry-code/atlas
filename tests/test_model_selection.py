"""Presidia la selezione del modello dal nodo al registry."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "payload"))

from core import adapters, autopilot  # noqa: E402


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


class UnavailableOnLaunchAdapter(RecordingAdapter):
    def launch(self, context):
        self.context = context
        raise adapters.ProviderUnavailableError("provider offline")


class UnavailableOnWaitHandle:
    def wait(self):
        return adapters.AgentOutcome("provider-unavailable", "provider offline")


class UnavailableOnWaitAdapter(RecordingAdapter):
    def launch(self, context):
        self.context = context
        return UnavailableOnWaitHandle()


class ErrorAdapter(RecordingAdapter):
    def launch(self, context):
        self.context = context

        class ErrorHandle:
            def wait(self):
                return adapters.AgentOutcome("error", "agent work failed")

        return ErrorHandle()


class ModelSelectionTest(unittest.TestCase):
    def setUp(self):
        self.luna = RecordingAdapter(adapters.CODEX_LUNA)
        self.claude = RecordingAdapter(adapters.CLAUDE)
        self.registry = adapters.AdapterRegistry([self.luna, self.claude])

    def test_model_assente_o_vuoto_usa_codex_luna(self):
        for node in ({"id": "N01"}, {"id": "N02", "model": ""}):
            with self.subTest(node=node):
                risolto = self.registry.resolve(node)
                self.assertEqual(adapters.DEFAULT_MODEL, risolto.identity)
                self.assertIs(self.luna, risolto.adapter)
                self.assertTrue(risolto.defaulted)

    def test_model_esplicito_usa_lidentita_esatta(self):
        risolto = self.registry.resolve({"id": "N01", "model": adapters.CLAUDE})

        self.assertEqual(adapters.CLAUDE, risolto.identity)
        self.assertIs(self.claude, risolto.adapter)
        self.assertFalse(risolto.defaulted)

    def test_model_sconosciuto_rifiutato_con_diagnosi(self):
        with self.assertRaisesRegex(
            adapters.AdapterRegistryError,
            r"node N01 requests unknown model 'sonnet-unknown'.*configured identities: claude, codex-luna",
        ):
            self.registry.resolve({"id": "N01", "model": "sonnet-unknown"})

    def test_default_non_configurato_usa_claude_sonnet(self):
        registry = adapters.AdapterRegistry([self.claude])
        run = mock.Mock()
        run.log = []

        handle = autopilot.launcher_from_registry(registry)(run, {"id": "N01"})

        self.assertIsInstance(handle, Handle)
        self.assertIs(run, self.claude.context.run)
        self.assertEqual(
            [
                "model-selected node=N01 model=codex-luna source=default",
                "model-fallback node=N01 from=codex-luna to=claude reason=provider-unavailable",
                "model-selected node=N01 model=claude source=fallback",
            ],
            run.log,
        )

    def test_launcher_registra_la_selezione_nel_log_del_run(self):
        run = mock.Mock()
        run.log = []
        logger = mock.Mock()
        launcher = autopilot.launcher_from_registry(self.registry, logger)

        handle = launcher(run, {"id": "N01", "model": adapters.CLAUDE})

        self.assertIsInstance(handle, Handle)
        self.assertEqual(
            ["model-selected node=N01 model=claude source=explicit"], run.log)
        logger.assert_called_once_with(run.log[0])
        self.assertIs(run, self.claude.context.run)

    def test_launcher_registra_il_default_nel_log_del_run(self):
        run = mock.Mock()
        run.log = []
        launcher = autopilot.launcher_from_registry(self.registry)

        launcher(run, {"id": "N01"})

        self.assertEqual(
            ["model-selected node=N01 model=codex-luna source=default"], run.log)

    def test_provider_luna_non_disponibile_al_lancio_fa_una_sola_transizione(self):
        luna = UnavailableOnLaunchAdapter(adapters.CODEX_LUNA)
        registry = adapters.AdapterRegistry([luna, self.claude])
        run = mock.Mock()
        run.log = []
        launcher = autopilot.launcher_from_registry(registry)

        handle = launcher(run, {"id": "N01"})

        self.assertIsInstance(handle, Handle)
        self.assertEqual(
            [
                "model-selected node=N01 model=codex-luna source=default",
                "model-fallback node=N01 from=codex-luna to=claude reason=provider-unavailable",
                "model-selected node=N01 model=claude source=fallback",
            ],
            run.log,
        )

    def test_provider_luna_non_disponibile_durante_attesa_fa_fallback(self):
        luna = UnavailableOnWaitAdapter(adapters.CODEX_LUNA)
        registry = adapters.AdapterRegistry([luna, self.claude])
        run = mock.Mock()
        run.log = []

        handle = autopilot.launcher_from_registry(registry)(run, {"id": "N01"})

        self.assertEqual("closed", handle.wait().status)
        self.assertEqual(
            [
                "model-selected node=N01 model=codex-luna source=default",
                "model-fallback node=N01 from=codex-luna to=claude reason=provider-unavailable",
                "model-selected node=N01 model=claude source=fallback",
            ],
            run.log,
        )

    def test_fallback_non_disponibile_non_avvia_un_secondo_fallback(self):
        luna = UnavailableOnLaunchAdapter(adapters.CODEX_LUNA)
        claude = UnavailableOnLaunchAdapter(adapters.CLAUDE)
        registry = adapters.AdapterRegistry([luna, claude])
        run = mock.Mock()
        run.log = []

        with self.assertRaises(adapters.ProviderUnavailableError):
            autopilot.launcher_from_registry(registry)(run, {"id": "N01"})

        self.assertEqual(
            [
                "model-selected node=N01 model=codex-luna source=default",
                "model-fallback node=N01 from=codex-luna to=claude reason=provider-unavailable",
                "model-selected node=N01 model=claude source=fallback",
            ],
            run.log,
        )

    def test_errore_del_lavoro_non_attiva_fallback(self):
        luna = ErrorAdapter(adapters.CODEX_LUNA)
        registry = adapters.AdapterRegistry([luna, self.claude])
        run = mock.Mock()
        run.log = []

        handle = autopilot.launcher_from_registry(registry)(run, {"id": "N01"})

        self.assertEqual("error", handle.wait().status)
        self.assertEqual(
            ["model-selected node=N01 model=codex-luna source=default"], run.log)

    def test_richiesta_esplicita_non_attiva_fallback(self):
        luna = UnavailableOnLaunchAdapter(adapters.CODEX_LUNA)
        registry = adapters.AdapterRegistry([luna, self.claude])
        run = mock.Mock()
        run.log = []

        with self.assertRaises(adapters.ProviderUnavailableError):
            autopilot.launcher_from_registry(registry)(
                run, {"id": "N01", "model": adapters.CODEX_LUNA})

        self.assertEqual(
            ["model-selected node=N01 model=codex-luna source=explicit"], run.log)

    def test_launcher_registra_il_rifiuto_nel_log_del_run(self):
        run = mock.Mock()
        run.log = []
        logger = mock.Mock()
        launcher = autopilot.launcher_from_registry(self.registry, logger)

        with self.assertRaises(adapters.AdapterRegistryError):
            launcher(run, {"id": "N01", "model": "sonnet-unknown"})

        self.assertEqual(1, len(run.log))
        self.assertIn("model-rejected node=N01", run.log[0])
        self.assertIn("sonnet-unknown", run.log[0])
        logger.assert_called_once_with(run.log[0])


if __name__ == "__main__":
    unittest.main()
