"""Test di relay/view_command.py (D02): '/view' si ferma qui solo per
riconoscimento e instradamento, con la risposta 'non in linea' quando il
push non trova nessuna installazione o nessuna linea aperta. Stesso
principio di test_status_commands.py (D01)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "relay"))

import view_command


class CostruisciComandoView(unittest.TestCase):
    def setUp(self):
        self.push_chiamate = []
        self.messaggi = []

    def _comando(self, risolvi, push_esito=True):
        def _push(installation_id, evento):
            self.push_chiamate.append((installation_id, evento))
            return push_esito
        return view_command.costruisci_comando_view(
            risolvi, _push, lambda chat_id, testo: self.messaggi.append((chat_id, testo)))

    def test_testo_non_riconosciuto_torna_falso_e_non_tocca_niente(self):
        comando = self._comando(lambda chat_id: "la-macchina")
        self.assertFalse(comando("ciao", 42))
        self.assertFalse(comando("/stato", 42))
        self.assertEqual(self.push_chiamate, [])
        self.assertEqual(self.messaggi, [])

    def test_view_e_riconosciuto(self):
        comando = self._comando(lambda chat_id: "la-macchina")
        self.assertTrue(comando("/view", 42))

    def test_linea_aperta_spinge_levento_e_non_manda_offline(self):
        comando = self._comando(lambda chat_id: "la-macchina")
        self.assertTrue(comando("/view", 42))
        self.assertEqual(self.push_chiamate,
                         [("la-macchina", {"kind": "message", "chat_id": 42, "text": "/view"})])
        self.assertEqual(self.messaggi, [])

    def test_push_senza_linea_aperta_manda_offline(self):
        comando = self._comando(lambda chat_id: "la-macchina", push_esito=False)
        self.assertTrue(comando("/view", 42))
        self.assertEqual(self.messaggi, [(42, view_command.OFFLINE)])

    def test_nessuna_installazione_risolta_manda_offline_senza_pushare(self):
        comando = self._comando(lambda chat_id: None)
        self.assertTrue(comando("/view", 42))
        self.assertEqual(self.push_chiamate, [])
        self.assertEqual(self.messaggi, [(42, view_command.OFFLINE)])


if __name__ == "__main__":
    unittest.main()
