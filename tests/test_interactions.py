"""Schema e persistenza del ledger Interaction."""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SORGENTE = Path(__file__).resolve().parent.parent / "payload"
sys.path.insert(0, str(SORGENTE))


class InteractionsTest(unittest.TestCase):
    def setUp(self):
        from core import mutate
        from core.config import Workspace

        self.tmp = Path(tempfile.mkdtemp())
        self.ws = Workspace(self.tmp / ".atlas")
        self.ref = mutate.create_graph(self.ws, "prova", "Prova", "Verifica ledger")
        with mutate.editing(self.ref) as graph:
            mutate.add_node(graph, "A01", "Nodo", "A", "Domanda")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(SORGENTE))

    @staticmethod
    def actions():
        return [
            {"id": "confirm", "label": "Conferma", "effect": "resume"},
            {"id": "decline", "label": "Rifiuta", "effect": "cancel"},
        ]

    def test_apertura_persistente_auditabile_e_idempotente(self):
        from core import interactions, mutate
        from core.store import load

        with mock.patch.dict("os.environ", {"ATLAS_IDENTITY": "runner"}):
            with mutate.editing(self.ref) as graph:
                first = interactions.open_interaction(
                    graph, run_id="run-01", node_id="A01", event="decision-required",
                    summary="Serve una decisione per A01.", allowed_actions=self.actions(),
                    expires_at="2026-08-31T12:00:00+02:00", idempotency_key="run-01:A01:decision")
                again = interactions.open_interaction(
                    graph, run_id="run-01", node_id="A01", event="decision-required",
                    summary="Serve una decisione per A01.", allowed_actions=self.actions(),
                    expires_at="2026-08-31T12:00:00+02:00", idempotency_key="run-01:A01:decision")
        self.assertIs(first, again)
        record = load(self.ref.json_path)["interactions"][0]
        self.assertEqual("I001", record["id"])
        self.assertEqual(self.ref.slug, record["graph"])
        self.assertEqual("open", record["status"])
        self.assertEqual([{"at": record["createdAt"], "type": "opened", "by": "runner"}], record["events"])

    def test_stessa_chiave_con_richiesta_diversa_non_scrive(self):
        from core import interactions, mutate
        from core.store import StateError, load

        with mutate.editing(self.ref) as graph:
            interactions.open_interaction(graph, run_id="run-01", node_id="A01", event="decision-required",
                                          summary="Serve una decisione.", allowed_actions=self.actions(),
                                          expires_at="2026-08-31T12:00:00+02:00", idempotency_key="dedupe")
        with self.assertRaises(StateError):
            with mutate.editing(self.ref) as graph:
                interactions.open_interaction(graph, run_id="run-01", node_id="A01", event="decision-required",
                                              summary="Testo diverso.", allowed_actions=self.actions(),
                                              expires_at="2026-08-31T12:00:00+02:00", idempotency_key="dedupe")
        self.assertEqual(1, len(load(self.ref.json_path)["interactions"]))

    def test_schema_rifiuta_azione_o_scadenza_non_validi(self):
        from core import interactions, mutate
        from core.store import StateError

        with self.assertRaises(StateError):
            with mutate.editing(self.ref) as graph:
                interactions.open_interaction(graph, run_id="run-01", node_id="A01", event="decision-required",
                                              summary="Serve una decisione.",
                                              allowed_actions=[{"id": "shell", "label": "Shell", "effect": "bad"}],
                                              expires_at="domani", idempotency_key="invalid")


if __name__ == "__main__":
    unittest.main()
