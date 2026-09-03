"""D01: i tre comandi di stato lato client, la risposta che 'notify_telegram'
non porta (la card di un'Interazione) ma che qui si compone al volo dal
ledger locale (graph.json, run-state.json), sempre rispondendo con un
messaggio nuovo sulla chat di questa installazione."""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))

from core import interactions, mutate, relay_client, store, telegram_status
from core.config import Workspace
from core.run_state import RunState

INSTALLAZIONE = "la-macchina"


class TelegramStatusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.ws = Workspace(self.tmp / ".atlas")
        self.ref = mutate.create_graph(self.ws, "prova", "Il Progetto", "Verifica D01")
        with mutate.editing(self.ref) as graph:
            mutate.add_node(graph, "A01", "Primo nodo", "A", "Domanda")
        self.config = relay_client.TunnelConfig(base_url="https://relay.test", token="bearer")
        self.inviati = []

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _opener(self):
        def opener(richiesta, timeout=None):
            import json as _json

            class _Vuota:
                status = 200

                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    return False
            self.inviati.append(_json.loads(richiesta.data))
            return _Vuota()
        return opener

    def _gestore(self):
        return telegram_status.gestore(self.ref, INSTALLAZIONE, self.config, opener=self._opener())

    def _run_state(self) -> RunState:
        return RunState(self.ref.run_state_path, self.ref.slug)

    # --- routing dell'on_event ---

    def test_evento_non_message_ignorato(self):
        self._gestore()({"kind": "callback", "chat_id": 1, "text": "/stato"})
        self.assertEqual(self.inviati, [])

    def test_testo_non_nel_closed_set_ignorato(self):
        self._gestore()({"kind": "message", "chat_id": 1, "text": "ciao"})
        self.assertEqual(self.inviati, [])

    def test_comando_riconosciuto_manda_un_messaggio_nuovo_allinstallazione(self):
        self._gestore()({"kind": "message", "chat_id": 1, "text": "/stato"})
        self.assertEqual(len(self.inviati), 1)
        self.assertEqual(self.inviati[0]["installation"], INSTALLAZIONE)
        self.assertEqual(self.inviati[0]["buttons"], [])
        self.assertIn("Il Progetto", self.inviati[0]["text"])

    # --- /stato ---

    def test_stato_senza_run_ne_nodo_in_corso_mostra_la_frontiera(self):
        self._gestore()({"kind": "message", "chat_id": 1, "text": "/stato"})
        self.assertIn("A01", self.inviati[0]["text"])

    def test_stato_con_nodo_in_lavorazione_lo_nomina(self):
        stato = self._run_state()
        stato.start(1, ["A01"], time.time())
        stato.event("attempt-started", time.time(), status="active",
                    node="A01", provider="claude", attempt=1)
        self._gestore()({"kind": "message", "chat_id": 1, "text": "/stato"})
        self.assertIn("A01", self.inviati[0]["text"])
        self.assertIn("claude", self.inviati[0]["text"])

    def test_stato_senza_frontiera_ne_run_dice_fermo(self):
        with store.transaction(self.ref.json_path) as data:
            next(n for n in data["nodes"] if n["id"] == "A01")["status"] = store.CLOSED
        self._gestore()({"kind": "message", "chat_id": 1, "text": "/stato"})
        self.assertIn("1/1", self.inviati[0]["text"])
        self.assertIn("Nessun nodo prendibile", self.inviati[0]["text"])

    # --- /aspetta ---

    def test_aspetta_senza_interazioni_aperte(self):
        self._gestore()({"kind": "message", "chat_id": 1, "text": "/aspetta"})
        self.assertNotIn("A01", self.inviati[0]["text"])

    def test_aspetta_con_interazione_aperta_la_elenca(self):
        exp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() + 3600)) + "+00:00"
        with mutate.editing(self.ref) as graph:
            interactions.open_interaction(
                graph, run_id="run-01", node_id="A01", event="decision-required",
                summary="Serve una decisione.",
                allowed_actions=[{"id": "confirm", "label": "Conferma", "effect": "resume"}],
                expires_at=exp, idempotency_key="run-01:A01:decision")
        self._gestore()({"kind": "message", "chat_id": 1, "text": "/aspetta"})
        self.assertIn("A01", self.inviati[0]["text"])
        self.assertIn("Serve una decisione.", self.inviati[0]["text"])

    # --- /storto ---

    def test_storto_senza_run_mai_partito(self):
        self._gestore()({"kind": "message", "chat_id": 1, "text": "/storto"})
        self.assertNotIn("A01", self.inviati[0]["text"])

    def test_storto_run_attivo_senza_guasti_dice_niente_di_anomalo(self):
        stato = self._run_state()
        stato.start(1, ["A01"], time.time())
        self._gestore()({"kind": "message", "chat_id": 1, "text": "/storto"})
        self.assertNotIn("A01", self.inviati[0]["text"])

    def test_storto_con_attempt_failed_lo_mostra(self):
        stato = self._run_state()
        stato.start(1, ["A01"], time.time())
        stato.event("attempt-failed", time.time(), node="A01", attempt=1, failure="timeout")
        self._gestore()({"kind": "message", "chat_id": 1, "text": "/storto"})
        self.assertIn("A01", self.inviati[0]["text"])
        self.assertIn("timeout", self.inviati[0]["text"])


if __name__ == "__main__":
    unittest.main()
