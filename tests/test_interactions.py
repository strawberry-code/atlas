"""Schema e persistenza del ledger Interaction."""
from __future__ import annotations

import shutil
import sys
import tempfile
import threading
import time
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

    def test_risoluzione_applica_solo_una_capability_dichiarata_e_la_audita(self):
        from core import interactions, mutate
        from core.store import StateError, load

        with mock.patch.dict("os.environ", {"ATLAS_IDENTITY": "persona"}):
            with mutate.editing(self.ref) as graph:
                opened = interactions.open_interaction(
                    graph, run_id="run-01", node_id="A01", event="decision-required",
                    summary="Serve una decisione.", allowed_actions=self.actions(),
                    expires_at="2026-08-31T12:00:00+02:00", idempotency_key="resolve")
                resolved = interactions.resolve_interaction(graph, opened["id"], "confirm")

        self.assertEqual("resolved", resolved["status"])
        self.assertEqual({"action": "confirm", "effect": "resume"}, resolved["resolution"])
        self.assertEqual(["opened", "resolved"], [event["type"] for event in resolved["events"]])
        self.assertEqual("persona", resolved["events"][-1]["by"])
        with self.assertRaises(StateError):
            with mutate.editing(self.ref) as graph:
                interactions.resolve_interaction(graph, opened["id"], "decline")
        self.assertEqual("open", load(self.ref.json_path)["nodes"][0]["status"])

    def test_rifiuta_azione_non_dichiarata_senza_modificare_il_ledger(self):
        from core import interactions, mutate
        from core.store import StateError, load

        with mutate.editing(self.ref) as graph:
            opened = interactions.open_interaction(
                graph, run_id="run-01", node_id="A01", event="decision-required",
                summary="Serve una decisione.", allowed_actions=self.actions(),
                expires_at="2026-08-31T12:00:00+02:00", idempotency_key="reject")
        with self.assertRaises(StateError):
            with mutate.editing(self.ref) as graph:
                interactions.resolve_interaction(graph, opened["id"], "retry")
        record = load(self.ref.json_path)["interactions"][0]
        self.assertEqual("open", record["status"])
        self.assertEqual(["opened"], [event["type"] for event in record["events"]])

    def test_annullamento_e_scadenza_sono_transazioni_auditate(self):
        from core import interactions, mutate
        from core.store import load

        with mock.patch("core.interactions._now", return_value="2026-08-31T10:00:00+02:00"):
            with mutate.editing(self.ref) as graph:
                cancelled = interactions.open_interaction(
                    graph, run_id="run-01", node_id="A01", event="decision-required",
                    summary="Serve una decisione.", allowed_actions=self.actions(),
                    expires_at="2026-08-31T12:00:00+02:00", idempotency_key="cancel")
                expired = interactions.open_interaction(
                    graph, run_id="run-01", node_id="A01", event="decision-required",
                    summary="Serve una decisione.", allowed_actions=self.actions(),
                    expires_at="2026-08-31T11:00:00+02:00", idempotency_key="expire")
                interactions.cancel_interaction(graph, cancelled["id"])
        with mock.patch("core.interactions._now", return_value="2026-08-31T12:00:01+02:00"):
            with mutate.editing(self.ref) as graph:
                self.assertEqual([expired["id"]], [record["id"] for record in interactions.expire_interactions(graph)])

        records = {record["id"]: record for record in load(self.ref.json_path)["interactions"]}
        self.assertEqual("cancelled", records[cancelled["id"]]["status"])
        self.assertEqual(["opened", "cancelled"], [event["type"] for event in records[cancelled["id"]]["events"]])
        self.assertEqual("expired", records[expired["id"]]["status"])
        self.assertEqual(["opened", "expired"], [event["type"] for event in records[expired["id"]]["events"]])

    def test_schema_rifiuta_una_risoluzione_con_forma_non_auditabile(self):
        from core import interactions, mutate
        from core.store import StateError

        with self.assertRaises(StateError):
            with mutate.editing(self.ref) as graph:
                opened = interactions.open_interaction(
                    graph, run_id="run-01", node_id="A01", event="decision-required",
                    summary="Serve una decisione.", allowed_actions=self.actions(),
                    expires_at="2026-08-31T12:00:00+02:00", idempotency_key="malformed")
                interactions.resolve_interaction(graph, opened["id"], "confirm")["resolution"] = ["action", "effect"]

    def test_risoluzione_pubblica_un_evento_solo_dopo_il_commit(self):
        from core import interactions, mutate

        with mutate.editing(self.ref) as graph:
            opened = interactions.open_interaction(
                graph, run_id="run-01", node_id="A01", event="decision-required",
                summary="Serve una decisione.", allowed_actions=self.actions(),
                expires_at="2026-08-31T12:00:00+02:00", idempotency_key="wake")

        received = []
        waiter = threading.Thread(
            target=lambda: received.append(interactions.wait_for_resolution(self.ref.slug, "run-01")))
        waiter.start()
        with mutate.editing(self.ref) as graph:
            interactions.resolve_interaction(graph, opened["id"], "confirm")
        waiter.join(timeout=1)

        self.assertFalse(waiter.is_alive())
        self.assertEqual(opened["id"], received[0].interaction_id)

    def test_attesa_con_scadenza_torna_senza_evento_invece_di_bloccare(self):
        """Chi aspetta deve poter tornare a guardare il grafo.

        La coda degli eventi vive in memoria di processo: una risposta scritta nel
        grafo da un altro comando non arriva mai qui, e un'attesa senza scadenza
        terrebbe fermo un run AFK per sempre.
        """
        from core import interactions

        inizio = time.monotonic()
        evento = interactions.wait_for_resolution(self.ref.slug, "run-senza-risposta",
                                                  timeout=0.05)

        self.assertIsNone(evento)
        self.assertLess(time.monotonic() - inizio, 2.0)

    def test_una_card_aperta_e_scaduta_si_riconosce_dal_suo_record(self):
        from core import interactions

        aperta = {"status": "open", "expiresAt": "2020-01-01T00:00:00+01:00"}
        futura = {"status": "open", "expiresAt": "2099-01-01T00:00:00+01:00"}
        risolta = {"status": "resolved", "expiresAt": "2020-01-01T00:00:00+01:00"}

        self.assertTrue(interactions.is_expired(aperta))
        self.assertFalse(interactions.is_expired(futura))
        self.assertFalse(interactions.is_expired(risolta))


if __name__ == "__main__":
    unittest.main()
