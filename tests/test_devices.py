"""Test dell'elenco dei computer collegati e del distacco (C02): la
formattazione di 'quanto tempo fa', il comando '/computer' e il tap
'Stacca'. Nessuna rete reale: 'invia_messaggio'/'invia_bottoni'/
'modifica_messaggio' sono sempre doppi finti che raccolgono le chiamate.
"""
from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "relay"))

import devices
import pairing


class FaQuantoTest(unittest.TestCase):
    def test_pochi_secondi(self):
        self.assertEqual(devices._fa_quanto(5), "pochi istanti fa")

    def test_minuti(self):
        self.assertEqual(devices._fa_quanto(120), "2 minuti fa")

    def test_un_minuto_singolare(self):
        self.assertEqual(devices._fa_quanto(60), "1 minuto fa")

    def test_ore(self):
        self.assertEqual(devices._fa_quanto(3 * 3600), "3 ore fa")

    def test_giorni(self):
        self.assertEqual(devices._fa_quanto(5 * 86400), "5 giorni fa")

    def test_mesi(self):
        self.assertEqual(devices._fa_quanto(90 * 86400), "3 mesi fa")


class CostruisciComandoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        self.messaggi = []
        self.bottoni = []
        self.scarto = 0.0   # secondi aggiunti al clock vero, per simulare "tempo passato"
        self.elenca = devices.costruisci_comando(
            self.store,
            lambda chat_id, testo: self.messaggi.append((chat_id, testo)),
            lambda chat_id, testo, tasti: self.bottoni.append((chat_id, testo, tasti)),
            clock=lambda: time.time() + self.scarto)

    def _approva(self, installation_id: str, chat_id: int) -> None:
        codice, _ = self.store.richiedi(installation_id)
        self.store.richiedi_ingresso(codice, chat_id, None)
        self.store.approva(codice)

    def test_nessuna_installazione_lo_dice_senza_bottoni(self):
        self.elenca(42)
        self.assertEqual(self.messaggi, [(42, "Nessun computer collegato a questa chat.")])
        self.assertEqual(self.bottoni, [])

    def test_elenca_con_ultima_vista_e_un_bottone_per_installazione(self):
        self._approva("macchina-1", 42)
        self.scarto = 3600  # un'ora dopo l'approvazione
        self.elenca(42)

        self.assertEqual(len(self.messaggi), 1)
        self.assertIn("macchina-1", self.messaggi[0][1])
        self.assertIn("1 ora fa", self.messaggi[0][1])
        self.assertEqual(len(self.bottoni), 1)
        chat_id, _, tasti = self.bottoni[0]
        self.assertEqual(chat_id, 42)
        self.assertEqual(tasti, [("Stacca macchina-1", f"{devices.PREFISSO_STACCA}macchina-1")])

    def test_piu_installazioni_un_bottone_ciascuna(self):
        self._approva("macchina-1", 42)
        self._approva("macchina-2", 42)
        self.elenca(42)
        _, _, tasti = self.bottoni[0]
        self.assertEqual(len(tasti), 2)

    def test_non_tocca_le_installazioni_di_unaltra_chat(self):
        self._approva("macchina-1", 42)
        self._approva("macchina-2", 7)
        self.elenca(42)
        _, testo = self.messaggi[0]
        self.assertNotIn("macchina-2", testo)


class CostruisciDecisionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        codice, _ = self.store.richiedi("macchina-1")
        self.store.richiedi_ingresso(codice, 42, None)
        self.store.approva(codice)
        self.messaggi = []
        self.modifiche = []
        self.decidi = devices.costruisci_decision(
            self.store,
            lambda chat_id, testo: self.messaggi.append((chat_id, testo)),
            lambda chat_id, message_id, testo: self.modifiche.append((chat_id, message_id, testo)))

    def test_stacca_rimuove_lassociazione_e_modifica_il_messaggio(self):
        gestito = self.decidi(f"{devices.PREFISSO_STACCA}macchina-1", 42, 7)
        self.assertTrue(gestito)
        self.assertFalse(self.store.is_paired(42))
        self.assertEqual(self.modifiche, [(42, 7, "Staccato: macchina-1.")])
        self.assertEqual(self.messaggi, [(42, "Non ricevi piu' notifiche da macchina-1.")])

    def test_stacca_da_una_chat_diversa_e_assorbito_senza_effetto(self):
        gestito = self.decidi(f"{devices.PREFISSO_STACCA}macchina-1", 999, 7)
        self.assertTrue(gestito)  # riconosciuto (prefisso suo), ma nessuna azione
        self.assertTrue(self.store.is_paired(42))
        self.assertEqual(self.messaggi, [])
        self.assertEqual(self.modifiche, [])

    def test_callback_data_non_sua_torna_false(self):
        self.assertFalse(self.decidi("altro:prefisso:xyz", 42, 7))

    def test_secondo_tap_sulla_stessa_installazione_gia_staccata_e_assorbito(self):
        self.decidi(f"{devices.PREFISSO_STACCA}macchina-1", 42, 7)
        self.messaggi.clear()
        self.modifiche.clear()
        gestito = self.decidi(f"{devices.PREFISSO_STACCA}macchina-1", 42, 7)
        self.assertTrue(gestito)
        self.assertEqual(self.messaggi, [])
        self.assertEqual(self.modifiche, [])


if __name__ == "__main__":
    unittest.main()
