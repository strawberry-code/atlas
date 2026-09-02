"""Test del pairing Telegram lato client (D05): serve_pairing.avvia/stato
parlano col relay con lo stesso 'opener' iniettabile di relay_client, mai
rete vera. Il gate (relay non configurato in questo ambiente) e' lo stesso
di relay_client.da_ambiente, gia' testato in isolamento in
tests/test_relay_client.py.
"""
from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))

import unittest

from core import serve_pairing

ENV = {
    "RELAY_HTTPS_HOSTNAME": "relay.test",
    "ATLAS_RELAY_TOKEN_REF": "il-bearer",
}


class RifGrafo:
    def __init__(self, slug: str) -> None:
        self.slug = slug


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


class Avvia(unittest.TestCase):
    def test_503_senza_relay_configurato(self):
        stato, payload = serve_pairing.avvia(RifGrafo("prova"), env={})
        self.assertEqual(stato, 503)
        self.assertFalse(payload["ok"])

    def test_200_torna_url_e_codice(self):
        chiamate = []

        def opener(richiesta, timeout):
            chiamate.append(richiesta)
            corpo = json.dumps({"code": "abc123", "url": "https://t.me/atlas_bot?start=abc123",
                                 "expiresAt": 123.0}).encode("utf-8")
            return FakeRisposta(200, corpo)

        stato, payload = serve_pairing.avvia(RifGrafo("prova"), env=ENV, opener=opener)
        self.assertEqual(stato, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["code"], "abc123")
        self.assertEqual(payload["url"], "https://t.me/atlas_bot?start=abc123")
        self.assertEqual(len(chiamate), 1)
        self.assertIn("Bearer il-bearer", chiamate[0].headers["Authorization"])
        self.assertEqual(json.loads(chiamate[0].data), {"graph": "prova"})

    def test_502_se_il_relay_rifiuta(self):
        def opener(richiesta, timeout):
            raise urllib.error.URLError("giu'")

        stato, payload = serve_pairing.avvia(RifGrafo("prova"), env=ENV, opener=opener)
        self.assertEqual(stato, 502)
        self.assertFalse(payload["ok"])

    def test_502_se_lo_status_non_e_200(self):
        def opener(richiesta, timeout):
            return FakeRisposta(404, b"{}")

        stato, payload = serve_pairing.avvia(RifGrafo("prova"), env=ENV, opener=opener)
        self.assertEqual(stato, 502)


class Stato(unittest.TestCase):
    def test_503_senza_relay_configurato(self):
        stato, payload = serve_pairing.stato("abc123", env={})
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
