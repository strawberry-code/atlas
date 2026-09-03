"""L'esito 'serve una persona' (H01/3, H05): 'atlas ask-human' sospende il nodo
sopra un'Interazione del ledger gia' esistente, invece di un canale nuovo. Qui si
prova che il comando apre la card giusta e rilascia il claim, che claim() rifiuta
di riprendere il nodo finche' la card resta aperta e lo lascia libero dopo la
risposta, che frontier()/waiting_human() si dividono il nodo correttamente, e che
il comando CLI stampa id e scadenza.
"""
from __future__ import annotations

import contextlib
import io
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "payload"))

from tests.test_motore import Base  # noqa: E402


class AskHuman(Base):
    def setUp(self):
        super().setUp()
        self.popola()
        self.claims.claim(self.ref, "F01")

    def _node(self, node_id="F01"):
        return self.model.node_of(self.store.load(self.ref.json_path), node_id)

    def test_sospende_il_nodo_e_apre_linterazione(self):
        record = self.claims.ask_human(self.ref, "F01", "Procedo con l'opzione A, confermi?")
        node = self._node()
        self.assertEqual("open", node["status"])
        self.assertIsNone(node["claim"])
        self.assertIsNone(node["assignee"])

        self.assertEqual("F01", record["nodeId"])
        self.assertEqual("human-needed", record["event"])
        self.assertEqual("open", record["status"])
        self.assertEqual("Procedo con l'opzione A, confermi?", record["summary"])
        azioni = {a["id"] for a in record["allowedActions"]}
        self.assertEqual({"confirm", "decline"}, azioni)

        dati = self.store.load(self.ref.json_path)
        self.assertEqual([record], dati["interactions"])

    def test_scadenza_e_la_finestra_condivisa_di_una_decisione(self):
        from core import interactions

        prima = datetime.now().astimezone()
        record = self.claims.ask_human(self.ref, "F01", "domanda")
        scadenza = datetime.fromisoformat(record["expiresAt"])
        self.assertGreaterEqual(scadenza - prima, interactions.SCADENZA_DECISIONE - timedelta(seconds=5))

    def test_domanda_vuota_rifiutata(self):
        with self.assertRaises(self.store.StateError):
            self.claims.ask_human(self.ref, "F01", "   ")
        self.assertEqual("claimed", self._node()["status"])

    def test_nodo_non_rivendicato_rifiutato(self):
        with self.assertRaises(self.store.StateError):
            self.claims.ask_human(self.ref, "F02", "domanda")

    def test_claim_rifiuta_di_riprendere_finche_la_card_e_aperta(self):
        self.claims.ask_human(self.ref, "F01", "domanda")
        with self.assertRaises(self.store.StateError):
            self.claims.claim(self.ref, "F01")
        node = self.claims.claim(self.ref, "F01", force=True)
        self.assertEqual("claimed", node["status"])

    def test_claim_torna_libero_dopo_la_risposta(self):
        from core import interactions

        record = self.claims.ask_human(self.ref, "F01", "domanda")
        with self.mutate.editing(self.ref) as g:
            interactions.resolve_interaction(g, record["id"], "confirm")
        node = self.claims.claim(self.ref, "F01")
        self.assertEqual("claimed", node["status"])

    def test_frontier_esclude_e_waiting_human_include(self):
        self.claims.ask_human(self.ref, "F01", "domanda")
        dati = self.store.load(self.ref.json_path)
        self.assertNotIn("F01", [n["id"] for n in self.model.frontier(dati)])
        self.assertNotIn("F01", [n["id"] for n in self.model.blocked(dati)])
        self.assertEqual(["F01"], [n["id"] for n in self.model.waiting_human(dati)])

    def test_id_progressivi_delle_interazioni(self):
        self.claims.ask_human(self.ref, "F01", "prima domanda")
        self.claims.claim(self.ref, "F02", force=True)   # F02 e' ancora bloccato da F01
        self.claims.ask_human(self.ref, "F02", "seconda domanda")
        dati = self.store.load(self.ref.json_path)
        self.assertEqual(["I001", "I002"], [i["id"] for i in dati["interactions"]])


class AskHumanCLI(Base):
    def setUp(self):
        super().setUp()
        self.popola()
        self.claims.claim(self.ref, "F01")

    def _run(self, *argv):
        from core import cli
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            codice = cli.main(list(argv))
        return codice, buffer.getvalue()

    def test_comando_scrive_e_stampa(self):
        codice, uscita = self._run("ask-human", "F01", "-q", "Procedo cosi', confermi?")
        self.assertEqual(0, codice)
        self.assertIn("F01", uscita)
        self.assertIn("I001", uscita)
        dati = self.store.load(self.ref.json_path)
        self.assertEqual("open", dati["nodes"][0]["status"])
        self.assertEqual("human-needed", dati["interactions"][0]["event"])

    def test_comando_rifiuta_domanda_mancante_in_fase_di_parsing(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self._run("ask-human", "F01")


if __name__ == "__main__":
    import unittest
    unittest.main()
