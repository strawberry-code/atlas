"""Proiezione del ledger Interaction per la dashboard."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path


SORGENTE = Path(__file__).resolve().parent.parent / "payload"
sys.path.insert(0, str(SORGENTE))


class InteractionsViewTest(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(SORGENTE))

    @staticmethod
    def _record(**over):
        base = {
            "id": "I001", "graph": "prova", "runId": "run-01", "nodeId": "A01",
            "event": "decision-required", "summary": "Serve una decisione per A01.",
            "allowedActions": [
                {"id": "confirm", "label": "Conferma", "effect": "resume"},
                {"id": "decline", "label": "Rifiuta", "effect": "cancel"},
            ],
            "expiresAt": "2026-08-31T12:00:00+02:00",
            "idempotencyKey": "run-01:A01:decision", "status": "open",
            "createdAt": "2026-08-31T11:45:00+02:00", "updatedAt": "2026-08-31T11:45:00+02:00",
            "resolution": None,
            "events": [{"at": "2026-08-31T11:45:00+02:00", "type": "opened", "by": "runner"}],
        }
        base.update(over)
        return base

    def test_proietta_solo_i_campi_minimi_dal_record(self):
        from core import interactions_view

        momento = datetime.fromisoformat("2026-08-31T11:50:00+02:00")
        data = {"interactions": [self._record()]}

        [voce] = interactions_view.project(data, now=momento)

        self.assertEqual(
            {"id", "node", "run", "status", "summary", "age", "urgency", "resolvedAge", "allowedActions"},
            set(voce))
        self.assertEqual("I001", voce["id"])
        self.assertEqual("A01", voce["node"])
        self.assertEqual("run-01", voce["run"])
        self.assertEqual("open", voce["status"])
        self.assertEqual("Serve una decisione per A01.", voce["summary"])
        self.assertEqual(timedelta(minutes=5), voce["age"])
        self.assertEqual(timedelta(minutes=10), voce["urgency"])
        self.assertIsNone(voce["resolvedAge"])
        self.assertEqual(
            [{"id": "confirm", "label": "Conferma"}, {"id": "decline", "label": "Rifiuta"}],
            voce["allowedActions"],
        )

    def test_urgenza_negativa_quando_la_scadenza_e_gia_passata(self):
        from core import interactions_view

        momento = datetime.fromisoformat("2026-08-31T13:00:00+02:00")
        data = {"interactions": [self._record()]}

        [voce] = interactions_view.project(data, now=momento)

        self.assertEqual(timedelta(hours=-1), voce["urgency"])

    def test_una_card_terminale_non_ha_urgenza_ma_conserva_leta(self):
        from core import interactions_view

        momento = datetime.fromisoformat("2026-08-31T12:30:00+02:00")
        record = self._record(status="resolved", resolution={"action": "confirm", "effect": "resume"},
                              updatedAt="2026-08-31T12:00:00+02:00",
                              events=[
                                  {"at": "2026-08-31T11:45:00+02:00", "type": "opened", "by": "runner"},
                                  {"at": "2026-08-31T12:00:00+02:00", "type": "resolved", "by": "persona"},
                              ])
        data = {"interactions": [record]}

        [voce] = interactions_view.project(data, now=momento)

        self.assertEqual("resolved", voce["status"])
        self.assertIsNone(voce["urgency"])
        self.assertEqual(timedelta(minutes=45), voce["age"])
        self.assertEqual(timedelta(minutes=30), voce["resolvedAge"])

    def test_nessuna_interaction_nel_grafo_produce_lista_vuota(self):
        from core import interactions_view

        self.assertEqual([], interactions_view.project({}))
        self.assertEqual([], interactions_view.project({"interactions": []}))

    def test_non_rilegge_la_sequenza_events_per_derivare_lo_stato(self):
        """Il record dichiara gia' status e scadenza: 'events' resta un audit
        di sola consultazione, non una fonte da rigiocare per lo stato mostrato."""
        from core import interactions_view

        momento = datetime.fromisoformat("2026-08-31T11:50:00+02:00")
        record = self._record(events="questo campo non deve essere letto dalla proiezione")

        [voce] = interactions_view.project({"interactions": [record]}, now=momento)

        self.assertEqual("open", voce["status"])

    def test_events_of_espone_il_log_di_una_sola_interaction_su_richiesta(self):
        from core import interactions_view

        altra = self._record(id="I002", idempotencyKey="run-01:A01:altra")
        data = {"interactions": [self._record(), altra]}

        self.assertEqual([{"at": "2026-08-31T11:45:00+02:00", "type": "opened", "by": "runner"}],
                         interactions_view.events_of(data, "I001"))

    def test_events_of_senza_la_interaction_torna_lista_vuota(self):
        from core import interactions_view

        self.assertEqual([], interactions_view.events_of({"interactions": []}, "I999"))
        self.assertEqual([], interactions_view.events_of({}, "I999"))


if __name__ == "__main__":
    unittest.main()
