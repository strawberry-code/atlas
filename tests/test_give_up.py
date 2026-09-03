"""La resa (H01/2, H04): 'atlas give-up' dichiara un esito terminale, motivo scelto
da un elenco chiuso piu' un dettaglio libero obbligatorio. Qui si prova che il
comando scrive il record append-only e riapre il nodo come release(), che il
motivo fuori elenco e il dettaglio vuoto si rifiutano, e che il comando CLI
stampa motivo e id.
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "payload"))

from tests.test_motore import Base  # noqa: E402


class GiveUp(Base):
    def setUp(self):
        super().setUp()
        self.popola()
        self.claims.claim(self.ref, "F01")

    def _node(self, node_id="F01"):
        return self.model.node_of(self.store.load(self.ref.json_path), node_id)

    def test_riapre_il_nodo_e_scrive_il_record(self):
        node = self.claims.give_up(self.ref, "F01", "infeasible", "manca un servizio esterno")
        self.assertEqual("open", node["status"])
        self.assertIsNone(node["claim"])
        self.assertIsNone(node["assignee"])

        dati = self.store.load(self.ref.json_path)
        resa = dati["surrenders"][0]
        self.assertEqual("F01", resa["node"])
        self.assertEqual("infeasible", resa["reason"])
        self.assertEqual("manca un servizio esterno", resa["detail"])
        self.assertTrue(resa["id"].startswith("Y"))
        self.assertIn("at", resa)
        self.assertIn("by", resa)

    def test_id_progressivi(self):
        self.claims.give_up(self.ref, "F01", "infeasible", "primo motivo")
        self.claims.claim(self.ref, "F02", force=True)   # F02 e' ancora bloccato da F01
        self.claims.give_up(self.ref, "F02", "needs-redesign", "secondo motivo")
        dati = self.store.load(self.ref.json_path)
        self.assertEqual(["Y001", "Y002"], [r["id"] for r in dati["surrenders"]])

    def test_motivo_fuori_elenco_rifiutato(self):
        with self.assertRaises(self.store.StateError):
            self.claims.give_up(self.ref, "F01", "non-ce-la-faccio", "dettaglio")
        self.assertEqual("claimed", self._node()["status"], "un motivo invalido non deve toccare il nodo")

    def test_dettaglio_vuoto_rifiutato(self):
        with self.assertRaises(self.store.StateError):
            self.claims.give_up(self.ref, "F01", "infeasible", "   ")
        self.assertEqual("claimed", self._node()["status"])

    def test_nodo_non_rivendicato_rifiutato(self):
        with self.assertRaises(self.store.StateError):
            self.claims.give_up(self.ref, "F02", "infeasible", "dettaglio")


class GiveUpCLI(Base):
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
        codice, uscita = self._run(
            "give-up", "F01", "--motivo", "missing-resource", "-d", "serve una credenziale")
        self.assertEqual(0, codice)
        self.assertIn("F01", uscita)
        self.assertIn("missing-resource", uscita)

    def test_comando_rifiuta_un_motivo_fuori_elenco_in_fase_di_parsing(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self._run("give-up", "F01", "--motivo", "boh", "-d", "dettaglio")


if __name__ == "__main__":
    import unittest
    unittest.main()
