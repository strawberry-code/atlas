"""D06: apertura/chiusura del tunnel Telegram nel ciclo di vita di un run
Autopilot (_avvia_tunnel_telegram/_ferma_tunnel_telegram), in isolamento dal
resto di execute()."""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))

from core import autopilot


def _run(graph_slug="g", run_id="r1"):
    return types.SimpleNamespace(
        graph=types.SimpleNamespace(slug=graph_slug),
        run_state=types.SimpleNamespace(run_id=run_id),
    )


class AvviaTunnelTelegram(unittest.TestCase):
    def test_nessun_thread_senza_configurazione_relay(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            fermo, thread = autopilot._avvia_tunnel_telegram(_run())
        self.assertIsNone(fermo)
        self.assertIsNone(thread)

    def test_nessun_thread_solo_relay_senza_chiave_capability(self):
        env = {"RELAY_PUBLIC_URL": "https://relay.test", "ATLAS_RELAY_TOKEN_REF": "t"}
        with mock.patch.dict("os.environ", env, clear=True):
            fermo, thread = autopilot._avvia_tunnel_telegram(_run())
        self.assertIsNone(fermo)
        self.assertIsNone(thread)

    def test_nessun_thread_solo_chiave_capability_senza_relay(self):
        with mock.patch.dict("os.environ", {"ATLAS_CAPABILITY_KEY_REF": "k"}, clear=True):
            fermo, thread = autopilot._avvia_tunnel_telegram(_run())
        self.assertIsNone(fermo)
        self.assertIsNone(thread)

    def test_thread_avviato_con_identita_di_installazione_e_fermato_pulito(self):
        env = {
            "RELAY_PUBLIC_URL": "https://relay.test",
            "ATLAS_RELAY_TOKEN_REF": "t",
            "ATLAS_CAPABILITY_KEY_REF": "k",
        }
        chiamate = []

        def fake_esegui(config, installation_id, on_event, stop):
            chiamate.append(installation_id)
            stop.wait()

        installazione = types.SimpleNamespace(installation_id="mia-installazione")
        with mock.patch.dict("os.environ", env, clear=True), \
             mock.patch.object(autopilot.relay_client, "esegui", fake_esegui), \
             mock.patch.object(autopilot.relay_identity, "carica_o_crea", lambda: installazione):
            fermo, thread = autopilot._avvia_tunnel_telegram(_run("mio-grafo", "run-42"))
            self.assertIsNotNone(thread)
            self.assertTrue(thread.is_alive())
            autopilot._ferma_tunnel_telegram(fermo, thread)

        self.assertFalse(thread.is_alive())
        self.assertEqual(chiamate, ["mia-installazione"])

    def test_ferma_senza_thread_non_solleva(self):
        autopilot._ferma_tunnel_telegram(None, None)


if __name__ == "__main__":
    unittest.main()
