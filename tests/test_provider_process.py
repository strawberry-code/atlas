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

    def test_il_briefing_non_ordina_un_secondo_lucchetto_ne_ammette_domande(self):
        """Il figlio riceve un nodo gia' suo e nessuno a cui chiedere.

        Regressione del run del 2026-08-30: il briefing ordinava 'atlas take', il
        nodo risultava gia' rivendicato e l'agente si e' fermato a chiedere
        l'autorizzazione a forzarlo, uscendo con exit status zero.
        """
        prompt = providers._prompt(self.context)

        self.assertIn("do not run 'atlas take'", prompt)
        self.assertIn("already claimed N01 for you", prompt)
        self.assertIn("atlas close N01", prompt)
        self.assertIn("never", prompt.lower())
        self.assertIn("handle $(unsafe) && value", prompt)

    @mock.patch.object(providers.subprocess, "Popen")
    def test_quota_finita_vale_provider_assente_non_errore_del_lavoro(self, popen):
        """Regressione del run del 2026-08-31: quota Codex esaurita per un mese.

        Uscendo come 'error' il runner ritentava lo stesso provider otto volte e
        il fallback a Claude, promesso a ogni avvio, non scattava mai.
        """
        uscita = (
            "OpenAI Codex v0.151.0\nworkdir: /progetto\nuser\n"
            "Work only on Atlas node D01... Node question: applica retry bounded.\n"
            "hook: UserPromptSubmit Completed\n"
            "ERROR: You've hit your usage limit. Upgrade to Plus to continue using "
            "Codex (https://chatgpt.com/explore/plus), or try again at Sep 30th, 2026 9:35 AM."
        )
        popen.return_value = SimpleNamespace(returncode=1, communicate=lambda: (uscita, ""))

        outcome = providers.codex_adapter().launch(self.context).wait()

        self.assertEqual("provider-unavailable", outcome.status)

    @mock.patch.object(providers.subprocess, "Popen")
    def test_un_ticket_che_parla_di_rate_limit_non_e_un_provider_assente(self, popen):
        """La firma si cerca nella coda, non nell'eco del prompt.

        Il detail contiene la domanda del nodo: cercarla nel testo intero faceva
        passare per provider a quota finita un nodo che parla di rate limit.
        """
        self.context.node["question"] = "implementa un rate limit con 429 e quota per utente"
        eco = providers._prompt(self.context)
        uscita = (f"OpenAI Codex v0.151.0\nuser\n{eco}\n"
                  "thinking\nERROR: the test suite failed, three assertions are red.")
        popen.return_value = SimpleNamespace(returncode=1, communicate=lambda: (uscita, ""))

        outcome = providers.codex_adapter().launch(self.context).wait()

        self.assertEqual("error", outcome.status)
        self.assertNotIn("rate limit", outcome.detail)

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
