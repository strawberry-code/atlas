"""Identita' d'installazione verso il relay (A01): nascita del segreto,
percorso fuori dal repo, firma delle richieste e sua verifica."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))

from core import relay_identity


class PercorsoPredefinito(unittest.TestCase):
    def test_dentro_config_home_utente(self):
        percorso = relay_identity.percorso_predefinito(env={})
        self.assertEqual(percorso, Path.home() / ".config" / "atlas" / "relay-identity.json")

    def test_override_da_ambiente(self):
        percorso = relay_identity.percorso_predefinito(env={"ATLAS_INSTALL_HOME": "/tmp/una-casa"})
        self.assertEqual(percorso, Path("/tmp/una-casa/relay-identity.json"))


class CaricaOCrea(unittest.TestCase):
    def test_genera_alla_prima_chiamata(self):
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "sub" / "relay-identity.json"
            installazione = relay_identity.carica_o_crea(percorso)
            self.assertTrue(percorso.is_file())
            self.assertTrue(installazione.installation_id)
            self.assertTrue(installazione.secret)

    def test_seconda_chiamata_rilegge_la_stessa_identita(self):
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "relay-identity.json"
            prima = relay_identity.carica_o_crea(percorso)
            seconda = relay_identity.carica_o_crea(percorso)
            self.assertEqual(prima, seconda)

    def test_due_installazioni_diverse_non_condividono_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = relay_identity.carica_o_crea(Path(tmp) / "a.json")
            b = relay_identity.carica_o_crea(Path(tmp) / "b.json")
            self.assertNotEqual(a.installation_id, b.installation_id)
            self.assertNotEqual(a.secret, b.secret)

    @unittest.skipIf(sys.platform == "win32", "chmod 0600 non si applica su Windows")
    def test_file_scritto_leggibile_solo_dal_proprietario(self):
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "relay-identity.json"
            relay_identity.carica_o_crea(percorso)
            modo = percorso.stat().st_mode & 0o777
            self.assertEqual(modo, 0o600)

    def test_file_corrotto_viene_rigenerato(self):
        with tempfile.TemporaryDirectory() as tmp:
            percorso = Path(tmp) / "relay-identity.json"
            percorso.write_text("non e' json", encoding="utf-8")
            installazione = relay_identity.carica_o_crea(percorso)
            self.assertTrue(installazione.installation_id)


class IntestazioniEVerifica(unittest.TestCase):
    def setUp(self):
        self.installazione = relay_identity.Installazione(installation_id="inst-1", secret="segreto")
        self.nonces = relay_identity.NonceVisti()

    def test_intestazioni_hanno_tutti_i_campi_del_contratto(self):
        intestazioni = relay_identity.intestazioni_richiesta(
            self.installazione, "POST", "/tunnel/deliver", b'{"a":1}')
        for chiave in (relay_identity.INTESTAZIONE_INSTALL, relay_identity.INTESTAZIONE_PROTOCOLLO,
                      relay_identity.INTESTAZIONE_TIMESTAMP, relay_identity.INTESTAZIONE_NONCE,
                      relay_identity.INTESTAZIONE_FIRMA):
            self.assertIn(chiave, intestazioni)
        self.assertEqual(intestazioni[relay_identity.INTESTAZIONE_INSTALL], "inst-1")
        self.assertEqual(intestazioni[relay_identity.INTESTAZIONE_PROTOCOLLO], str(relay_identity.PROTOCOLLO))

    def test_secret_non_compare_mai_nelle_intestazioni(self):
        intestazioni = relay_identity.intestazioni_richiesta(self.installazione, "GET", "/tunnel", b"")
        self.assertNotIn("segreto", intestazioni.values())

    def test_round_trip_accettato(self):
        intestazioni = relay_identity.intestazioni_richiesta(
            self.installazione, "POST", "/tunnel/deliver", b'{"a":1}')
        relay_identity.verifica_richiesta(
            self.installazione.secret, self.installazione.installation_id, intestazioni,
            "POST", "/tunnel/deliver", b'{"a":1}', nonces=self.nonces)  # non solleva

    def test_secret_sbagliato_rifiutato(self):
        intestazioni = relay_identity.intestazioni_richiesta(self.installazione, "GET", "/tunnel", b"")
        with self.assertRaises(relay_identity.IdentitaRelayRifiutata):
            relay_identity.verifica_richiesta(
                "altro-secret", self.installazione.installation_id, intestazioni,
                "GET", "/tunnel", b"", nonces=self.nonces)

    def test_corpo_manomesso_rifiutato(self):
        intestazioni = relay_identity.intestazioni_richiesta(
            self.installazione, "POST", "/tunnel/deliver", b'{"a":1}')
        with self.assertRaises(relay_identity.IdentitaRelayRifiutata):
            relay_identity.verifica_richiesta(
                self.installazione.secret, self.installazione.installation_id, intestazioni,
                "POST", "/tunnel/deliver", b'{"a":2}', nonces=self.nonces)

    def test_percorso_manomesso_rifiutato(self):
        intestazioni = relay_identity.intestazioni_richiesta(self.installazione, "GET", "/tunnel", b"")
        with self.assertRaises(relay_identity.IdentitaRelayRifiutata):
            relay_identity.verifica_richiesta(
                self.installazione.secret, self.installazione.installation_id, intestazioni,
                "GET", "/tunnel/deliver", b"", nonces=self.nonces)

    def test_timestamp_fuori_tolleranza_rifiutato(self):
        intestazioni = relay_identity.intestazioni_richiesta(
            self.installazione, "GET", "/tunnel", b"", timestamp="1000")
        with self.assertRaises(relay_identity.IdentitaRelayRifiutata):
            relay_identity.verifica_richiesta(
                self.installazione.secret, self.installazione.installation_id, intestazioni,
                "GET", "/tunnel", b"", nonces=self.nonces, now=1000 + relay_identity.TOLLERANZA_SECONDI + 1)

    def test_nonce_riusato_rifiutato(self):
        intestazioni = relay_identity.intestazioni_richiesta(self.installazione, "GET", "/tunnel", b"")
        relay_identity.verifica_richiesta(
            self.installazione.secret, self.installazione.installation_id, intestazioni,
            "GET", "/tunnel", b"", nonces=self.nonces)
        with self.assertRaises(relay_identity.IdentitaRelayRifiutata):
            relay_identity.verifica_richiesta(
                self.installazione.secret, self.installazione.installation_id, intestazioni,
                "GET", "/tunnel", b"", nonces=self.nonces)

    def test_header_mancante_rifiutato(self):
        with self.assertRaises(relay_identity.IdentitaRelayRifiutata):
            relay_identity.verifica_richiesta(
                self.installazione.secret, self.installazione.installation_id, {},
                "GET", "/tunnel", b"", nonces=self.nonces)


class NonceVistiTest(unittest.TestCase):
    def test_prima_volta_vero_seconda_falso(self):
        nonces = relay_identity.NonceVisti()
        self.assertTrue(nonces.consuma("n1", now_epoch=0.0, tolleranza=300))
        self.assertFalse(nonces.consuma("n1", now_epoch=0.0, tolleranza=300))

    def test_nonce_fuori_tolleranza_viene_potato_e_puo_ripresentarsi(self):
        nonces = relay_identity.NonceVisti()
        nonces.consuma("n1", now_epoch=0.0, tolleranza=300)
        self.assertTrue(nonces.consuma("n1", now_epoch=301.0, tolleranza=300))


if __name__ == "__main__":
    unittest.main()
