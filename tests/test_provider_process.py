"""Verifica il confine fra Autopilot e i processi provider reali."""
from __future__ import annotations

import os
import sys
import unittest
from datetime import timedelta
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

    def test_un_agente_che_non_finisce_viene_ucciso_e_conta_come_crash(self):
        """Il tetto di durata esiste perche' senza il runner aspetta all'infinito.

        Regressione del run del 2026-09-03: un agente e' rimasto vivo 442 minuti
        senza scrivere niente, tenendo il nodo rivendicato e fermando il run, e
        l'unico sintomo era che nessun file cambiava piu'.
        """
        import subprocess

        class Appeso:
            returncode = None

            def __init__(self):
                self.ucciso = False
                self.chiamate = 0

            def communicate(self, timeout=None):
                self.chiamate += 1
                if self.chiamate == 1:
                    raise subprocess.TimeoutExpired(cmd="finto", timeout=timeout)
                return ("", "")

            def kill(self):
                self.ucciso = True

        processo = Appeso()
        esito = providers.ProcessHandle(processo, timeout=0.01).wait()

        self.assertTrue(processo.ucciso)
        self.assertEqual("crash", esito.status)
        self.assertIn("no termination", esito.detail)

    def test_un_agente_che_finisce_in_tempo_non_viene_toccato(self):
        class Puntuale:
            returncode = 0

            def __init__(self):
                self.ucciso = False

            def communicate(self, timeout=None):
                return ("fatto", "")

            def kill(self):
                self.ucciso = True

        processo = Puntuale()
        esito = providers.ProcessHandle(processo).wait()

        self.assertFalse(processo.ucciso)
        self.assertEqual("closed", esito.status)

    def test_l_attesa_e_a_fette_non_in_un_colpo_solo(self):
        """H03: comunicate() non riceve mai il tetto assoluto intero, solo fette
        successive. Senza le fette il runner terrebbe il nodo novanta minuti anche
        per un agente morto al secondo, senza mai guardare l'avanzamento dichiarato."""
        import subprocess

        class MaiFinisce:
            returncode = None

            def __init__(self):
                self.timeouts = []
                self.ucciso = False

            def communicate(self, timeout=None):
                self.timeouts.append(timeout)
                if not self.ucciso:
                    raise subprocess.TimeoutExpired(cmd="finto", timeout=timeout)
                return ("", "")

            def kill(self):
                self.ucciso = True

        processo = MaiFinisce()
        esito = providers.ProcessHandle(processo, timeout=0.03, fetta=0.01).wait()

        self.assertEqual(3, len(processo.timeouts[:3]))
        for valore in processo.timeouts[:3]:
            self.assertAlmostEqual(0.01, valore)
        self.assertTrue(processo.ucciso)
        self.assertEqual("crash", esito.status)

    def test_agente_fermo_dopo_un_passo_dichiarato_viene_ucciso_per_silenzio(self):
        """Un nodo che ha gia' dichiarato un passo (H01/4) e poi smette di
        muoversi non aspetta il tetto assoluto: lo dice l'esito 'timeout',
        distinto dal 'crash' del tetto, cosi' run-log distingue le due difese."""
        import subprocess

        class MaiFinisce:
            returncode = None

            def __init__(self):
                self.ucciso = False

            def communicate(self, timeout=None):
                if not self.ucciso:
                    raise subprocess.TimeoutExpired(cmd="finto", timeout=timeout)
                return ("", "")

            def kill(self):
                self.ucciso = True

        processo = MaiFinisce()
        handle = providers.ProcessHandle(
            processo, timeout=3600, fetta=0.01, silenzio_ammesso=0.02,
            graph=SimpleNamespace(json_path=Path("/fake/graph.json")), node_id="N01")

        with mock.patch.object(providers.claims, "silent_for", return_value=timedelta(seconds=5)), \
             mock.patch.object(providers, "load", return_value={}), \
             mock.patch.object(providers, "node_of", return_value={}):
            esito = handle.wait()

        self.assertTrue(processo.ucciso)
        self.assertEqual("timeout", esito.status)
        self.assertIn("no progress declared", esito.detail)

    def test_agente_senza_alcun_passo_dichiarato_non_e_ucciso_per_silenzio(self):
        """Il tetto assoluto resta l'unica difesa per chi non ha mai dichiarato
        un passo (claims.silent_for torna None): un silenzio_ammesso minuscolo
        non lo tocca, anche dopo diverse fette."""
        import subprocess

        class FinisceDopoQualcheFetta:
            returncode = 0

            def __init__(self, fette):
                self.fette = fette
                self.chiamate = 0
                self.ucciso = False

            def communicate(self, timeout=None):
                self.chiamate += 1
                if self.chiamate <= self.fette:
                    raise subprocess.TimeoutExpired(cmd="finto", timeout=timeout)
                return ("fatto", "")

            def kill(self):
                self.ucciso = True

        processo = FinisceDopoQualcheFetta(fette=5)
        handle = providers.ProcessHandle(
            processo, timeout=3600, fetta=0.01, silenzio_ammesso=0.001,
            graph=SimpleNamespace(json_path=Path("/fake/graph.json")), node_id="N01")

        with mock.patch.object(providers.claims, "silent_for", return_value=None), \
             mock.patch.object(providers, "load", return_value={}), \
             mock.patch.object(providers, "node_of", return_value={}):
            esito = handle.wait()

        self.assertFalse(processo.ucciso)
        self.assertEqual("closed", esito.status)
        self.assertEqual(6, processo.chiamate)

    def test_lettura_del_grafo_fallita_non_uccide_il_lavoro_per_un_guasto_suo(self):
        """Una lettura che va storta a meta' fetta (disco, permessi, un grafo a
        meta' scrittura) conta come 'non lo so', non come silenzio: il tentativo
        resta protetto dal solo tetto assoluto, come se il grafo non ci fosse."""
        import subprocess

        class MaiFinisce:
            returncode = None

            def __init__(self):
                self.ucciso = False

            def communicate(self, timeout=None):
                if not self.ucciso:
                    raise subprocess.TimeoutExpired(cmd="finto", timeout=timeout)
                return ("", "")

            def kill(self):
                self.ucciso = True

        processo = MaiFinisce()
        handle = providers.ProcessHandle(
            processo, timeout=0.05, fetta=0.01, silenzio_ammesso=0.001,
            graph=SimpleNamespace(json_path=Path("/fake/graph.json")), node_id="N01")

        with mock.patch.object(providers, "load", side_effect=OSError("disco pieno")):
            esito = handle.wait()

        self.assertTrue(processo.ucciso)
        self.assertEqual("crash", esito.status)
        self.assertIn("no termination", esito.detail)

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
        popen.return_value = SimpleNamespace(returncode=1, communicate=lambda timeout=None: (uscita, ""))

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
        popen.return_value = SimpleNamespace(returncode=1, communicate=lambda timeout=None: (uscita, ""))

        outcome = providers.codex_adapter().launch(self.context).wait()

        self.assertEqual("error", outcome.status)
        self.assertNotIn("rate limit", outcome.detail)

    @mock.patch.object(providers.subprocess, "Popen")
    def test_lancio_non_interattivo_e_argomenti_non_passano_dalla_shell(self, popen):
        process = SimpleNamespace(returncode=0, communicate=lambda timeout=None: ("out", ""))
        popen.return_value = process

        handle = providers.SubprocessAdapter("future", ("agent", "--prompt", providers.PROMPT)).launch(self.context)
        self.assertIs(handle._graph, self.context.run.graph)
        self.assertEqual("N01", handle._node_id)
        outcome = handle.wait()

        argv = popen.call_args.args[0]
        self.assertEqual("agent", argv[0])
        self.assertEqual("--prompt", argv[1])
        self.assertIn("$(unsafe) && value", argv[2])
        self.assertIs(popen.call_args.kwargs["stdin"], providers.subprocess.DEVNULL)
        self.assertFalse(popen.call_args.kwargs["shell"])
        self.assertEqual(Path("/project"), popen.call_args.kwargs["cwd"])
        self.assertEqual("N01", popen.call_args.kwargs["env"]["ATLAS_AUTOPILOT_NODE"])
        self.assertEqual("run-01", popen.call_args.kwargs["env"]["ATLAS_GRAPH"])
        self.assertEqual("closed", outcome.status)

    @mock.patch.object(providers.subprocess, "Popen")
    def test_ambiente_base_viene_preservato_e_i_metadati_atlas_sono_obbligatori(self, popen):
        popen.return_value = SimpleNamespace(returncode=1, communicate=lambda timeout=None: ("", "bad"))
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
