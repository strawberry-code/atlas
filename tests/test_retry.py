"""Presidia retry bounded, classificazione e ripresa del runner."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SORGENTE = Path(__file__).resolve().parent.parent / "payload"


class RetryClassifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(SORGENTE))
        from core import adapters, retry

        cls.adapters = adapters
        cls.retry = retry

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(SORGENTE))

    def test_classifica_i_sei_guasti(self):
        casi = (
            (TimeoutError("provider timed out"), "timeout"),
            (self.retry.CrashError("process crashed"), "crash"),
            (self.retry.RateLimitError("429 too many requests"), "rate-limit"),
            (self.adapters.ProviderUnavailableError("provider offline"), "provider-unavailable"),
            (self.retry.AmbiguousTerminationError("termination is ambiguous"), "ambiguous-termination"),
            (self.retry.PermanentError("invalid request"), "permanent-error"),
        )
        for errore, atteso in casi:
            with self.subTest(errore=errore):
                self.assertEqual(atteso, self.retry.classify_failure(errore))

    def test_classifica_gli_esiti_osservabili_degli_adapter(self):
        casi = (
            (self.adapters.AgentOutcome("timeout"), "timeout"),
            (self.adapters.AgentOutcome("crash"), "crash"),
            (self.adapters.AgentOutcome("rate-limit"), "rate-limit"),
            (self.adapters.AgentOutcome("provider-unavailable"), "provider-unavailable"),
            (self.adapters.AgentOutcome("ambiguous"), "ambiguous-termination"),
            (self.adapters.AgentOutcome("permanent-error"), "permanent-error"),
        )
        for esito, atteso in casi:
            with self.subTest(esito=esito):
                self.assertEqual(atteso, self.retry.classify_failure(esito))

    def test_chiusura_non_e_un_guasto(self):
        self.assertIsNone(self.retry.classify_failure(self.adapters.AgentOutcome("closed")))

    def test_la_resa_si_classifica_a_parte_e_non_e_ritentabile(self):
        """H01/2 + H04: SurrenderedError non passa da _da_dettaglio come gli altri
        guasti testuali, e 'surrendered' resta fuori da RETRYABLE_FAILURES."""
        self.assertEqual(
            "surrendered",
            self.retry.classify_failure(self.retry.SurrenderedError("infeasible: non si puo' fare")))
        self.assertNotIn("surrendered", self.retry.RETRYABLE_FAILURES)

    def test_lorfano_di_risposta_non_e_ritentabile(self):
        """H07: chi legge il log sa gia' cosa fare (recuperare, non rifare), quindi
        'orphaned-answer' resta fuori da RETRYABLE_FAILURES come 'surrendered'."""
        self.assertNotIn("orphaned-answer", self.retry.RETRYABLE_FAILURES)

    def test_backoff_cresce_fino_al_cap_di_un_ora(self):
        policy = self.retry.RetryPolicy()

        self.assertEqual([60, 120, 240, 480, 960, 1920, 3600, 3600],
                         [policy.delay_for(attempt) for attempt in range(1, 9)])
        self.assertTrue(policy.can_retry(1))
        self.assertFalse(policy.can_retry(policy.max_attempts))

    def test_lambiguo_ha_un_tetto_piu_stretto_del_budget_generale(self):
        """Rilanciare otto volte un agente che esce senza chiudere brucia quota."""
        policy = self.retry.RetryPolicy()

        self.assertTrue(policy.can_retry(1, "ambiguous-termination"))
        self.assertFalse(policy.can_retry(2, "ambiguous-termination"))
        self.assertTrue(policy.can_retry(2, "timeout"))
        # Un budget generale piu' stretto del tetto ambiguo resta il vincolo.
        stretta = self.retry.RetryPolicy(max_attempts=1)
        self.assertFalse(stretta.can_retry(1, "ambiguous-termination"))
        with self.assertRaises(ValueError):
            self.retry.RetryPolicy(ambiguous_attempts=0)


class RetryStateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(SORGENTE))

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(SORGENTE))

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_stato_attivo_e_fallimento_sopravvivono_al_riavvio(self):
        from core.retry import RetryState

        path = self.tmp / "retry-state.json"
        stato = RetryState(path, "grafo")
        self.assertEqual(1, stato.begin("N01", 100.0))
        stato.record_failure("N01", 1, "timeout", "lento", 100.0, 60.0)

        riavviato = RetryState(path, "grafo")
        record = riavviato.record("N01")
        self.assertEqual("pending", record["status"])
        self.assertEqual("timeout", record["failure"])
        self.assertEqual(160.0, record["next_at"])
        self.assertEqual("grafo", json.loads(path.read_text())["graph"])


class RetryRunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / ".atlas"
        shutil.copytree(SORGENTE, self.root)
        (self.root / "config.json").write_text('{"project": "prova"}', encoding="utf-8")
        for cartella in ("graphs", "scripts"):
            (self.root / cartella).mkdir()
        sys.path.insert(0, str(self.root))
        os.environ["ATLAS_ROOT"] = str(self.root)
        for modulo in [m for m in sys.modules if m == "core" or m.startswith("core.")]:
            del sys.modules[modulo]
        from core import autopilot, claims, docs, mutate, retry, store

        self.autopilot, self.claims = autopilot, claims
        self.docs, self.mutate, self.retry, self.store = docs, mutate, retry, store
        self.ws = __import__("core.config", fromlist=["workspace"]).workspace(self.tmp)
        self.ref = mutate.create_graph(self.ws, "prova", "Grafo", "Verificare")
        with self.mutate.editing(self.ref) as graph:
            self.mutate.add_branch(graph, "B", "Runner", "#0f766e")
            self.mutate.add_node(graph, "N01", "Nodo", "B", "esegui")
        self.docs.write_stubs(self.ref, self.store.load(self.ref.json_path))

    def tearDown(self):
        sys.path.remove(str(self.root))
        os.environ.pop("ATLAS_ROOT", None)
        for modulo in [m for m in sys.modules if m == "core" or m.startswith("core.")]:
            del sys.modules[modulo]
        shutil.rmtree(self.tmp)

    def _chiudi(self):
        path = self.ref.ticket_path("N01")
        path.write_text(path.read_text(encoding="utf-8") + "\nRisposta eseguita.\n", encoding="utf-8")
        self.claims.close(self.ref, "N01", "eseguito", artifacts=[])

    def test_retry_rilancia_dopo_timeout_e_pulisce_lo_stato_a_chiusura(self):
        tentativi = []
        policy = self.retry.RetryPolicy(max_attempts=3, initial_delay=0)

        def launcher(run, node):
            tentativi.append(node["id"])
            return node["id"]

        def wait_for(_handle):
            if len(tentativi) == 1:
                return self.autopilot.AgentOutcome("timeout", "provider timed out")
            self._chiudi()
            return self.autopilot.ClosureEvent("N01")

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            risultato = self.autopilot.start(self.ref, 1, retry_policy=policy).execute(
                launcher, wait_for=wait_for, sleeper=lambda _seconds: None)

        self.assertEqual(("N01",), risultato.terminal_nodes)
        self.assertEqual(["N01", "N01"], tentativi)
        self.assertEqual({}, json.loads(self.ref.retry_state_path.read_text())["nodes"])

    def test_retry_e_bounded_e_non_riprova_un_errore_permanente(self):
        tentativi = []
        policy = self.retry.RetryPolicy(max_attempts=2, initial_delay=0)

        def launcher(_run, node):
            tentativi.append(node["id"])
            return node["id"]

        def wait_for(_handle):
            return self.autopilot.AgentOutcome("permanent-error", "invalid request")

        from core import interactions

        from tests import waiter_risolutore

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            with self.assertRaises(self.autopilot.RunnerError):
                self.autopilot.start(self.ref, 1, retry_policy=policy).execute(
                    launcher, wait_for=wait_for, sleeper=lambda _seconds: None,
                    interaction_waiter=waiter_risolutore(self.ref, self.mutate, interactions))

        self.assertEqual(["N01"], tentativi)
        self.assertEqual("terminal", json.loads(self.ref.retry_state_path.read_text())["nodes"]["N01"]["status"])

    def test_resa_e_terminale_e_non_ritenta(self):
        """H01/2 + H04: oggi lo stesso caso finiva in 'ambiguous-termination', che
        e' fra i guasti ritentabili. Una resa dichiarata deve fermarsi al primo
        tentativo, restare distinguibile da un crash nel ledger e riaprire il
        nodo, non lasciarlo rivendicato come fa un guasto qualunque."""
        tentativi = []
        policy = self.retry.RetryPolicy(max_attempts=3, initial_delay=0)

        def launcher(_run, node):
            tentativi.append(node["id"])
            return node["id"]

        def wait_for(_handle):
            self.claims.give_up(self.ref, "N01", "infeasible",
                                "il vincolo dichiarato e' impossibile da rispettare")
            return None

        from core import interactions

        from tests import waiter_risolutore

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            with self.assertRaises(self.autopilot.RunnerError):
                self.autopilot.start(self.ref, 1, retry_policy=policy).execute(
                    launcher, wait_for=wait_for, sleeper=lambda _seconds: None,
                    interaction_waiter=waiter_risolutore(self.ref, self.mutate, interactions))

        self.assertEqual(["N01"], tentativi, "una resa non deve far ripartire un secondo tentativo")
        record = json.loads(self.ref.retry_state_path.read_text())["nodes"]["N01"]
        self.assertEqual("terminal", record["status"])
        self.assertEqual("surrendered", record["failure"])
        self.assertEqual("open", json.loads(self.ref.json_path.read_text())["nodes"][0]["status"])
        eventi = json.loads(self.ref.run_state_path.read_text())["events"]
        falliti = [e for e in eventi if e["type"] == "attempt-failed"]
        self.assertEqual(["surrendered"], [e["failure"] for e in falliti])

    def test_retry_applica_il_backoff_persistito_prima_del_secondo_lancio(self):
        tentativi, attese = [], []
        orologio = [100.0]
        policy = self.retry.RetryPolicy(max_attempts=3)

        def launcher(_run, node):
            tentativi.append(node["id"])
            return node["id"]

        def wait_for(_handle):
            if len(tentativi) == 1:
                return self.autopilot.AgentOutcome("rate-limit", "429")
            self._chiudi()
            return self.autopilot.ClosureEvent("N01")

        def sleeper(secondi):
            attese.append(secondi)
            orologio[0] += secondi

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            risultato = self.autopilot.start(self.ref, 1, retry_policy=policy).execute(
                launcher, wait_for=wait_for, now=lambda: orologio[0], sleeper=sleeper)

        self.assertEqual(("N01",), risultato.terminal_nodes)
        self.assertEqual([60.0], attese)
        self.assertEqual(["N01", "N01"], tentativi)

    def test_riavvio_di_un_tentativo_interrotto_attende_il_claim_morto(self):
        tentativi = []
        policy = self.retry.RetryPolicy(max_attempts=2, initial_delay=0)
        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            self.claims.claim(self.ref, "N01")
            stato = self.retry.RetryState(self.ref.retry_state_path, self.ref.slug)
            stato.begin("N01", 100.0)

            def launcher(_run, node):
                tentativi.append(node["id"])
                return node["id"]

            def wait_for(_handle):
                self._chiudi()
                return self.autopilot.ClosureEvent("N01")

            risultato = self.autopilot.start(self.ref, 1, retry_policy=policy).execute(
                launcher, wait_for=wait_for, now=lambda: 100.0,
                sleeper=lambda _seconds: None)

        self.assertEqual(("N01",), risultato.terminal_nodes)
        self.assertEqual(["N01"], tentativi)

    def test_riavvio_non_duplica_un_agente_con_claim_vivo(self):
        with self.mutate.editing(self.ref) as graph:
            node = graph.node("N01")
            node.update(status="claimed", assignee="Luna",
                        claim={"pid": 123, "identity": "Luna", "host": "host"})
        stato = self.retry.RetryState(self.ref.retry_state_path, self.ref.slug)
        stato.begin("N01", 100.0)
        run = self.autopilot.start(self.ref, 1)

        with mock.patch.object(self.autopilot.claims, "claim_state", return_value="live"):
            with self.assertRaises(self.autopilot.RunnerError):
                run.execute(lambda _run, _node: self.fail("agente duplicato"),
                            now=lambda: 100.0, sleeper=lambda _seconds: None)

    def test_resume_di_un_nuovo_run_riusa_retry_e_run_id(self):
        tentativi = []
        orologio = [100.0]
        policy = self.retry.RetryPolicy(max_attempts=3)

        def launcher(_run, node):
            tentativi.append(node["id"])
            return node["id"]

        def primo_wait(_handle):
            return self.autopilot.AgentOutcome("timeout", "provider timed out")

        def interrompi(_seconds):
            raise KeyboardInterrupt

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            primo = self.autopilot.start(self.ref, 1, retry_policy=policy)
            with self.assertRaises(KeyboardInterrupt):
                primo.execute(launcher, wait_for=primo_wait,
                              now=lambda: orologio[0], sleeper=interrompi)

            stato_parziale = json.loads(self.ref.run_state_path.read_text())
            self.assertEqual("waiting", stato_parziale["status"])
            self.assertEqual("pending", json.loads(
                self.ref.retry_state_path.read_text())["nodes"]["N01"]["status"])

            def secondo_wait(_handle):
                self._chiudi()
                return self.autopilot.ClosureEvent("N01")

            orologio[0] = 160.0
            ripreso = self.autopilot.start(self.ref, 1, retry_policy=policy)
            risultato = ripreso.execute(launcher, wait_for=secondo_wait,
                                         now=lambda: orologio[0],
                                         sleeper=lambda _seconds: None)

        self.assertEqual(("N01",), risultato.terminal_nodes)
        self.assertEqual(["N01", "N01"], tentativi)
        self.assertEqual(primo.run_state.run_id, ripreso.run_state.run_id)
        eventi = json.loads(self.ref.run_state_path.read_text())["events"]
        self.assertIn("run-resumed", [evento["type"] for evento in eventi])

    def test_resume_riconcilia_claim_scaduto_senza_record_retry(self):
        tentativi = []
        policy = self.retry.RetryPolicy(max_attempts=2, initial_delay=0)

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            self.claims.claim(self.ref, "N01")

            def launcher(_run, node):
                tentativi.append(node["id"])
                return node["id"]

            def wait_for(_handle):
                self._chiudi()
                return self.autopilot.ClosureEvent("N01")

            with mock.patch.object(self.autopilot.claims, "claim_state", return_value="dead"):
                risultato = self.autopilot.start(
                    self.ref, 1, retry_policy=policy).execute(
                        launcher, wait_for=wait_for, now=lambda: 100.0,
                        sleeper=lambda _seconds: None)

        self.assertEqual(("N01",), risultato.terminal_nodes)
        self.assertEqual(["N01"], tentativi)
        self.assertEqual({}, json.loads(self.ref.retry_state_path.read_text())["nodes"])
        eventi = json.loads(self.ref.run_state_path.read_text())["events"]
        self.assertIn("claim-reconciled", [evento["type"] for evento in eventi])

    def test_resume_non_avvia_un_claim_vivo_senza_record_retry(self):
        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            self.claims.claim(self.ref, "N01")
            run = self.autopilot.start(self.ref, 1)

            with mock.patch.object(self.autopilot.claims, "claim_state", return_value="live"):
                with self.assertRaises(self.autopilot.RunnerError):
                    run.execute(lambda _run, _node: self.fail("agente duplicato"),
                                now=lambda: 100.0,
                                sleeper=lambda _seconds: None)

        self.assertFalse(self.ref.retry_state_path.exists())
        self.assertEqual("claimed", self.store.load(self.ref.json_path)["nodes"][0]["status"])

    def test_un_ledger_di_un_altro_run_non_spende_il_budget_di_questo(self):
        """Il budget dei tentativi appartiene al run che li ha spesi.

        Regressione del 2026-09-01: un nodo esaurito il giorno prima lasciava un
        record 'terminal' che faceva morire in un secondo il run successivo, con
        una diagnosi che parlava di tentativi mai fatti in quella esecuzione.
        """
        vecchio = self.retry.RetryState(self.ref.retry_state_path, self.ref.slug, run_id="run-vecchio")
        vecchio.begin("N01", 100.0)
        vecchio.record_failure("N01", 8, "crash", "budget finito", 100.0, None)
        self.assertTrue(vecchio.terminal("N01"))

        nuovo = self.retry.RetryState(self.ref.retry_state_path, self.ref.slug, run_id="run-nuovo")

        self.assertFalse(nuovo.terminal("N01"))
        self.assertEqual(1, nuovo.begin("N01", 200.0))

    def test_resume_considera_chiuso_un_nodo_chiuso_durante_l_arresto(self):
        run = self.autopilot.start(self.ref, 1)
        run.run_state.start(1, ["N01"], 100.0)
        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            self.claims.claim(self.ref, "N01")
            stato_retry = self.retry.RetryState(self.ref.retry_state_path, self.ref.slug)
            stato_retry.begin("N01", 100.0)
            self._chiudi()

            ripreso = self.autopilot.start(self.ref, 1)
            risultato = ripreso.execute(
                lambda _run, _node: self.fail("nodo gia' chiuso rilanciato"),
                now=lambda: 100.0, sleeper=lambda _seconds: None)

        self.assertEqual((), risultato.terminal_nodes)
        self.assertEqual({}, json.loads(self.ref.retry_state_path.read_text())["nodes"])
        eventi = json.loads(self.ref.run_state_path.read_text())["events"]
        self.assertIn("node-reconciled-closed", [evento["type"] for evento in eventi])


if __name__ == "__main__":
    unittest.main()
