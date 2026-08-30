"""Verifica il confine fra Automata e i processi provider reali."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "payload"))

from core import providers  # noqa: E402


class ProviderProcessTest(unittest.TestCase):
    def setUp(self):
        workspace = SimpleNamespace(root=Path("/project/.atlas"), project_root=Path("/project"))
        graph = SimpleNamespace(slug="run-01", workspace=workspace,
                                ticket_path=lambda node_id: Path(f"/project/.atlas/tickets/{node_id}.md"))
        self.context = SimpleNamespace(
            run=SimpleNamespace(graph=graph),
            node={"id": "N01", "question": "handle $(unsafe) && value"},
            policy=SimpleNamespace(afk=True, sandbox=False, bypass_permissions=True),
        )

    @mock.patch.object(providers.subprocess, "Popen")
    def test_lancio_non_interattivo_e_argomenti_non_passano_dalla_shell(self, popen):
        process = SimpleNamespace(returncode=0, communicate=lambda: ("out", ""))
        popen.return_value = process

        handle = providers.SubprocessAdapter("future", ("agent", "--prompt", providers.PROMPT)).launch(self.context)
        outcome = handle.wait()

        argv = popen.call_args.args[0]
        self.assertEqual("agent", argv[0])
        self.assertEqual("--prompt", argv[1])
        self.assertIn("$(unsafe) && value", argv[2])
        self.assertIs(popen.call_args.kwargs["stdin"], providers.subprocess.DEVNULL)
        self.assertFalse(popen.call_args.kwargs["shell"])
        self.assertEqual(Path("/project"), popen.call_args.kwargs["cwd"])
        self.assertEqual("N01", popen.call_args.kwargs["env"]["ATLAS_AUTOMATA_NODE"])
        self.assertEqual("run-01", popen.call_args.kwargs["env"]["ATLAS_GRAPH"])
        self.assertEqual("closed", outcome.status)

    @mock.patch.object(providers.subprocess, "Popen")
    def test_ambiente_base_viene_preservato_e_i_metadati_atlas_sono_obbligatori(self, popen):
        popen.return_value = SimpleNamespace(returncode=1, communicate=lambda: ("", "bad"))
        with mock.patch.dict(os.environ, {"PROVIDER_TOKEN": "secret"}):
            providers.SubprocessAdapter("future", ("agent", providers.PROMPT)).launch(self.context)

        environment = popen.call_args.kwargs["env"]
        self.assertEqual("secret", environment["PROVIDER_TOKEN"])
        self.assertEqual("/project/.atlas", environment["ATLAS_ROOT"])
        self.assertEqual("future", environment["ATLAS_IDENTITY"])

    def test_flag_provider_non_interattivi(self):
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", providers.codex_adapter().command)
        self.assertIn("--dangerously-skip-permissions", providers.claude_adapter().command)
        self.assertIn("--sandbox=false", providers.gemini_adapter().command)
        self.assertIn("--yolo", providers.gemini_adapter().command)

    def test_policy_non_conforme_viene_rifiutata_al_lancio(self):
        self.context.policy = SimpleNamespace(afk=True, sandbox=True, bypass_permissions=True)
        with self.assertRaises(ValueError):
            providers.SubprocessAdapter("future", ("agent", providers.PROMPT)).launch(self.context)

    def test_contenuto_nul_non_arriva_al_processo(self):
        self.context.node["question"] = "unsafe\x00value"
        with self.assertRaises(ValueError):
            providers.SubprocessAdapter("future", ("agent", providers.PROMPT)).launch(self.context)

    @mock.patch.object(providers.subprocess, "Popen", side_effect=FileNotFoundError("missing"))
    def test_provider_assente_e_indisponibilita_esplicita(self, _popen):
        with self.assertRaises(providers.ProviderUnavailableError):
            providers.SubprocessAdapter("future", ("missing-agent", providers.PROMPT)).launch(self.context)


if __name__ == "__main__":
    unittest.main()
