"""Il codice opaco di progetto (E01): genera una volta, persiste in
config.json senza toccare il resto del file, e resta identico a ogni
rilettura successiva - la proprieta' che lo rende 'uguale su tutte le copie'
una volta committato.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SORGENTE = Path(__file__).resolve().parent.parent / "payload"


class ProjectCodeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(SORGENTE))
        from core import project_code
        from core.config import Workspace
        cls.project_code = project_code
        cls.Workspace = Workspace

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(SORGENTE))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / ".atlas"
        self.root.mkdir()
        self.ws = self.Workspace(self.root)

    def _scrivi_config(self, dati: dict) -> None:
        (self.root / "config.json").write_text(json.dumps(dati), encoding="utf-8")

    def test_genera_una_stringa_non_banale(self):
        codice = self.project_code.genera()
        self.assertIsInstance(codice, str)
        self.assertGreaterEqual(len(codice), 16)

    def test_senza_config_json_ne_crea_uno_col_solo_codice(self):
        codice = self.project_code.carica_o_crea(self.ws)
        dati = json.loads((self.root / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(dati, {"projectCode": codice})

    def test_config_json_esistente_prende_il_codice_senza_toccare_le_altre_chiavi(self):
        self._scrivi_config({"project": "prova", "language": "it"})
        codice = self.project_code.carica_o_crea(self.ws)
        dati = json.loads((self.root / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(dati, {"project": "prova", "language": "it", "projectCode": codice})

    def test_codice_gia_presente_non_si_rigenera(self):
        self._scrivi_config({"project": "prova", "projectCode": "gia-qui"})
        self.assertEqual(self.project_code.carica_o_crea(self.ws), "gia-qui")

    def test_due_letture_successive_tornano_lo_stesso_codice(self):
        primo = self.project_code.carica_o_crea(self.ws)
        secondo = self.project_code.carica_o_crea(self.ws)
        self.assertEqual(primo, secondo)


if __name__ == "__main__":
    unittest.main()
