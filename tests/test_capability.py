"""Capability token del protocollo D01 (D06): emissione, verifica firma,
scadenza e monouso (jti)."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))

from core import capability

CHIAVE = "una-chiave-hmac-di-progetto"


def _exp(delta: timedelta) -> str:
    return (datetime.now().astimezone() + delta).isoformat(timespec="seconds")


class DaAmbiente(unittest.TestCase):
    def test_none_senza_chiave(self):
        self.assertIsNone(capability.da_ambiente({}))

    def test_torna_la_chiave_dichiarata(self):
        self.assertEqual(capability.da_ambiente({"ATLAS_CAPABILITY_KEY_REF": CHIAVE}), CHIAVE)


class EmettiEVerifica(unittest.TestCase):
    def setUp(self):
        self.consumati = capability.ConsumatiJti()

    def test_round_trip(self):
        token = capability.emetti(CHIAVE, graph="g", run_id="r1", interaction_id="I001",
                                  action_id="confirm", exp=_exp(timedelta(minutes=5)))
        payload = capability.verifica(CHIAVE, token, consumati=self.consumati)
        self.assertEqual(payload["graph"], "g")
        self.assertEqual(payload["runId"], "r1")
        self.assertEqual(payload["interactionId"], "I001")
        self.assertEqual(payload["actionId"], "confirm")

    def test_due_token_della_stessa_azione_hanno_jti_diversi(self):
        kwargs = dict(graph="g", run_id="r1", interaction_id="I001", action_id="confirm",
                     exp=_exp(timedelta(minutes=5)))
        self.assertNotEqual(capability.emetti(CHIAVE, **kwargs), capability.emetti(CHIAVE, **kwargs))

    def test_firma_sbagliata_rifiutata(self):
        token = capability.emetti(CHIAVE, graph="g", run_id="r1", interaction_id="I001",
                                  action_id="confirm", exp=_exp(timedelta(minutes=5)))
        corpo, _firma = token.split(".", 1)
        manomesso = f"{corpo}.{'a' * 40}"
        with self.assertRaises(capability.CapabilityRejected):
            capability.verifica(CHIAVE, manomesso, consumati=self.consumati)

    def test_chiave_diversa_rifiutata(self):
        token = capability.emetti(CHIAVE, graph="g", run_id="r1", interaction_id="I001",
                                  action_id="confirm", exp=_exp(timedelta(minutes=5)))
        with self.assertRaises(capability.CapabilityRejected):
            capability.verifica("altra-chiave", token, consumati=self.consumati)

    def test_token_malformato_rifiutato(self):
        with self.assertRaises(capability.CapabilityRejected):
            capability.verifica(CHIAVE, "non-e-un-token", consumati=self.consumati)

    def test_payload_con_campo_mancante_rifiutato(self):
        import base64
        import hashlib
        import hmac
        import json

        corpo = json.dumps({"graph": "g"}).encode("utf-8")
        firma = hmac.new(CHIAVE.encode("utf-8"), corpo, hashlib.sha256).digest()
        b64 = lambda dato: base64.urlsafe_b64encode(dato).rstrip(b"=").decode("ascii")
        token = f"{b64(corpo)}.{b64(firma)}"
        with self.assertRaises(capability.CapabilityRejected):
            capability.verifica(CHIAVE, token, consumati=self.consumati)

    def test_scaduto_rifiutato(self):
        token = capability.emetti(CHIAVE, graph="g", run_id="r1", interaction_id="I001",
                                  action_id="confirm", exp=_exp(-timedelta(minutes=1)))
        with self.assertRaises(capability.CapabilityRejected):
            capability.verifica(CHIAVE, token, consumati=self.consumati)

    def test_riuso_dello_stesso_token_rifiutato(self):
        token = capability.emetti(CHIAVE, graph="g", run_id="r1", interaction_id="I001",
                                  action_id="confirm", exp=_exp(timedelta(minutes=5)))
        capability.verifica(CHIAVE, token, consumati=self.consumati)
        with self.assertRaises(capability.CapabilityRejected):
            capability.verifica(CHIAVE, token, consumati=self.consumati)


class ConsumatiJtiTest(unittest.TestCase):
    def test_prima_volta_vero_seconda_falso(self):
        consumati = capability.ConsumatiJti()
        self.assertTrue(consumati.consuma("j1", exp_epoch=1000.0, now_epoch=0.0))
        self.assertFalse(consumati.consuma("j1", exp_epoch=1000.0, now_epoch=0.0))

    def test_jti_scaduto_viene_potato_e_puo_ripresentarsi(self):
        consumati = capability.ConsumatiJti()
        consumati.consuma("j1", exp_epoch=100.0, now_epoch=0.0)
        self.assertTrue(consumati.consuma("j1", exp_epoch=100.0, now_epoch=200.0))


if __name__ == "__main__":
    unittest.main()
