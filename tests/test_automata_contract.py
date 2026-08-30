"""Presidia il contratto pubblico di Atlas Automata.

Il runner viene implementato nei nodi successivi. Questo test tiene pero' stabile
la superficie normativa che quei nodi devono rispettare, evitando che i requisiti
di A01 restino soltanto nella prosa del ticket.
"""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "docs" / "atlas-automata-contract.md"


class AtlasAutomataContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = CONTRACT.read_text(encoding="utf-8")

    def test_il_contratto_esiste_con_encoding_utf8(self):
        self.assertIn("Versione del contratto: 1.", self.text)

    def test_presidia_i_confini_operativi(self):
        requisiti = (
            "non usa un LLM per scegliere i nodi",
            "frontiera Atlas è la sorgente di verità",
            "`parallelism=1` significa esecuzione strettamente seriale",
            "### 3. Ogni agente è AFK",
            "fuori sandbox e con bypass dei permessi",
            "Gli adapter sono un confine estensibile",
            "Terminazione valida",
            "Fuori ambito di questo contratto",
        )
        for requisito in requisiti:
            with self.subTest(requisito=requisito):
                self.assertIn(requisito, self.text)

    def test_presidia_le_condizioni_di_terminazione(self):
        condizioni = (
            "la frontiera Atlas è vuota",
            "non ci sono agenti attivi, claim ancora protetti o retry in attesa",
            "ogni nodo è terminale, cioè `closed` oppure `out-of-scope`",
            "non è sufficiente",
        )
        for condizione in condizioni:
            with self.subTest(condizione=condizione):
                self.assertIn(condizione, self.text)

    def test_presidia_il_rifiuto_del_parallelismo_invalido(self):
        self.assertIn(
            "deve essere rifiutato prima di avviare un agente", self.text)
        self.assertIn(
            "avvio rifiuta un `parallelism` mancante, non intero o non positivo",
            self.text)

    def test_presidia_diagnosi_e_retry(self):
        requisiti = (
            "Interpretare diagnosi e retry",
            "`active` significa",
            "da 60 secondi fino a 3600 secondi",
            "terminazione ambigua",
            "ritentabili",
            "Un claim vivo blocca il duplicato",
        )
        for requisito in requisiti:
            with self.subTest(requisito=requisito):
                self.assertIn(requisito, self.text)

    def test_presidia_la_superficie_cli_automata(self):
        for comando in ("atlas run --parallelism 1", "atlas run-status", "atlas run-log --tail 20"):
            with self.subTest(comando=comando):
                self.assertIn(comando, self.text)


if __name__ == "__main__":
    unittest.main()
