"""Test del pairing Telegram lato client (D05/A04): serve_pairing.avvia/stato
parlano col relay con lo stesso 'opener' iniettabile di relay_client, mai
rete vera. Il gate (relay non configurato in questo ambiente) e' lo stesso
di relay_client.da_ambiente, gia' testato in isolamento in
tests/test_relay_client.py. Il gesto e' per macchina (A04): ogni test isola
l'identita' di relay_identity in una ATLAS_INSTALL_HOME temporanea, mai la
vera '~/.config/atlas'.
"""
from __future__ import annotations

import json
import sys
import tempfile
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))

import unittest

from core import relay_identity, serve_pairing

ENV = {
    "RELAY_HTTPS_HOSTNAME": "relay.test",
    "ATLAS_RELAY_TOKEN_REF": "il-bearer",
}


# Un ambiente vuoto non basta a dire 'questa macchina non ha un relay': la
# configurazione vive anche in un profilo su disco, e un test che non lo isola
# leggerebbe quello di chi lo lancia, passando o fallendo a seconda del computer.
SENZA_RELAY = {"ATLAS_INSTALL_HOME": tempfile.mkdtemp(prefix="atlas-test-senza-relay-")}


class FakeRisposta:
    def __init__(self, status: int, corpo: bytes) -> None:
        self.status = status
        self._corpo = corpo

    def read(self) -> bytes:
        return self._corpo

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class MotivoDelFallimento(unittest.TestCase):
    """Due guasti diversi devono dire due cose diverse a chi guarda.

    Senza un relay configurato, riprovare non funzionera' mai: il pannello che
    dice 'riprova' manda una persona a premere un bottone per sempre. Il motivo
    e' un valore codificato, non prosa, perche' a sceglierne il testo e' il
    browser e non un modello.
    """

    def test_senza_relay_configurato_lo_dichiara(self):
        stato, corpo = serve_pairing.avvia(env=SENZA_RELAY)
        self.assertEqual(503, stato)
        self.assertEqual("relay-non-configurato", corpo["motivo"])

    def test_relay_che_non_risponde_e_un_altro_motivo(self):
        def opener(richiesta, timeout=None):
            raise OSError("connessione rifiutata")

        stato, corpo = serve_pairing.avvia(
            env={"RELAY_PUBLIC_URL": "https://relay.example", "ATLAS_RELAY_TOKEN_REF": "x"},
            opener=opener)
        self.assertEqual(502, stato)
        self.assertEqual("relay-non-risponde", corpo["motivo"])


class Avvia(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.env = dict(ENV, ATLAS_INSTALL_HOME=self._tmp.name)

    def test_503_senza_relay_configurato(self):
        stato, payload = serve_pairing.avvia(env=SENZA_RELAY)
        self.assertEqual(stato, 503)
        self.assertFalse(payload["ok"])

    def test_200_torna_url_e_codice(self):
        chiamate = []

        def opener(richiesta, timeout):
            chiamate.append(richiesta)
            corpo = json.dumps({"code": "abc123", "url": "https://t.me/atlas_bot?start=abc123",
                                 "expiresAt": 123.0}).encode("utf-8")
            return FakeRisposta(200, corpo)

        stato, payload = serve_pairing.avvia(env=self.env, opener=opener)
        self.assertEqual(stato, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["code"], "abc123")
        self.assertEqual(payload["url"], "https://t.me/atlas_bot?start=abc123")
        self.assertEqual(len(chiamate), 1)
        self.assertIn("Bearer il-bearer", chiamate[0].headers["Authorization"])
        installazione = relay_identity.carica_o_crea(env=self.env)
        self.assertEqual(json.loads(chiamate[0].data), {"installation": installazione.installation_id})

    def test_502_se_il_relay_rifiuta(self):
        def opener(richiesta, timeout):
            raise urllib.error.URLError("giu'")

        stato, payload = serve_pairing.avvia(env=self.env, opener=opener)
        self.assertEqual(stato, 502)
        self.assertFalse(payload["ok"])

    def test_502_se_lo_status_non_e_200(self):
        def opener(richiesta, timeout):
            return FakeRisposta(404, b"{}")

        stato, payload = serve_pairing.avvia(env=self.env, opener=opener)
        self.assertEqual(stato, 502)


class Stato(unittest.TestCase):
    def test_503_senza_relay_configurato(self):
        stato, payload = serve_pairing.stato("abc123", env=SENZA_RELAY)
        self.assertEqual(stato, 503)

    def test_400_senza_codice(self):
        stato, payload = serve_pairing.stato("", env=ENV)
        self.assertEqual(stato, 400)

    def test_200_torna_lo_stato(self):
        chiamate = []

        def opener(richiesta, timeout):
            chiamate.append(richiesta)
            return FakeRisposta(200, json.dumps({"status": "associato"}).encode("utf-8"))

        stato, payload = serve_pairing.stato("abc123", env=ENV, opener=opener)
        self.assertEqual(stato, 200)
        self.assertEqual(payload, {"ok": True, "status": "associato"})
        self.assertIn("code=abc123", chiamate[0].full_url)

    def test_502_su_guasto_di_trasporto(self):
        def opener(richiesta, timeout):
            raise urllib.error.URLError("giu'")

        stato, payload = serve_pairing.stato("abc123", env=ENV, opener=opener)
        self.assertEqual(stato, 502)


if __name__ == "__main__":
    unittest.main()
