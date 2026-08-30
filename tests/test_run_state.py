"""Verifica il ledger durevole e atomico di Automata."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SORGENTE = Path(__file__).resolve().parent.parent / "payload"
sys.path.insert(0, str(SORGENTE))


class RunStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(SORGENTE))

    def test_eventi_e_snapshot_sopravvivono_al_riavvio(self):
        from core.run_state import RunState

        path = self.tmp / "run-state.json"
        stato = RunState(path, "grafo", run_id="run-01")
        stato.start(1, ["N01"], 100.0)
        stato.event("provider-selected", 101.0, node="N01", provider="codex-luna",
                    source="default", status="active")
        stato.event("backoff-scheduled", 102.0, node="N01", attempt=1,
                    next_at=162.0, status="waiting")

        riavviato = RunState(path, "grafo", run_id="run-01")
        riavviato.start(1, ["N01"], 200.0)
        dati = riavviato.snapshot()
        self.assertEqual("run-01", dati["run_id"])
        self.assertEqual("waiting", dati["status"])
        self.assertEqual(162.0, dati["next_at"])
        self.assertEqual(["run-started", "provider-selected", "backoff-scheduled"],
                         [evento["type"] for evento in dati["events"]])
        self.assertEqual(dati, json.loads(path.read_text(encoding="utf-8")))

    def test_ledger_corrotto_e_diagnosticato(self):
        from core.run_state import RunState, RunStateError

        path = self.tmp / "run-state.json"
        path.write_text("{}", encoding="utf-8")
        with self.assertRaises(RunStateError):
            RunState.read(path)


if __name__ == "__main__":
    unittest.main()
