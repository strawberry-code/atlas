"""Test del pairing Telegram one-tap lato relay (D05): store persistente,
monouso, scaduto, e la chiusura che traduce un '/start <codice>' in un
messaggio Telegram di esito. Nessuna rete reale: 'invia_messaggio' e' sempre
un doppio finto che raccoglie le chiamate.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "relay"))

import pairing


class GestorePairingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")

    def test_codice_fresco_e_in_attesa(self):
        codice, scadenza = self.store.richiedi("prova")
        self.assertTrue(codice)
        self.assertGreater(scadenza, 0)
        self.assertEqual(self.store.stato(codice), "in_attesa")

    def test_conferma_associa_e_torna_il_graph(self):
        codice, _ = self.store.richiedi("prova")
        graph = self.store.conferma(codice, 42)
        self.assertEqual(graph, "prova")
        self.assertTrue(self.store.is_paired(42))
        self.assertEqual(self.store.progetto_di(42), "prova")
        self.assertEqual(self.store.stato(codice), "associato")

    def test_monouso_il_secondo_tentativo_fallisce(self):
        codice, _ = self.store.richiedi("prova")
        self.assertEqual(self.store.conferma(codice, 42), "prova")
        self.assertIsNone(self.store.conferma(codice, 999))
        self.assertFalse(self.store.is_paired(999))

    def test_codice_scaduto_non_associa(self):
        store = pairing.GestorePairing(Path(self.tmp.name) / "pairing2.json", ttl_seconds=-1)
        codice, _ = store.richiedi("prova")
        self.assertEqual(store.stato(codice), "scaduto")
        self.assertIsNone(store.conferma(codice, 42))

    def test_codice_sconosciuto(self):
        self.assertEqual(self.store.stato("non-esiste"), "sconosciuto")
        self.assertIsNone(self.store.conferma("non-esiste", 42))

    def test_chat_non_associata_di_default(self):
        self.assertFalse(self.store.is_paired(42))
        self.assertIsNone(self.store.progetto_di(42))

    def test_persiste_su_disco_tra_istanze_diverse(self):
        codice, _ = self.store.richiedi("prova")
        self.store.conferma(codice, 42)
        ripreso = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        self.assertTrue(ripreso.is_paired(42))
        self.assertEqual(ripreso.progetto_di(42), "prova")

    def test_due_richieste_per_lo_stesso_graph_non_si_calpestano(self):
        codice_a, _ = self.store.richiedi("prova")
        codice_b, _ = self.store.richiedi("prova")
        self.assertNotEqual(codice_a, codice_b)
        self.assertEqual(self.store.conferma(codice_a, 1), "prova")
        self.assertEqual(self.store.conferma(codice_b, 2), "prova")


class CostruisciPairingStartTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        self.messaggi = []
        self.on_start = pairing.costruisci_pairing_start(
            self.store, lambda chat_id, testo: self.messaggi.append((chat_id, testo)))

    def test_codice_valido_associa_e_conferma(self):
        codice, _ = self.store.richiedi("prova")
        self.on_start(codice, 42)
        self.assertTrue(self.store.is_paired(42))
        self.assertEqual(len(self.messaggi), 1)
        self.assertEqual(self.messaggi[0][0], 42)
        self.assertIn("prova", self.messaggi[0][1])

    def test_codice_invalido_rifiuta_senza_associare(self):
        self.on_start("non-esiste", 42)
        self.assertFalse(self.store.is_paired(42))
        self.assertEqual(len(self.messaggi), 1)
        self.assertIn("non valido", self.messaggi[0][1])


class CostruisciDaAmbienteTest(unittest.TestCase):
    def test_none_senza_prerequisiti(self):
        self.assertIsNone(pairing.costruisci_da_ambiente({}))

    def test_gestore_con_prerequisiti_completi(self):
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "pairing.json"
            gestore = pairing.costruisci_da_ambiente({
                "TELEGRAM_BOT_TOKEN_REF": "op://vault/telegram-bot-token",
                "TELEGRAM_BOT_USERNAME": "atlas_bot",
            }, state_path=percorso)
            self.assertIsInstance(gestore, pairing.GestorePairing)

    def test_percorso_di_stato_da_env_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            gestore = pairing.costruisci_da_ambiente({
                "TELEGRAM_BOT_TOKEN_REF": "op://vault/telegram-bot-token",
                "TELEGRAM_BOT_USERNAME": "atlas_bot",
                pairing.ENV_STATE_DIR: tmp,
            })
            codice, _ = gestore.richiedi("prova")
            self.assertTrue((Path(tmp) / "pairing.json").is_file())
            self.assertEqual(gestore.stato(codice), "in_attesa")


if __name__ == "__main__":
    unittest.main()
