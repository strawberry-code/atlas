"""Test del lato relay dell'avviso 'qualcosa e' cambiato' (E01) in
isolamento: RegistroPeer e costruisci_avviso. La traduzione HTTP (endpoint
/peers/notify) e' testata a parte in tests/test_relay.py (PeersNotifySulRelay),
qui non c'e' nessun server acceso.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "relay"))

import peers


class RegistroPeerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.registro = peers.RegistroPeer(Path(self.tmp.name) / "peers.json")

    def test_prima_installazione_non_trova_pari(self):
        pari = self.registro.osserva_e_ottieni_pari("codice-1", "mac-a")
        self.assertEqual(pari, [])

    def test_seconda_installazione_trova_la_prima(self):
        self.registro.osserva_e_ottieni_pari("codice-1", "mac-a")
        pari = self.registro.osserva_e_ottieni_pari("codice-1", "mac-b")
        self.assertEqual(pari, ["mac-a"])

    def test_non_torna_mai_se_stessa(self):
        self.registro.osserva_e_ottieni_pari("codice-1", "mac-a")
        pari = self.registro.osserva_e_ottieni_pari("codice-1", "mac-a")
        self.assertEqual(pari, [])

    def test_codici_diversi_non_si_vedono(self):
        self.registro.osserva_e_ottieni_pari("codice-1", "mac-a")
        pari = self.registro.osserva_e_ottieni_pari("codice-2", "mac-b")
        self.assertEqual(pari, [])

    def test_persiste_fra_due_istanze(self):
        self.registro.osserva_e_ottieni_pari("codice-1", "mac-a")
        rifatto = peers.RegistroPeer(self.registro._path)
        self.assertEqual(rifatto.osserva_e_ottieni_pari("codice-1", "mac-b"), ["mac-a"])


class CostruisciAvvisoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.registro = peers.RegistroPeer(Path(self.tmp.name) / "peers.json")
        self.chat_di = {"mac-a": 42}
        self.messaggi = []
        self.avvisa = peers.costruisci_avviso(
            self.registro, self.chat_di.get,
            lambda chat_id, testo: self.messaggi.append((chat_id, testo)))

    def test_nessun_pari_non_manda_nulla(self):
        self.avvisa("codice-1", "mac-a")
        self.assertEqual(self.messaggi, [])

    def test_avvisa_il_pari_gia_noto_col_testo_muto(self):
        self.avvisa("codice-1", "mac-a")
        self.avvisa("codice-1", "mac-b")
        self.assertEqual(self.messaggi, [(42, peers.TESTO_AVVISO)])

    def test_pari_senza_chat_associata_non_solleva_ne_manda(self):
        self.avvisa("codice-1", "mac-sconosciuta")
        self.avvisa("codice-1", "mac-b")   # mac-sconosciuta e' pari ma non ha chat
        self.assertEqual(self.messaggi, [])

    def test_un_pari_irraggiungibile_non_blocca_gli_altri(self):
        import urllib.error
        self.chat_di.update({"mac-a": 42, "mac-b": 43})

        def invia_a_scatti(chat_id, testo):
            if chat_id == 42:
                raise urllib.error.URLError("giu'")
            self.messaggi.append((chat_id, testo))

        avvisa = peers.costruisci_avviso(self.registro, self.chat_di.get, invia_a_scatti)
        avvisa("codice-1", "mac-a")
        avvisa("codice-1", "mac-b")
        avvisa("codice-1", "mac-c")   # avvisa sia mac-a (rotto) sia mac-b
        self.assertEqual(self.messaggi, [(43, peers.TESTO_AVVISO)])


if __name__ == "__main__":
    unittest.main()
