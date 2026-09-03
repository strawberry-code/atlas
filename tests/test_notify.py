"""Coordinatore notifiche: consegne, dedup, esiti e retry bounded."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SORGENTE = Path(__file__).resolve().parent.parent / "payload"


def _record(interaction_id: str, status: str = "open", event: str = "decision-required") -> dict:
    return {"id": interaction_id, "status": status, "event": event, "nodeId": "A01",
            "runId": "run-01", "summary": "Serve una decisione per A01."}


class _FakeChannel:
    def __init__(self, identity: str, fails: int = 0, error: Exception | None = None):
        self.identity = identity
        self.fails = fails
        self.error = error
        self.delivered: list[str] = []

    def deliver(self, interaction):
        if self.fails > 0:
            self.fails -= 1
            raise self.error or RuntimeError("canale non raggiungibile")
        self.delivered.append(interaction["id"])


class NotifyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(SORGENTE))
        from core import channels, notify
        cls.notify = notify
        cls.channels = channels

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(SORGENTE))

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.state = self.notify.NotifyState(self.tmp / "notify-state.json", "grafo")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_pianifica_una_consegna_per_canale_di_ogni_interazione_aperta(self):
        data = {"interactions": [_record("I001"), _record("I002", status="resolved")]}

        dovute = self.notify.plan(data, self.state, ["local", "himalaya"], now=0.0)

        self.assertEqual({("I001", "local"), ("I001", "himalaya")},
                         {(d.interaction_id, d.channel) for d in dovute})

    def test_consegna_riuscita_e_silenziosa_sul_retry_ma_rumorosa_sull_esito(self):
        data = {"interactions": [_record("I001")]}
        registry = self.channels.ChannelRegistry([_FakeChannel("local")])
        policy = self.notify.RetryPolicy(max_attempts=3, initial_delay=0)

        esiti = self.notify.dispatch(data, self.notify.plan(data, self.state, ["local"], 0.0),
                                     registry, self.state, policy, now=0.0)

        self.assertEqual(1, len(esiti))
        self.assertEqual("delivered", esiti[0].status)
        self.assertTrue(esiti[0].escalate)

    def test_deduplica_una_consegna_gia_riuscita(self):
        data = {"interactions": [_record("I001")]}
        registry = self.channels.ChannelRegistry([_FakeChannel("local")])
        policy = self.notify.RetryPolicy(initial_delay=0)

        self.notify.dispatch(data, self.notify.plan(data, self.state, ["local"], 0.0),
                             registry, self.state, policy, now=0.0)
        ancora_dovute = self.notify.plan(data, self.state, ["local"], now=100.0)

        self.assertEqual([], ancora_dovute)

    def test_un_fallimento_ritentabile_resta_silenzioso_finche_il_budget_non_si_esaurisce(self):
        data = {"interactions": [_record("I001")]}
        canale = _FakeChannel("local", fails=1, error=TimeoutError("provider timed out"))
        registry = self.channels.ChannelRegistry([canale])
        policy = self.notify.RetryPolicy(max_attempts=3, initial_delay=60.0)

        primo = self.notify.dispatch(data, self.notify.plan(data, self.state, ["local"], 0.0),
                                     registry, self.state, policy, now=0.0)

        self.assertEqual("pending", primo[0].status)
        self.assertFalse(primo[0].escalate)
        self.assertEqual([], self.notify.plan(data, self.state, ["local"], now=10.0))

        secondo = self.notify.dispatch(data, self.notify.plan(data, self.state, ["local"], 60.0),
                                       registry, self.state, policy, now=60.0)

        self.assertEqual("delivered", secondo[0].status)
        self.assertTrue(secondo[0].escalate)
        self.assertEqual(["I001"], canale.delivered)

    def test_il_budget_esaurito_e_rumoroso_e_smette_di_essere_pianificato(self):
        data = {"interactions": [_record("I001")]}
        registry = self.channels.ChannelRegistry([_FakeChannel("local", fails=99)])
        policy = self.notify.RetryPolicy(max_attempts=2, initial_delay=0)

        primo = self.notify.dispatch(data, self.notify.plan(data, self.state, ["local"], 0.0),
                                     registry, self.state, policy, now=0.0)
        self.assertEqual("pending", primo[0].status)

        secondo = self.notify.dispatch(data, self.notify.plan(data, self.state, ["local"], 0.0),
                                       registry, self.state, policy, now=0.0)

        self.assertEqual("failed", secondo[0].status)
        self.assertTrue(secondo[0].escalate)
        self.assertEqual([], self.notify.plan(data, self.state, ["local"], now=99999.0))

    def test_un_canale_non_registrato_solleva_un_errore_diagnostico(self):
        registry = self.channels.ChannelRegistry()
        with self.assertRaises(self.channels.ChannelRegistryError):
            registry.get("assente")

    def test_registrare_due_volte_la_stessa_identita_e_un_errore(self):
        registry = self.channels.ChannelRegistry([_FakeChannel("local")])
        with self.assertRaises(self.channels.ChannelRegistryError):
            registry.register(_FakeChannel("local"))

    def test_failed_channels_riporta_solo_le_consegne_esaurite(self):
        data = {"interactions": [_record("I001")]}
        registry = self.channels.ChannelRegistry(
            [_FakeChannel("local", fails=99), _FakeChannel("himalaya")])
        policy = self.notify.RetryPolicy(max_attempts=1, initial_delay=0)

        self.notify.dispatch(data, self.notify.plan(data, self.state, ["local", "himalaya"], 0.0),
                             registry, self.state, policy, now=0.0)

        self.assertEqual(["local"], self.state.failed_channels("I001"))

    def test_failed_channels_e_vuoto_senza_consegne_esaurite(self):
        data = {"interactions": [_record("I001")]}
        registry = self.channels.ChannelRegistry([_FakeChannel("local")])
        policy = self.notify.RetryPolicy(initial_delay=0)

        self.notify.dispatch(data, self.notify.plan(data, self.state, ["local"], 0.0),
                             registry, self.state, policy, now=0.0)

        self.assertEqual([], self.state.failed_channels("I001"))
        self.assertEqual([], self.state.failed_channels("I002"))

    def test_lo_stato_sopravvive_al_riavvio(self):
        data = {"interactions": [_record("I001")]}
        registry = self.channels.ChannelRegistry([_FakeChannel("local")])
        policy = self.notify.RetryPolicy(initial_delay=0)
        self.notify.dispatch(data, self.notify.plan(data, self.state, ["local"], 0.0),
                             registry, self.state, policy, now=0.0)

        riavviato = self.notify.NotifyState(self.state.path, "grafo")

        self.assertEqual([], self.notify.plan(data, riavviato, ["local"], now=0.0))
        self.assertEqual("grafo", json.loads(self.state.path.read_text())["graph"])


if __name__ == "__main__":
    unittest.main()
