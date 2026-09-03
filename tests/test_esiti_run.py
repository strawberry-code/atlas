"""H07: il protocollo di esito (H01-H06) provato contro tre guasti veri.

Un run solo, tre nodi indipendenti, tre modi in cui un agente si perde: muore
dopo aver scritto la risposta, resta vivo senza produrre niente, si arrende.
Il pilota deve raccontarli in modo diverso su 'atlas run-status' e sul ledger,
e non deve sprecare tentativi dove ritentare non serve a niente.
"""
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


class TreGuastiVeri(unittest.TestCase):
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
        from core import autopilot, claims, config, docs, interactions, mutate, retry, store

        self.autopilot, self.claims, self.retry = autopilot, claims, retry
        self.docs, self.mutate, self.store, self.interactions = docs, mutate, store, interactions
        self.ws = config.workspace(self.tmp)
        self.ref = mutate.create_graph(self.ws, "prova", "Grafo", "Verificare il protocollo di esito.")
        with self.mutate.editing(self.ref) as graph:
            self.mutate.add_branch(graph, "B", "Runner", "#0f766e")
            for nodo_id in ("N01", "N02", "N03"):
                self.mutate.add_node(graph, nodo_id, nodo_id, "B", "esegui")
        self.docs.write_stubs(self.ref, self.store.load(self.ref.json_path))

    def tearDown(self):
        sys.path.remove(str(self.root))
        os.environ.pop("ATLAS_ROOT", None)
        for modulo in [m for m in sys.modules if m == "core" or m.startswith("core.")]:
            del sys.modules[modulo]
        shutil.rmtree(self.tmp)

    def _scrivi_risposta(self, node_id):
        path = self.ref.ticket_path(node_id)
        path.write_text(path.read_text(encoding="utf-8") + "\nLavoro svolto e scritto qui.\n",
                        encoding="utf-8")

    def _chiudi(self, node_id):
        self._scrivi_risposta(node_id)
        self.claims.close(self.ref, node_id, "eseguito", artifacts=[])

    def test_i_tre_guasti_producono_tre_esiti_distinti_senza_sprecare_tentativi(self):
        """Regressione del run del 2026-09-03: N01 e' il caso gia' noto (ticket
        scritto, chiusura mai chiamata, cinque tentativi identici sprecati prima
        di questo fix). N02 e N03 sono gli altri due guasti osservati lo stesso
        giorno, ciascuno col proprio esito."""
        from tests import waiter_risolutore

        tentativi = {"N01": 0, "N02": 0, "N03": 0}
        policy = self.retry.RetryPolicy(max_attempts=3, initial_delay=0)

        def launcher(_run, node):
            tentativi[node["id"]] += 1
            return node["id"]

        def wait_for(node_id):
            if node_id == "N01":
                # finisce il lavoro e muore prima di chiudere: la risposta e'
                # scritta nel ticket, 'atlas close' non arriva mai.
                self._scrivi_risposta("N01")
                return None
            if node_id == "N02":
                # resta vivo senza produrre niente: la stessa uccisione per
                # silenzio di H03 (providers.ProcessHandle), vista da qui come la
                # vedrebbe il pilota. E' un guasto transitorio vero: al secondo
                # giro l'agente si sveglia e chiude.
                if tentativi["N02"] == 1:
                    return self.autopilot.AgentOutcome(
                        "timeout", "no progress declared for 3600s: killed by the runner")
                self._chiudi("N02")
                return self.autopilot.ClosureEvent("N02")
            # N03: si arrende, con un motivo dichiarato (H01/2, H04).
            self.claims.give_up(self.ref, "N03", "infeasible",
                                "il vincolo dichiarato e' impossibile da rispettare")
            return None

        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "Luna"}), \
                self.assertRaises(self.autopilot.RunnerError):
            self.autopilot.start(self.ref, 1, retry_policy=policy).execute(
                launcher, wait_for=wait_for, sleeper=lambda _seconds: None,
                interaction_waiter=waiter_risolutore(self.ref, self.mutate, self.interactions))

        # Un solo tentativo dove ritentare non serve a niente: N01 (la risposta
        # c'e' gia', rifarla e' spreco) e N03 (l'agente ha gia' deciso). N02 e' un
        # guasto transitorio vero, e il budget lo ritenta finche' non chiude.
        self.assertEqual({"N01": 1, "N02": 2, "N03": 1}, tentativi)

        record = json.loads(self.ref.retry_state_path.read_text(encoding="utf-8"))["nodes"]
        self.assertEqual("terminal", record["N01"]["status"])
        self.assertEqual("orphaned-answer", record["N01"]["failure"])
        self.assertNotIn("N02", record, "chiuso: il ledger dei tentativi lo dimentica")
        self.assertEqual("terminal", record["N03"]["status"])
        self.assertEqual("surrendered", record["N03"]["failure"])

        stati = {n["id"]: n["status"] for n in self.store.load(self.ref.json_path)["nodes"]}
        self.assertEqual({"N01": "open", "N02": "closed", "N03": "open"}, stati)

        eventi = json.loads(self.ref.run_state_path.read_text(encoding="utf-8"))["events"]
        falliti = {e["node"]: e["failure"] for e in eventi if e["type"] == "attempt-failed"}
        self.assertEqual({"N01": "orphaned-answer", "N02": "timeout", "N03": "surrendered"}, falliti)
        self.assertIn("N01", [e["node"] for e in eventi if e["type"] == "work-not-lost"])
        self.assertNotIn("N02", [e["node"] for e in eventi if e["type"] == "work-not-lost"])

        # Leggibile in 'atlas run-status' (l'ultimo guasto dello snapshot) e nel
        # ledger (la cronologia intera, con i tre esiti ancora distinti).
        from core.cli import main

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, main(["run-status", "-g", self.ref.slug]))
        self.assertIn("stato=failed", output.getvalue())
        self.assertIn("failure=surrendered", output.getvalue())

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, main(["run-log", "-g", self.ref.slug]))
        log = output.getvalue()
        self.assertIn("failure=orphaned-answer", log)
        self.assertIn("failure=timeout", log)
        self.assertIn("failure=surrendered", log)
