"""Test del freno automatico oltre soglia (C01): la finestra scorrevole di
FrenoOrario in isolamento, e i due costruttori che parlano con Telegram
(notifica del blocco, decisione del gestore su 'Sblocca'/'Chiedi sblocco').
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "relay"))

import throttle


class OrologioFinto:
    def __init__(self, adesso: float = 0.0) -> None:
        self.adesso = adesso

    def __call__(self) -> float:
        return self.adesso


class FrenoOrarioTest(unittest.TestCase):
    def test_sotto_soglia_consente_sempre(self):
        freno = throttle.FrenoOrario(soglia=3)
        for _ in range(3):
            self.assertEqual(freno.consenti("macchina-a"), "ok")

    def test_oltre_soglia_blocca_una_volta_sola(self):
        freno = throttle.FrenoOrario(soglia=2)
        self.assertEqual(freno.consenti("macchina-a"), "ok")
        self.assertEqual(freno.consenti("macchina-a"), "ok")
        self.assertEqual(freno.consenti("macchina-a"), "nuovo_blocco")
        self.assertEqual(freno.consenti("macchina-a"), "gia_bloccata")
        self.assertEqual(freno.consenti("macchina-a"), "gia_bloccata")

    def test_installazioni_diverse_non_si_influenzano(self):
        freno = throttle.FrenoOrario(soglia=1)
        self.assertEqual(freno.consenti("macchina-a"), "ok")
        self.assertEqual(freno.consenti("macchina-a"), "nuovo_blocco")
        self.assertEqual(freno.consenti("macchina-b"), "ok")

    def test_tentativi_respinti_non_allungano_il_blocco(self):
        orologio = OrologioFinto()
        freno = throttle.FrenoOrario(soglia=1, finestra=10.0, clock=orologio)
        self.assertEqual(freno.consenti("macchina-a"), "ok")
        orologio.adesso = 5.0
        self.assertEqual(freno.consenti("macchina-a"), "nuovo_blocco")   # non registrato
        orologio.adesso = 11.0   # il solo tentativo vero (a t=0) e' uscito dalla finestra
        self.assertEqual(freno.consenti("macchina-a"), "ok")

    def test_sblocca_azzera_la_finestra_subito(self):
        freno = throttle.FrenoOrario(soglia=1)
        freno.consenti("macchina-a")
        self.assertEqual(freno.consenti("macchina-a"), "nuovo_blocco")
        freno.sblocca("macchina-a")
        self.assertEqual(freno.consenti("macchina-a"), "ok")

    def test_ricaduta_sotto_soglia_poi_di_nuovo_sopra_riavvisa(self):
        orologio = OrologioFinto()
        freno = throttle.FrenoOrario(soglia=1, finestra=10.0, clock=orologio)
        freno.consenti("macchina-a")
        self.assertEqual(freno.consenti("macchina-a"), "nuovo_blocco")
        orologio.adesso = 11.0
        self.assertEqual(freno.consenti("macchina-a"), "ok")   # finestra svuotata da sola
        self.assertEqual(freno.consenti("macchina-a"), "nuovo_blocco")   # riavvisa, non 'gia_bloccata'


class GestorePairingFinto:
    def __init__(self, gestore_chat_id=None, chat_di=None):
        self._gestore_chat_id = gestore_chat_id
        self._chat_di = chat_di or {}

    def gestore_chat_id(self):
        return self._gestore_chat_id

    def chat_id_di(self, installation_id):
        return self._chat_di.get(installation_id)


class NotificaBloccoTest(unittest.TestCase):
    def test_avvisa_la_macchina_fermata_e_il_gestore(self):
        messaggi = []
        bottoni = []
        store = GestorePairingFinto(gestore_chat_id=99)
        notifica = throttle.costruisci_notifica_blocco(
            store, lambda chat_id, testo: messaggi.append((chat_id, testo)),
            lambda chat_id, testo, opzioni: bottoni.append((chat_id, testo, opzioni)))

        notifica("macchina-a", 42)

        self.assertTrue(any(chat_id == 42 for chat_id, _ in messaggi))
        chat_bottoni = [chat_id for chat_id, _, _ in bottoni]
        self.assertIn(42, chat_bottoni)   # il bottone 'Chiedi sblocco' alla macchina fermata
        self.assertIn(99, chat_bottoni)   # il bottone 'Sblocca' al gestore

    def test_senza_gestore_avvisa_solo_la_macchina_fermata(self):
        bottoni = []
        store = GestorePairingFinto(gestore_chat_id=None)
        notifica = throttle.costruisci_notifica_blocco(
            store, lambda chat_id, testo: None,
            lambda chat_id, testo, opzioni: bottoni.append(chat_id))

        notifica("macchina-a", 42)

        self.assertEqual(bottoni, [42])


class AdminDecisionTest(unittest.TestCase):
    def setUp(self):
        self.freno = throttle.FrenoOrario(soglia=1)
        self.freno.consenti("macchina-a")
        self.freno.consenti("macchina-a")   # ora bloccata
        self.messaggi = []
        self.bottoni = []
        self.store = GestorePairingFinto(gestore_chat_id=99, chat_di={"macchina-a": 42})
        self.decidi = throttle.costruisci_admin_decision(
            self.freno, self.store, lambda chat_id, testo: self.messaggi.append((chat_id, testo)),
            lambda chat_id, testo, opzioni: self.bottoni.append((chat_id, testo, opzioni)))

    def test_sblocca_dal_gestore_azzera_il_freno_e_avvisa_entrambi(self):
        gestito = self.decidi(f"{throttle.PREFISSO_SBLOCCA}macchina-a", 99, 7)

        self.assertTrue(gestito)
        self.assertEqual(self.freno.consenti("macchina-a"), "ok")
        chat_avvisate = [chat_id for chat_id, _ in self.messaggi]
        self.assertIn(99, chat_avvisate)
        self.assertIn(42, chat_avvisate)

    def test_sblocca_da_chat_diversa_dal_gestore_e_assorbito_senza_effetto(self):
        gestito = self.decidi(f"{throttle.PREFISSO_SBLOCCA}macchina-a", 12345, 7)

        self.assertTrue(gestito)
        self.assertEqual(self.messaggi, [])
        self.assertEqual(self.freno.consenti("macchina-a"), "gia_bloccata")

    def test_appello_inoltra_al_gestore_con_bottone_sblocca(self):
        gestito = self.decidi(f"{throttle.PREFISSO_APPELLO}macchina-a", 42, 7)

        self.assertTrue(gestito)
        self.assertEqual(len(self.bottoni), 1)
        chat_id, _, opzioni = self.bottoni[0]
        self.assertEqual(chat_id, 99)
        self.assertEqual(opzioni, [("Sblocca", f"{throttle.PREFISSO_SBLOCCA}macchina-a")])

    def test_callback_data_non_riconosciuto_non_gestito(self):
        self.assertFalse(self.decidi("qualcos-altro", 42, 7))


if __name__ == "__main__":
    unittest.main()
