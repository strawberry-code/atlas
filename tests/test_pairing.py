"""Test del pairing Telegram one-tap e del cancello d'ingresso lato relay
(D05/A02/A03): store persistente, monouso, scaduto, sul modello 'chat ->
installazione' di SS4-bis, piu' l'approvazione del gestore imposta da S11/3.
Nessuna rete reale: 'invia_messaggio'/'invia_bottoni'/'modifica_messaggio'
sono sempre doppi finti che raccolgono le chiamate.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "relay"))

import bootstrap_gestore
import pairing


class GestorePairingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")

    def _approva(self, installation_id: str, chat_id: int, nome: str | None = None) -> str:
        """Le richieste da 'associazioni' passano ora dal cancello d'ingresso
        (A03): questo helper le porta fino ad 'associato' per i test che
        vogliono solo un'installazione gia' appaiata, senza ripetere le due
        chiamate ovunque serva."""
        codice, _ = self.store.richiedi(installation_id)
        self.store.richiedi_ingresso(codice, chat_id, nome)
        self.store.approva(codice)
        return codice

    def test_codice_fresco_e_in_attesa(self):
        codice, scadenza = self.store.richiedi("macchina-1")
        self.assertTrue(codice)
        self.assertGreater(scadenza, 0)
        self.assertEqual(self.store.stato(codice), "in_attesa")

    def test_richiedi_ingresso_sposta_lo_stato_in_attesa_gestore(self):
        codice, _ = self.store.richiedi("macchina-1")
        self.assertEqual(self.store.richiedi_ingresso(codice, 42, "@tizio"), "macchina-1")
        self.assertEqual(self.store.stato(codice), "in_attesa_gestore")
        self.assertFalse(self.store.is_paired(42))  # ancora nessuna associazione (S11/3)

    def test_approva_associa_e_torna_installazione_chat_nome(self):
        codice, _ = self.store.richiedi("macchina-1")
        self.store.richiedi_ingresso(codice, 42, "@tizio")
        esito = self.store.approva(codice)
        self.assertEqual(esito, ("macchina-1", 42, "@tizio"))
        self.assertTrue(self.store.is_paired(42))
        self.assertEqual(self.store.chat_id_di("macchina-1"), 42)
        self.assertEqual(self.store.stato(codice), "associato")

    def test_rifiuta_non_associa(self):
        codice, _ = self.store.richiedi("macchina-1")
        self.store.richiedi_ingresso(codice, 42, "@tizio")
        esito = self.store.rifiuta(codice)
        self.assertEqual(esito, ("macchina-1", 42, "@tizio"))
        self.assertFalse(self.store.is_paired(42))
        self.assertEqual(self.store.stato(codice), "rifiutato")

    def test_approva_su_richiesta_non_ancora_arrivata_none(self):
        codice, _ = self.store.richiedi("macchina-1")
        self.assertIsNone(self.store.approva(codice))  # nessun richiedi_ingresso ancora

    def test_secondo_tap_su_approva_o_rifiuta_non_ha_secondo_effetto(self):
        codice, _ = self.store.richiedi("macchina-1")
        self.store.richiedi_ingresso(codice, 42, None)
        self.assertIsNotNone(self.store.approva(codice))
        self.assertIsNone(self.store.approva(codice))
        self.assertIsNone(self.store.rifiuta(codice))

    def test_segna_senza_gestore(self):
        codice, _ = self.store.richiedi("macchina-1")
        self.store.richiedi_ingresso(codice, 42, None)
        self.store.segna_senza_gestore(codice)
        self.assertEqual(self.store.stato(codice), "senza_gestore")

    def test_monouso_richiedi_ingresso_il_secondo_tentativo_fallisce(self):
        codice, _ = self.store.richiedi("macchina-1")
        self.assertEqual(self.store.richiedi_ingresso(codice, 42, None), "macchina-1")
        self.assertIsNone(self.store.richiedi_ingresso(codice, 999, None))

    def test_codice_scaduto_non_entra(self):
        store = pairing.GestorePairing(Path(self.tmp.name) / "pairing2.json", ttl_seconds=-1)
        codice, _ = store.richiedi("macchina-1")
        self.assertEqual(store.stato(codice), "scaduto")
        self.assertIsNone(store.richiedi_ingresso(codice, 42, None))

    def test_codice_sconosciuto(self):
        self.assertEqual(self.store.stato("non-esiste"), "sconosciuto")
        self.assertIsNone(self.store.richiedi_ingresso("non-esiste", 42, None))

    def test_chat_non_associata_di_default(self):
        self.assertFalse(self.store.is_paired(42))
        self.assertIsNone(self.store.chat_id_di("macchina-1"))
        self.assertEqual(self.store.installazioni_di(42), [])

    def test_persiste_su_disco_tra_istanze_diverse(self):
        self._approva("macchina-1", 42)
        ripreso = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        self.assertTrue(ripreso.is_paired(42))
        self.assertEqual(ripreso.chat_id_di("macchina-1"), 42)

    def test_installazioni_di_e_l_inverso_di_chat_id_di(self):
        self._approva("macchina-1", 42)
        self.assertEqual(self.store.installazioni_di(42), ["macchina-1"])

    def test_un_installazione_ha_una_chat_sola_un_nuovo_pairing_la_sposta(self):
        self._approva("macchina-1", 1)
        self._approva("macchina-1", 2)
        self.assertEqual(self.store.chat_id_di("macchina-1"), 2)
        self.assertFalse(self.store.is_paired(1))
        self.assertTrue(self.store.is_paired(2))

    def test_una_chat_puo_seguire_piu_installazioni(self):
        self._approva("macchina-1", 42)
        self._approva("macchina-2", 42)
        self.assertEqual(set(self.store.installazioni_di(42)), {"macchina-1", "macchina-2"})
        self.assertEqual(self.store.installazioni_di(42)[0], "macchina-2")  # la piu' recente prima

    def test_due_richieste_per_la_stessa_installazione_non_si_calpestano(self):
        codice_a, _ = self.store.richiedi("macchina-1")
        codice_b, _ = self.store.richiedi("macchina-1")
        self.assertNotEqual(codice_a, codice_b)
        self.store.richiedi_ingresso(codice_a, 1, None)
        self.store.richiedi_ingresso(codice_b, 2, None)
        self.assertEqual(self.store.approva(codice_a), ("macchina-1", 1, None))
        self.assertEqual(self.store.approva(codice_b), ("macchina-1", 2, None))

    def test_approva_imposta_gia_ultima_vista(self):
        self._approva("macchina-1", 42)
        self.assertIsNotNone(self.store.ultima_vista("macchina-1"))

    def test_ultima_vista_none_per_installazione_non_associata(self):
        self.assertIsNone(self.store.ultima_vista("non-esiste"))

    def test_segna_vista_aggiorna_il_timestamp(self):
        self._approva("macchina-1", 42)
        prima = self.store.ultima_vista("macchina-1")
        self.store.segna_vista("macchina-1")
        self.assertGreaterEqual(self.store.ultima_vista("macchina-1"), prima)

    def test_segna_vista_su_installazione_non_associata_e_no_op(self):
        self.store.segna_vista("non-esiste")  # non deve sollevare
        self.assertIsNone(self.store.ultima_vista("non-esiste"))

    def test_stacca_rimuove_lassociazione(self):
        self._approva("macchina-1", 42)
        self.store.stacca("macchina-1")
        self.assertFalse(self.store.is_paired(42))
        self.assertIsNone(self.store.chat_id_di("macchina-1"))

    def test_stacca_su_installazione_non_associata_e_no_op(self):
        self.store.stacca("non-esiste")  # non deve sollevare

    def test_stacca_non_tocca_altre_installazioni_della_stessa_chat(self):
        self._approva("macchina-1", 42)
        self._approva("macchina-2", 42)
        self.store.stacca("macchina-1")
        self.assertTrue(self.store.is_paired(42))
        self.assertEqual(self.store.installazioni_di(42), ["macchina-2"])


class GestoreBootstrapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")

    def test_nessun_gestore_di_default(self):
        self.assertIsNone(self.store.gestore_chat_id())

    def test_emetti_bootstrap_torna_un_codice(self):
        codice = self.store.emetti_bootstrap_gestore()
        self.assertTrue(codice)

    def test_emetti_bootstrap_e_idempotente_finche_valido(self):
        primo = self.store.emetti_bootstrap_gestore()
        secondo = self.store.emetti_bootstrap_gestore()
        self.assertEqual(primo, secondo)

    def test_conferma_gestore_reclama_il_ruolo(self):
        codice = self.store.emetti_bootstrap_gestore()
        self.assertTrue(self.store.conferma_gestore(codice, 100))
        self.assertEqual(self.store.gestore_chat_id(), 100)

    def test_conferma_gestore_codice_sbagliato_fallisce(self):
        self.store.emetti_bootstrap_gestore()
        self.assertFalse(self.store.conferma_gestore("altro-codice", 100))
        self.assertIsNone(self.store.gestore_chat_id())

    def test_gestore_gia_registrato_non_si_riemette_ne_si_riclama(self):
        codice = self.store.emetti_bootstrap_gestore()
        self.store.conferma_gestore(codice, 100)
        self.assertIsNone(self.store.emetti_bootstrap_gestore())
        self.assertFalse(self.store.conferma_gestore(codice, 200))
        self.assertEqual(self.store.gestore_chat_id(), 100)

    def test_bootstrap_scaduto_non_reclama(self):
        store = pairing.GestorePairing(Path(self.tmp.name) / "pairing2.json", ttl_seconds=-1)
        codice = store.emetti_bootstrap_gestore()
        self.assertFalse(store.conferma_gestore(codice, 100))


class CostruisciPairingStartTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        self.messaggi = []
        self.bottoni = []
        self.on_start = pairing.costruisci_pairing_start(
            self.store,
            lambda chat_id, testo: self.messaggi.append((chat_id, testo)),
            lambda chat_id, testo, tasti: self.bottoni.append((chat_id, testo, tasti)))

    def test_bootstrap_reclama_il_gestore_e_non_chiede_ingresso(self):
        codice = self.store.emetti_bootstrap_gestore()
        self.on_start(codice, 100, "@cristiano")
        self.assertEqual(self.store.gestore_chat_id(), 100)
        self.assertEqual(len(self.messaggi), 1)
        self.assertIn("gestore", self.messaggi[0][1])
        self.assertEqual(self.bottoni, [])

    def test_richiesta_con_gestore_configurato_resta_in_sospeso_e_avvisa_il_gestore(self):
        codice_bootstrap = self.store.emetti_bootstrap_gestore()
        self.on_start(codice_bootstrap, 100)  # 100 diventa il gestore

        codice, _ = self.store.richiedi("macchina-1")
        self.on_start(codice, 42, "@tizio")

        self.assertFalse(self.store.is_paired(42))
        self.assertEqual(self.store.stato(codice), "in_attesa_gestore")
        self.assertEqual(len(self.messaggi), 2)
        self.assertIn("via libera", self.messaggi[1][1])
        self.assertEqual(len(self.bottoni), 1)
        chat_gestore, testo, tasti = self.bottoni[0]
        self.assertEqual(chat_gestore, 100)
        self.assertIn("@tizio", testo)
        self.assertEqual([etichetta for etichetta, _ in tasti], ["Approva", "Rifiuta"])
        self.assertTrue(all(dato.endswith(codice) for _, dato in tasti))

    def test_richiesta_senza_gestore_si_segna_e_lo_dice_al_richiedente(self):
        codice, _ = self.store.richiedi("macchina-1")
        self.on_start(codice, 42, "@tizio")
        self.assertEqual(self.store.stato(codice), "senza_gestore")
        self.assertIn("gestore configurato", self.messaggi[0][1])
        self.assertEqual(self.bottoni, [])

    def test_codice_invalido_rifiuta_senza_associare(self):
        self.on_start("non-esiste", 42)
        self.assertFalse(self.store.is_paired(42))
        self.assertEqual(len(self.messaggi), 1)
        self.assertIn("non valido", self.messaggi[0][1])


class CostruisciAdminDecisionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = pairing.GestorePairing(Path(self.tmp.name) / "pairing.json")
        self.store.conferma_gestore(self.store.emetti_bootstrap_gestore(), 100)
        self.messaggi = []
        self.modifiche = []
        self.decidi = pairing.costruisci_admin_decision(
            self.store,
            lambda chat_id, testo: self.messaggi.append((chat_id, testo)),
            lambda chat_id, message_id, testo: self.modifiche.append((chat_id, message_id, testo)))
        self.codice, _ = self.store.richiedi("macchina-1")
        self.store.richiedi_ingresso(self.codice, 42, "@tizio")

    def test_approva_associa_avvisa_richiedente_e_modifica_il_messaggio_del_gestore(self):
        gestito = self.decidi(f"gestore:approva:{self.codice}", 100, 7)
        self.assertTrue(gestito)
        self.assertTrue(self.store.is_paired(42))
        self.assertEqual(self.messaggi, [(42, "Connesso ad Atlas. Da qui in poi ricevi qui "
                                              "le notifiche di questa macchina.")])
        self.assertEqual(self.modifiche, [(100, 7, "Approvato: @tizio.")])

    def test_rifiuta_non_associa_e_lo_dice_al_richiedente(self):
        gestito = self.decidi(f"gestore:rifiuta:{self.codice}", 100, 7)
        self.assertTrue(gestito)
        self.assertFalse(self.store.is_paired(42))
        self.assertEqual(self.messaggi, [(42, "Richiesta di accesso rifiutata.")])
        self.assertEqual(self.modifiche, [(100, 7, "Rifiutato: @tizio.")])

    def test_tap_da_chi_non_e_il_gestore_e_assorbito_senza_effetto(self):
        gestito = self.decidi(f"gestore:approva:{self.codice}", 999, 7)
        self.assertTrue(gestito)  # riconosciuto (prefisso suo), ma nessuna azione
        self.assertFalse(self.store.is_paired(42))
        self.assertEqual(self.messaggi, [])
        self.assertEqual(self.modifiche, [])

    def test_callback_data_non_sua_torna_false(self):
        self.assertFalse(self.decidi("altro:prefisso:xyz", 100, 7))

    def test_doppio_tap_sullo_stesso_codice_secondo_e_no_op(self):
        self.decidi(f"gestore:approva:{self.codice}", 100, 7)
        self.messaggi.clear()
        self.modifiche.clear()
        gestito = self.decidi(f"gestore:approva:{self.codice}", 100, 7)
        self.assertTrue(gestito)
        self.assertEqual(self.messaggi, [])
        self.assertEqual(self.modifiche, [])


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
            codice, _ = gestore.richiedi("macchina-1")
            self.assertTrue((Path(tmp) / "pairing.json").is_file())
            self.assertEqual(gestore.stato(codice), "in_attesa")


class BootstrapGestoreScriptTest(unittest.TestCase):
    """Il comando locale (A03) che stampa il link di bootstrap: nessuna rete,
    solo il file di stato. 'link_di_bootstrap' e' puro sull'ambiente passato,
    come 'deploy.deploy(env, ...)': nessun test tocca 'os.environ' vero."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = {
            "TELEGRAM_BOT_TOKEN_REF": "op://vault/telegram-bot-token",
            "TELEGRAM_BOT_USERNAME": "atlas_bot",
            pairing.ENV_STATE_DIR: self.tmp.name,
        }

    def test_senza_prerequisiti_esce_con_errore(self):
        esito, riga = bootstrap_gestore.link_di_bootstrap({})
        self.assertEqual(esito, 1)
        self.assertTrue(riga)

    def test_stampa_un_link_t_me_valido(self):
        esito, riga = bootstrap_gestore.link_di_bootstrap(self.env)
        self.assertEqual(esito, 0)
        self.assertTrue(riga.startswith("https://t.me/atlas_bot?start="))

    def test_gestore_gia_presente_esce_con_errore_e_non_riemette_il_link(self):
        store = pairing.costruisci_da_ambiente(self.env)
        store.conferma_gestore(store.emetti_bootstrap_gestore(), 100)

        esito, riga = bootstrap_gestore.link_di_bootstrap(self.env)
        self.assertEqual(esito, 1)
        self.assertNotIn("https://t.me", riga)


if __name__ == "__main__":
    unittest.main()
