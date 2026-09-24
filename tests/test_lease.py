"""Il lease entra nel lucchetto: host e lease_until, e la lente remota con cui
un lettore giudica un claim di un'altra macchina.
"""
from __future__ import annotations

import os
import socket
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "payload"))

from tests.test_motore import Base  # noqa: E402


class LeaseCampi(Base):
    """Senza trasporto il percorso e' local-only: i campi nuovi ci sono, ma la
    liveness resta quella di prima (PID locale, lease per i lettori remoti)."""

    def _claim_remoto(self, node_id, host="altra-macchina", secondi=3600):
        """Riscrive il claim di un nodo come se l'avesse scritto un'altra macchina."""
        with self.store.transaction(self.ref.json_path) as data:
            claim = self.model.node_of(data, node_id)["claim"]
            claim["host"] = host
            claim["pid"] = 999999
            claim["lease_until"] = (datetime.now().astimezone()
                                    + timedelta(seconds=secondi)).isoformat(timespec="seconds")

    def test_claim_scrive_host_e_lease_until(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        claim = self.model.node_of(self.store.load(self.ref.json_path), "F01")["claim"]
        self.assertEqual(socket.gethostname(), claim["host"])
        self.assertGreater(datetime.fromisoformat(claim["lease_until"]),
                           datetime.now().astimezone())

    def test_il_percorso_e_local_only(self):
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        nodo, _ = self.claims.close(self.ref, "F01", "fatto")
        self.assertEqual("closed", nodo["status"])

    def test_reclaim_rinnova_il_lease(self):
        with mock.patch.dict(os.environ, {"ATLAS_IDENTITY": "test-session"}):
            self.popola()
            self.claims.claim(self.ref, "F01")
            prima = self.model.node_of(self.store.load(self.ref.json_path), "F01")["claim"]["lease_until"]
            self.claims.claim(self.ref, "F01")
            dopo = self.model.node_of(self.store.load(self.ref.json_path), "F01")["claim"]["lease_until"]
        self.assertGreaterEqual(dopo, prima)

    def test_claim_state_locale_usa_il_pid(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        with self.store.transaction(self.ref.json_path) as data:
            self.model.node_of(data, "F01")["claim"]["pid"] = 999999
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("dead", self.claims.claim_state(nodo, self.ws.config["agent"]))

    def test_claim_state_remoto_live_ignora_il_pid(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        self._claim_remoto("F01", secondi=3600)      # pid morto, lease fresco
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("live", self.claims.claim_state(nodo, self.ws.config["agent"]))

    def test_claim_state_remoto_dead_a_lease_scaduto(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        self._claim_remoto("F01", secondi=-3600)
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("dead", self.claims.claim_state(nodo, self.ws.config["agent"]))

    def test_claim_state_remoto_senza_lease_until_e_fresco(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        self._claim_remoto("F01", secondi=3600)
        with self.store.transaction(self.ref.json_path) as data:
            del self.model.node_of(data, "F01")["claim"]["lease_until"]
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("live", self.claims.claim_state(nodo, self.ws.config["agent"]))

    def test_claim_state_delegato_live_col_lease_anche_senza_pid(self):
        """Un claim on_behalf_of (Autopilot per conto del provider) non porta il PID
        di chi lavora davvero: senza la lente del lease sarebbe sempre 'dead', un
        lucchetto vivo scambiato per orfano mentre l'agente delegato lo sta lavorando."""
        self.popola()
        self.claims.claim(self.ref, "F01", on_behalf_of="codex-luna")
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertIsNone(nodo["claim"]["pid"])
        self.assertEqual("live", self.claims.claim_state(nodo, self.ws.config["agent"]))

    def test_claim_state_delegato_dead_a_lease_scaduto(self):
        self.popola()
        self.claims.claim(self.ref, "F01", on_behalf_of="codex-luna")
        with self.store.transaction(self.ref.json_path) as data:
            claim = self.model.node_of(data, "F01")["claim"]
            claim["lease_until"] = (datetime.now().astimezone()
                                    - timedelta(seconds=3600)).isoformat(timespec="seconds")
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("dead", self.claims.claim_state(nodo, self.ws.config["agent"]))

    def test_close_rifiuta_un_claim_remoto_fresco(self):
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        self._claim_remoto("F01", secondi=3600)
        with self.assertRaises(self.store.StateError) as caso:
            self.claims.close(self.ref, "F01", "fatto")
        self.assertIn("altra-macchina", str(caso.exception))

    def test_close_permette_un_claim_remoto_scaduto(self):
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        self._claim_remoto("F01", secondi=-3600)
        nodo, _ = self.claims.close(self.ref, "F01", "fatto")
        self.assertEqual("closed", nodo["status"])
