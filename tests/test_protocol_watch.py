"""Test dell'avviso di fine servizio per protocollo vecchio (E02): la
soglia di deprecazione in isolamento e il costruttore che parla con
Telegram tramite il pairing.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "relay"))

import protocol_watch


class AvvisoProtocolloTest(unittest.TestCase):
    def test_senza_soglia_non_avvisa_mai(self):
        avviso = protocol_watch.AvvisoProtocollo(soglia=None)
        self.assertFalse(avviso.da_avvisare("macchina-a", 1))

    def test_versione_sconosciuta_non_avvisa(self):
        avviso = protocol_watch.AvvisoProtocollo(soglia=2)
        self.assertFalse(avviso.da_avvisare("macchina-a", None))

    def test_versione_pari_o_sopra_soglia_non_avvisa(self):
        avviso = protocol_watch.AvvisoProtocollo(soglia=2)
        self.assertFalse(avviso.da_avvisare("macchina-a", 2))
        self.assertFalse(avviso.da_avvisare("macchina-a", 3))

    def test_versione_sotto_soglia_va_avvisata(self):
        avviso = protocol_watch.AvvisoProtocollo(soglia=2)
        self.assertTrue(avviso.da_avvisare("macchina-a", 1))

    def test_dopo_segna_avvisata_non_ripropone(self):
        avviso = protocol_watch.AvvisoProtocollo(soglia=2)
        self.assertTrue(avviso.da_avvisare("macchina-a", 1))
        avviso.segna_avvisata("macchina-a")
        self.assertFalse(avviso.da_avvisare("macchina-a", 1))

    def test_installazioni_diverse_non_si_influenzano(self):
        avviso = protocol_watch.AvvisoProtocollo(soglia=2)
        avviso.segna_avvisata("macchina-a")
        self.assertTrue(avviso.da_avvisare("macchina-b", 1))


class GestorePairingFinto:
    def __init__(self, chat_di=None):
        self._chat_di = chat_di or {}

    def chat_id_di(self, installation_id):
        return self._chat_di.get(installation_id)


class CostruisciAvvisoTest(unittest.TestCase):
    def test_manda_il_messaggio_e_marca_avvisata(self):
        messaggi = []
        avviso = protocol_watch.AvvisoProtocollo(soglia=2)
        store = GestorePairingFinto(chat_di={"macchina-a": 42})
        avvisa = protocol_watch.costruisci_avviso(
            avviso, store, lambda chat_id, testo: messaggi.append((chat_id, testo)))

        avvisa("macchina-a", 1)

        self.assertEqual(messaggi, [(42, protocol_watch.MESSAGGIO)])
        self.assertFalse(avviso.da_avvisare("macchina-a", 1))

    def test_seconda_chiamata_non_rimanda(self):
        messaggi = []
        avviso = protocol_watch.AvvisoProtocollo(soglia=2)
        store = GestorePairingFinto(chat_di={"macchina-a": 42})
        avvisa = protocol_watch.costruisci_avviso(
            avviso, store, lambda chat_id, testo: messaggi.append((chat_id, testo)))

        avvisa("macchina-a", 1)
        avvisa("macchina-a", 1)

        self.assertEqual(len(messaggi), 1)

    def test_versione_sopra_soglia_non_manda_nulla(self):
        messaggi = []
        avviso = protocol_watch.AvvisoProtocollo(soglia=2)
        store = GestorePairingFinto(chat_di={"macchina-a": 42})
        avvisa = protocol_watch.costruisci_avviso(
            avviso, store, lambda chat_id, testo: messaggi.append((chat_id, testo)))

        avvisa("macchina-a", 2)

        self.assertEqual(messaggi, [])

    def test_installazione_non_appaiata_non_manda_e_non_si_marca(self):
        messaggi = []
        avviso = protocol_watch.AvvisoProtocollo(soglia=2)
        store = GestorePairingFinto(chat_di={})
        avvisa = protocol_watch.costruisci_avviso(
            avviso, store, lambda chat_id, testo: messaggi.append((chat_id, testo)))

        avvisa("macchina-a", 1)

        self.assertEqual(messaggi, [])
        self.assertTrue(avviso.da_avvisare("macchina-a", 1))   # non perso: si riprova alla prossima


if __name__ == "__main__":
    unittest.main()
