"""Testa l'entry point di Automata e il suo parametro per-run."""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SORGENTE = Path(__file__).resolve().parent.parent / "payload"


class AutomataRun(unittest.TestCase):
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
        from core import automata, claims, config, docs, mutate, store

        self.automata, self.claims = automata, claims
        self.config, self.docs, self.mutate, self.store = config, docs, mutate, store
        self.ws = config.workspace(self.tmp)
        self.ref = mutate.create_graph(self.ws, "prova", "Grafo di prova", "Verificare il run.")

    def tearDown(self):
        sys.path.remove(str(self.root))
        os.environ.pop("ATLAS_ROOT", None)
        for modulo in [m for m in sys.modules if m == "core" or m.startswith("core.")]:
            del sys.modules[modulo]
        shutil.rmtree(self.tmp)

    def test_start_accetta_intero_positivo_e_lo_tiene_nel_run(self):
        run = self.automata.start(self.ref, 3)

        self.assertEqual(3, run.parallelism)
        self.assertFalse(run.serial)

    def test_uno_e_seriale(self):
        run = self.automata.start(self.ref, 1)

        self.assertTrue(run.serial)

    def test_start_rifiuta_valori_mancanti_non_interi_e_non_positivi(self):
        for valore in (None, 0, -1, 1.0, "1", True):
            with self.subTest(valore=valore), self.assertRaises(ValueError):
                self.automata.start(self.ref, valore)

    def test_start_non_scrive_il_parallelismo_nel_grafo(self):
        prima = json.loads(self.ref.json_path.read_text(encoding="utf-8"))

        self.automata.start(self.ref, 2)

        dopo = json.loads(self.ref.json_path.read_text(encoding="utf-8"))
        self.assertEqual(prima, dopo)
        self.assertNotIn("parallelism", dopo)

    def test_comando_run_richiede_parallelism_e_dichiara_la_serialita(self):
        from core import adapters, cli

        self._popola_frontiera(1)

        class Handle:
            def wait(inner_self):
                self._chiudi("N01")
                return adapters.AgentOutcome("closed")

        class Luna:
            identity = adapters.CODEX_LUNA

            def launch(inner_self, _context):
                return Handle()

        output = io.StringIO()
        with mock.patch.object(cli, "default_adapter_registry",
                               return_value=adapters.AdapterRegistry([Luna()])):
            with contextlib.redirect_stdout(output):
                codice = cli.main(["run", "-g", self.ref.slug, "--parallelism", "1"])

        self.assertEqual(0, codice)
        self.assertIn("parallelism=1", output.getvalue())
        self.assertIn("seriale", output.getvalue())
        stato = json.loads(self.ref.run_state_path.read_text(encoding="utf-8"))
        self.assertEqual("completed", stato["status"])
        self.assertEqual("closed", self.store.load(self.ref.json_path)["nodes"][0]["status"])

    def test_comando_run_rifiuta_parallelism_non_positivo(self):
        from core.cli import main

        with self.assertRaises(SystemExit) as errore:
            main(["run", "-g", self.ref.slug, "--parallelism", "0"])

        self.assertEqual(2, errore.exception.code)

    def test_comando_run_rifiuta_parallelism_mancante_o_non_intero(self):
        from core.cli import main

        for argomenti in ([], ["--parallelism", "1.5"]):
            with self.subTest(argomenti=argomenti), self.assertRaises(SystemExit) as errore:
                main(["run", "-g", self.ref.slug, *argomenti])
            self.assertEqual(2, errore.exception.code)

    def _popola_ciclo(self):
        with self.mutate.editing(self.ref) as g:
            self.mutate.add_branch(g, "B", "Runner", "#0f766e")
            self.mutate.add_node(g, "N01", "Primo", "B", "esegui")
            self.mutate.add_node(g, "N02", "Secondo", "B", "esegui", blockedBy=["N01"])
        self.docs.write_stubs(self.ref, self.store.load(self.ref.json_path))

    def _popola_frontiera(self, quanti=4):
        with self.mutate.editing(self.ref) as g:
            self.mutate.add_branch(g, "B", "Runner", "#0f766e")
            for indice in range(1, quanti + 1):
                self.mutate.add_node(g, f"N{indice:02d}", f"Nodo {indice}", "B", "esegui")
        self.docs.write_stubs(self.ref, self.store.load(self.ref.json_path))

    def _abilita_claim_paralleli(self, limite):
        (self.root / "config.json").write_text(
            json.dumps({"project": "prova", "agent": {"max_claims_per_session": limite}}),
            encoding="utf-8")

    def _risolutore(self):
        """Il waiter condiviso, legato al grafo di questo test."""
        from core import interactions

        from tests import waiter_risolutore

        return waiter_risolutore(self.ref, self.mutate, interactions)

    def _chiudi(self, node_id):
        path = self.ref.ticket_path(node_id)
        path.write_text(path.read_text(encoding="utf-8") + "\nRisposta eseguita.\n", encoding="utf-8")
        return self.claims.close(self.ref, node_id, "eseguito", artifacts=[])

    def test_execute_claima_frontiera_attende_chiusura_e_rilegge_prima_del_successivo(self):
        self._popola_ciclo()
        avvii, attese, stati = [], [], []

        def launcher(run, node):
            avvii.append(node["id"])
            stati.append(self.store.load(self.ref.json_path)["nodes"])
            return node["id"]

        def wait_for(node_id):
            attese.append(node_id)
            path = self.ref.ticket_path(node_id)
            path.write_text(path.read_text(encoding="utf-8") + "\nRisposta eseguita.\n", encoding="utf-8")
            self.claims.close(self.ref, node_id, "eseguito", artifacts=[])
            return self.automata.ClosureEvent(node_id)

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            risultato = self.automata.start(self.ref, 4).execute(launcher, wait_for)

        self.assertEqual(("N01", "N02"), risultato.terminal_nodes)
        self.assertEqual(["N01", "N02"], avvii)
        self.assertEqual(["N01", "N02"], attese)
        self.assertEqual("claimed", next(n for n in stati[0] if n["id"] == "N01")["status"])
        self.assertEqual("closed", next(n for n in stati[1] if n["id"] == "N01")["status"])

    def test_execute_deduplica_eventi_e_ignora_quelli_in_ritardo(self):
        self._popola_ciclo()
        avvii = []

        def launcher(run, node):
            avvii.append(node["id"])
            return node["id"]

        def wait_for(node_id):
            self._chiudi(node_id)
            if node_id == "N01":
                return (self.automata.ClosureEvent("N01"),
                        self.automata.ClosureEvent("N01"))
            return (self.automata.ClosureEvent("N01"),
                    self.automata.ClosureEvent("N02"))

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            risultato = self.automata.start(self.ref, 1).execute(launcher, wait_for)

        self.assertEqual(("N01", "N02"), risultato.terminal_nodes)
        self.assertEqual(["N01", "N02"], avvii)

    def test_execute_accetta_chiusura_da_atlas_anche_se_levento_manca(self):
        self._popola_ciclo()
        avvii = []

        def launcher(run, node):
            avvii.append(node["id"])
            return node["id"]

        def wait_for(node_id):
            self._chiudi(node_id)
            return None

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            risultato = self.automata.start(self.ref, 1).execute(launcher, wait_for)

        self.assertEqual(("N01", "N02"), risultato.terminal_nodes)
        self.assertEqual(["N01", "N02"], avvii)

    def test_execute_non_considera_levento_una_prova_di_chiusura(self):
        """L'evento non chiude: il nodo diventa ambiguo, non terminale."""
        from core import retry

        self._popola_ciclo()

        def wait_for(node_id):
            return self.automata.ClosureEvent(node_id)

        policy = retry.RetryPolicy(max_attempts=1, initial_delay=0)
        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}), self.assertRaises(self.automata.RunnerError):
            self.automata.start(self.ref, 1, retry_policy=policy).execute(
                lambda run, node: node["id"], wait_for,
                interaction_waiter=self._risolutore())

        # Il lucchetto torna giu': un nodo lasciato 'claimed' da un agente morto
        # non e' piu' prendibile da nessuno, nemmeno dal run successivo.
        self.assertEqual("open", self.store.load(self.ref.json_path)["nodes"][0]["status"])
        eventi = json.loads(self.ref.run_state_path.read_text(encoding="utf-8"))["events"]
        falliti = [e for e in eventi if e["type"] == "attempt-failed"]
        self.assertEqual(["ambiguous-termination"], [e["failure"] for e in falliti])
        self.assertIn("N01", falliti[0]["reason"])

    def test_resume_sullo_stesso_run_non_riavvia_un_nodo_terminale(self):
        self._popola_ciclo()
        avvii = []

        def launcher(run, node):
            avvii.append(node["id"])
            return node["id"]

        def wait_for(node_id):
            self._chiudi(node_id)

        run = self.automata.start(self.ref, 1)
        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            run.execute(launcher, wait_for)
            ripresa = run.execute(launcher, wait_for)

        self.assertEqual((), ripresa.terminal_nodes)
        self.assertEqual(["N01", "N02"], avvii)

    def test_execute_riempie_gli_slot_senza_superare_il_parallelismo(self):
        self._popola_frontiera()
        self._abilita_claim_paralleli(2)
        avvii, attese, stati = [], [], []
        attivi = 0
        massimo = 0

        def launcher(run, node):
            nonlocal attivi, massimo
            attivi += 1
            massimo = max(massimo, attivi)
            avvii.append(node["id"])
            stati.append({n["id"]: n["status"] for n in self.store.load(self.ref.json_path)["nodes"]})
            self.assertIsNotNone(node["claim"])
            return node["id"]

        def wait_for(node_id):
            nonlocal attivi
            attese.append(node_id)
            attivi -= 1
            path = self.ref.ticket_path(node_id)
            path.write_text(path.read_text(encoding="utf-8") + "\nRisposta eseguita.\n", encoding="utf-8")
            self.claims.close(self.ref, node_id, "eseguito", artifacts=[])

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            risultato = self.automata.start(self.ref, 2).execute(launcher, wait_for)

        self.assertEqual(("N01", "N02", "N03", "N04"), risultato.terminal_nodes)
        self.assertEqual(["N01", "N02", "N03", "N04"], avvii)
        self.assertEqual(avvii, attese)
        self.assertEqual(2, massimo)
        self.assertEqual("closed", stati[2]["N01"])
        self.assertEqual("claimed", stati[2]["N02"])

    def test_execute_non_avanza_se_il_launcher_non_chiude_il_nodo(self):
        from core import retry

        self._popola_ciclo()
        policy = retry.RetryPolicy(max_attempts=1, initial_delay=0)

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}), self.assertRaises(self.automata.RunnerError):
            self.automata.start(self.ref, 1, retry_policy=policy).execute(
                lambda run, node: None, interaction_waiter=self._risolutore())

        # N02 dipende da N01: nessuno dei due avanza, ma il lucchetto e' rilasciato.
        stati = {n["id"]: n["status"] for n in self.store.load(self.ref.json_path)["nodes"]}
        self.assertEqual({"N01": "open", "N02": "open"}, stati)

    def test_execute_persisti_stato_eventi_e_comandi_di_diagnosi(self):
        self._popola_ciclo()
        avvii = []

        def launcher(_run, node):
            avvii.append(node["id"])
            return node["id"]

        def wait_for(node_id):
            self._chiudi(node_id)
            return self.automata.ClosureEvent(node_id)

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            self.automata.start(self.ref, 1).execute(launcher, wait_for)

        stato = json.loads(self.ref.run_state_path.read_text(encoding="utf-8"))
        eventi = [evento["type"] for evento in stato["events"]]
        self.assertEqual("completed", stato["status"])
        self.assertEqual(["N01", "N02"], avvii)
        for tipo in ("run-started", "node-claimed", "attempt-started", "attempt-waiting",
                     "node-closed", "frontier-updated", "run-completed"):
            self.assertIn(tipo, eventi)

        from core.cli import main

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, main(["run-status", "-g", self.ref.slug]))
        self.assertIn("stato=completed", output.getvalue())
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, main(["run-log", "-g", self.ref.slug, "--tail", "2"]))
        self.assertIn("run-completed", output.getvalue())

    def test_execute_persisti_provider_e_fallback(self):
        from core import adapters

        self._popola_frontiera(1)

        class OutcomeHandle:
            def __init__(self, outcome):
                self.outcome = outcome

            def wait(self):
                return self.outcome

        class Luna:
            identity = adapters.CODEX_LUNA

            def launch(self, _context):
                return OutcomeHandle(adapters.AgentOutcome("provider-unavailable", "offline"))

        class Claude:
            identity = adapters.CLAUDE

            def launch(self, _context):
                return OutcomeHandle(adapters.AgentOutcome("closed"))

        def wait_for(handle):
            self._chiudi("N01")
            return handle.wait()

        registry = adapters.AdapterRegistry([Luna(), Claude()])
        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            self.automata.start(self.ref, 1).execute(
                self.automata.launcher_from_registry(registry), wait_for)

        eventi = json.loads(self.ref.run_state_path.read_text(encoding="utf-8"))["events"]
        tipi = [evento["type"] for evento in eventi]
        self.assertEqual(2, tipi.count("provider-selected"))
        self.assertIn("fallback", tipi)
        selezioni = [evento for evento in eventi if evento["type"] == "provider-selected"]
        self.assertEqual(["codex-luna", "claude"], [evento["provider"] for evento in selezioni])

    def test_il_claim_del_runner_porta_lidentita_del_provider(self):
        """Il lucchetto nomina chi lavorera' il nodo, non chi lo ha preso.

        Regressione del run del 2026-08-30: il claim del runner portava identita'
        '?' e assignee 'claude' mentre lavorava Codex, e l' 'atlas take' del figlio
        trovava il proprio nodo tenuto da uno sconosciuto.
        """
        from core import adapters

        self._popola_frontiera(1)
        visti = {}

        class Handle:
            def wait(inner_self):
                nodo = self.store.load(self.ref.json_path)["nodes"][0]
                visti["identity"] = nodo["claim"]["identity"]
                visti["assignee"] = nodo["assignee"]
                # Il figlio disobbedisce al briefing e prende il nodo lo stesso:
                # con l'identita' giusta e' un rinnovo, non un conflitto.
                with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": adapters.CODEX_LUNA}):
                    visti["ripreso"] = self.claims.claim(self.ref, "N01")["status"]
                    self._chiudi("N01")
                return adapters.AgentOutcome("closed")

        class Luna:
            identity = adapters.CODEX_LUNA

            def launch(inner_self, _context):
                return Handle()

        registry = adapters.AdapterRegistry([Luna()])
        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "runner"}):
            risultato = self.automata.start(self.ref, 1).execute(
                self.automata.launcher_from_registry(registry), lambda handle: handle.wait())

        self.assertEqual(("N01",), risultato.terminal_nodes)
        self.assertEqual(adapters.CODEX_LUNA, visti["identity"])
        self.assertEqual(adapters.CODEX_LUNA, visti["assignee"])
        self.assertEqual("claimed", visti["ripreso"])

    def test_quota_finita_su_luna_passa_a_claude_e_riassegna_il_lucchetto(self):
        """Regressione del run del 2026-08-31.

        Codex esauriva la quota fino al mese dopo e Automata ritentava lo stesso
        provider otto volte, mentre il fallback a Claude, promesso a ogni avvio,
        non scattava perche' l'uscita valeva come errore del lavoro.
        """
        from core import adapters

        self._popola_frontiera(1)
        visti = {}

        class Handle:
            def __init__(inner, outcome):
                inner.outcome = outcome

            def wait(inner):
                return inner.outcome

        class Luna:
            identity = adapters.CODEX_LUNA

            def launch(inner, _context):
                return Handle(adapters.AgentOutcome(
                    "provider-unavailable",
                    "ERROR: You've hit your usage limit. Upgrade to Plus, "
                    "or try again at Sep 30th, 2026 9:35 AM."))

        class Claude:
            identity = adapters.CLAUDE

            def launch(inner, _context):
                visti["lanciato"] = True
                self._chiudi("N01")
                return Handle(adapters.AgentOutcome("closed"))

        registry = adapters.AdapterRegistry([Luna(), Claude()])
        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "runner"}):
            risultato = self.automata.start(self.ref, 1).execute(
                self.automata.launcher_from_registry(registry), lambda handle: handle.wait())

        self.assertEqual(("N01",), risultato.terminal_nodes)
        self.assertTrue(visti["lanciato"], "il fallback non ha lanciato Claude")
        eventi = json.loads(self.ref.run_state_path.read_text(encoding="utf-8"))["events"]
        self.assertEqual(1, sum(e["type"] == "fallback" for e in eventi))
        # Nessun tentativo bruciato: la quota finita non e' un guasto da ritentare
        # sullo stesso provider, e questo e' il punto della regressione.
        self.assertEqual(0, sum(e["type"] == "attempt-failed" for e in eventi))
        self.assertEqual(adapters.CLAUDE, [e["provider"] for e in eventi
                                           if e["type"] == "provider-selected"][-1])

    def test_un_nodo_che_non_si_chiude_non_ferma_gli_altri_rami(self):
        """Il budget esaurito e' del nodo, non del run.

        Regressione del run del 2026-08-30: A04 non si e' chiuso e il run e' morto
        li', lasciando intatti B01 e C01 che non dipendevano da lui.
        """
        from core import retry

        self._popola_frontiera(3)
        policy = retry.RetryPolicy(max_attempts=1, initial_delay=0)

        def wait_for(node_id):
            if node_id != "N02":
                self._chiudi(node_id)

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}), self.assertRaises(
                self.automata.RunnerError) as errore:
            self.automata.start(self.ref, 1, retry_policy=policy).execute(
                lambda run, node: node["id"], wait_for,
                interaction_waiter=self._risolutore())

        self.assertIn("N02", str(errore.exception))
        stati = {n["id"]: n["status"] for n in self.store.load(self.ref.json_path)["nodes"]}
        self.assertEqual({"N01": "closed", "N02": "open", "N03": "closed"}, stati)
        stato = json.loads(self.ref.run_state_path.read_text(encoding="utf-8"))
        self.assertEqual("failed", stato["status"])
        self.assertEqual(["N02"], [e["node"] for e in stato["events"]
                                   if e["type"] == "node-exhausted"])

    def test_una_chiusura_registrata_vale_anche_se_lagente_esce_male(self):
        """Il grafo e' la verita' in entrambi i versi.

        Un exit status zero non chiude niente da solo, e un'uscita storta non
        cancella una chiusura gia' registrata: buttare quel lavoro significava
        rifare da capo un nodo gia' fatto.
        """
        from core import adapters

        self._popola_frontiera(1)

        def wait_for(node_id):
            self._chiudi(node_id)
            return adapters.AgentOutcome("error", "exit status 1")

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}):
            risultato = self.automata.start(self.ref, 1).execute(
                lambda run, node: node["id"], wait_for)

        self.assertEqual(("N01",), risultato.terminal_nodes)
        self.assertEqual("closed", self.store.load(self.ref.json_path)["nodes"][0]["status"])

    def test_un_agente_che_molla_il_nodo_non_fa_morire_il_run(self):
        """release alza sul nodo non rivendicato: non deve uscire dal ciclo."""
        from core import retry

        self._popola_frontiera(2)
        policy = retry.RetryPolicy(max_attempts=1, initial_delay=0)

        def wait_for(node_id):
            if node_id == "N01":
                self.claims.release(self.ref, "N01")   # l'agente disobbedisce e molla
            else:
                self._chiudi(node_id)

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}), self.assertRaises(
                self.automata.RunnerError) as errore:
            self.automata.start(self.ref, 1, retry_policy=policy).execute(
                lambda run, node: node["id"], wait_for,
                interaction_waiter=self._risolutore())

        self.assertIn("N01", str(errore.exception))
        stati = {n["id"]: n["status"] for n in self.store.load(self.ref.json_path)["nodes"]}
        self.assertEqual({"N01": "open", "N02": "closed"}, stati)

    def test_un_avviso_di_guasto_scade_prima_di_una_decisione_umana(self):
        """La finestra della card dipende da cosa chiede.

        Un run notturno che si ferma non deve tenere occupato un terminale fino al
        giorno dopo per un avviso che nessuno sta guardando, mentre una decisione
        umana puo' aspettare la giornata di chi deve prenderla.
        """
        from datetime import datetime

        guasto = datetime.fromisoformat(self.automata._scadenza(1000.0, "run-stopped"))
        decisione = datetime.fromisoformat(self.automata._scadenza(1000.0, "decision-required"))
        base = datetime.fromtimestamp(1000.0).astimezone().replace(microsecond=0)

        self.assertEqual(self.automata.SCADENZA_GUASTO, guasto - base)
        self.assertEqual(self.automata.SCADENZA_DECISIONE, decisione - base)
        self.assertLess(guasto, decisione)

    def test_una_interazione_che_nessuno_raccoglie_scade_e_non_appende_il_run(self):
        """Un run AFK non puo' restare fermo su una domanda che nessuno vede.

        La coda degli eventi vive in memoria di processo: una risposta scritta nel
        grafo da un altro comando non la pubblica nessuno qui, quindi senza la
        scadenza della card il runner aspetterebbe per sempre, in silenzio.
        """
        from core import retry

        self._popola_frontiera(1)
        scadute = []

        def nessuna_risposta(graph, run_id, timeout=None):
            # Nessuno raccoglie la card: la porto oltre la sua scadenza, come
            # farebbe il tempo in un run notturno, e non pubblico nessun evento.
            with self.mutate.editing(self.ref) as state:
                for card in state.data["interactions"]:
                    if card["status"] == "open":
                        card["expiresAt"] = "2020-01-01T00:00:00+01:00"
                        scadute.append(card["id"])
            return None

        policy = retry.RetryPolicy(max_attempts=1, initial_delay=0)
        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}), self.assertRaises(
                self.automata.RunnerError):
            self.automata.start(self.ref, 1, retry_policy=policy).execute(
                lambda run, node: None, interaction_waiter=nessuna_risposta)

        self.assertTrue(scadute, "il runner non ha nemmeno aperto la card")
        card = self.store.load(self.ref.json_path)["interactions"][0]
        self.assertEqual("expired", card["status"])
        eventi = json.loads(self.ref.run_state_path.read_text(encoding="utf-8"))["events"]
        self.assertIn("interaction-closed", [e["type"] for e in eventi])

    def test_execute_apre_una_interazione_hitl_e_si_risveglia_sulla_risposta(self):
        from core import interactions

        with self.mutate.editing(self.ref) as g:
            self.mutate.add_node(g, "H01", "Domanda umana", "A", "decidere", mode="HITL")
        self.docs.write_stubs(self.ref, self.store.load(self.ref.json_path))

        def answer(graph, run_id, timeout=None):
            with self.mutate.editing(self.ref) as state:
                card = next(item for item in state.data["interactions"]
                            if item["graph"] == graph and item["runId"] == run_id)
                interactions.resolve_interaction(state, card["id"], "confirm")
            return interactions.wait_for_resolution(graph, run_id)

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}), self.assertRaises(self.automata.RunnerError):
            self.automata.start(self.ref, 1).execute(lambda run, node: None,
                                                     interaction_waiter=answer)

        self.assertEqual("open", self.store.load(self.ref.json_path)["nodes"][0]["status"])
        card = self.store.load(self.ref.json_path)["interactions"][0]
        self.assertEqual(("decision-required", "resolved"), (card["event"], card["status"]))


if __name__ == "__main__":
    unittest.main()
