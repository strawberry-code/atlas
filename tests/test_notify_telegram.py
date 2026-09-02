"""Verifica il canale Telegram (D07): come si compone il testo e i bottoni,
i guasti permanenti dichiarati (relay o capability non configurati) e il
rispetto del contratto 'channels.Channel' usato dal coordinatore (C01).
Nessuna rete reale: 'sender' e' sempre un doppio finto."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SORGENTE = Path(__file__).resolve().parent.parent / "payload"
sys.path.insert(0, str(SORGENTE))

from core import capability, notify_telegram, relay_client  # noqa: E402
from core.retry import PermanentError  # noqa: E402

CHIAVE = "una-chiave-di-prova"
ENV_COMPLETO = {
    "RELAY_HTTPS_HOSTNAME": "relay.test",
    "ATLAS_RELAY_TOKEN_REF": "il-bearer",
    "ATLAS_CAPABILITY_KEY_REF": CHIAVE,
}


def _interaction(**over):
    base = {
        "id": "I001", "graph": "prova", "nodeId": "B02", "runId": "run-01",
        "event": "decision-required", "summary": "Serve una decisione per B02.",
        "expiresAt": "2099-01-01T00:00:00+00:00",
        "allowedActions": [
            {"id": "confirm", "label": "Conferma", "effect": "resume"},
            {"id": "decline", "label": "Rifiuta", "effect": "cancel"},
        ],
    }
    base.update(over)
    return base


class Testo(unittest.TestCase):
    def test_porta_nodo_etichetta_e_summary(self):
        testo = notify_telegram._testo(_interaction())
        self.assertIn("B02", testo)
        self.assertIn("decisione richiesta", testo)
        self.assertIn("Serve una decisione per B02.", testo)

    def test_evento_sconosciuto_passa_cosi_com_e(self):
        testo = notify_telegram._testo(_interaction(event="qualcosa-di-nuovo"))
        self.assertIn("qualcosa-di-nuovo", testo)


class Bottoni(unittest.TestCase):
    def test_un_bottone_per_azione_con_capability_valida(self):
        bottoni = notify_telegram._bottoni(_interaction(), CHIAVE)
        self.assertEqual([label for label, _ in bottoni], ["Conferma", "Rifiuta"])
        consumati = capability.ConsumatiJti()
        for (_, token), azione in zip(bottoni, _interaction()["allowedActions"]):
            payload = capability.verifica(CHIAVE, token, consumati=consumati)
            self.assertEqual(payload["graph"], "prova")
            self.assertEqual(payload["runId"], "run-01")
            self.assertEqual(payload["interactionId"], "I001")
            self.assertEqual(payload["actionId"], azione["id"])

    def test_jti_diverso_per_ogni_bottone(self):
        bottoni = notify_telegram._bottoni(_interaction(), CHIAVE)
        self.assertNotEqual(bottoni[0][1], bottoni[1][1])


class TelegramChannelTest(unittest.TestCase):
    def test_senza_relay_configurato_e_un_guasto_permanente(self):
        chiamate = []
        canale = notify_telegram.TelegramChannel(env={}, sender=lambda *a: chiamate.append(a))
        with self.assertRaises(PermanentError):
            canale.deliver(_interaction())
        self.assertEqual([], chiamate)

    def test_senza_capability_key_e_un_guasto_permanente(self):
        env = {"RELAY_HTTPS_HOSTNAME": "relay.test", "ATLAS_RELAY_TOKEN_REF": "il-bearer"}
        chiamate = []
        canale = notify_telegram.TelegramChannel(env=env, sender=lambda *a: chiamate.append(a))
        with self.assertRaises(PermanentError):
            canale.deliver(_interaction())
        self.assertEqual([], chiamate)

    def test_deliver_passa_config_graph_testo_e_bottoni_al_sender(self):
        chiamate = []
        canale = notify_telegram.TelegramChannel(
            env=ENV_COMPLETO, sender=lambda *a: chiamate.append(a))
        canale.deliver(_interaction())
        self.assertEqual(1, len(chiamate))
        config, graph, testo, bottoni = chiamate[0]
        self.assertIsInstance(config, relay_client.TunnelConfig)
        self.assertEqual(config.base_url, "https://relay.test")
        self.assertEqual(config.token, "il-bearer")
        self.assertEqual(graph, "prova")
        self.assertIn("B02", testo)
        self.assertEqual([label for label, _ in bottoni], ["Conferma", "Rifiuta"])

    def test_sender_di_default_e_relay_client_invia_messaggio(self):
        self.assertIs(notify_telegram.TelegramChannel()._sender, relay_client.invia_messaggio)


class Registro(unittest.TestCase):
    def test_registry_registra_il_canale_telegram_sotto_la_sua_identita(self):
        reg = notify_telegram.registry()
        self.assertEqual(notify_telegram.IDENTITY, reg.get("telegram").identity)

    def test_registry_accetta_un_canale_finto_per_i_test(self):
        finto = notify_telegram.TelegramChannel(sender=lambda *a: None)
        reg = notify_telegram.registry(finto)
        self.assertIs(finto, reg.get("telegram"))

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(SORGENTE))


if __name__ == "__main__":
    unittest.main()
