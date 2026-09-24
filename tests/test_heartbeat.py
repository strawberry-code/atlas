"""Il rinnovo-su-lettura del battito (L06): chi tiene un nodo lo rinnova quando la
sessione lavora, non solo al claim. La primitiva sta in claims.py, il gancio nel
dispatcher (cli.py); qui si prova la primitiva e il gancio end-to-end.

Si prova che: il rinnovo scatta su un lease stantio e non tocca un lease fresco;
la cadenza (meta' del TTL) e' rispettata; il rinnovo tocca solo i claim nostri.
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "payload"))

from tests.test_motore import Base  # noqa: E402


class Battito(Base):
    """Il rinnovo locale: senza trasporto iniettato il percorso resta identico a
    oggi (solo il claim si aggiorna), con la soglia che evita il churn."""

    def setUp(self):
        super().setUp()
        os.environ["ATLAS_IDENTITY"] = "battito"
        os.environ["ATLAS_HOST"] = "macchina-battito"
        self.popola()

    def tearDown(self):
        os.environ.pop("ATLAS_IDENTITY", None)
        os.environ.pop("ATLAS_HOST", None)
        super().tearDown()

    def _claim(self, node_id="F01"):
        self.claims.claim(self.ref, node_id)
        return self.model.node_of(self.store.load(self.ref.json_path), node_id)

    def _invecchia(self, node_id, secondi):
        """Porta il lease di un claim a secondi da adesso (negativo = scaduto)."""
        with self.store.transaction(self.ref.json_path) as data:
            claim = self.model.node_of(data, node_id)["claim"]
            claim["lease_until"] = (datetime.now().astimezone()
                                    + timedelta(seconds=secondi)).isoformat(timespec="seconds")

    def _lease(self, node_id):
        return self.model.node_of(self.store.load(self.ref.json_path),
                                  node_id)["claim"]["lease_until"]

    def test_rinnova_un_lease_stantio(self):
        self._claim()
        self._invecchia("F01", -60)          # scaduto da un minuto
        self.assertTrue(self.claims.rinnova_se_necessario(self.ref))
        scadenza = datetime.fromisoformat(self._lease("F01"))
        self.assertGreater(scadenza, datetime.now().astimezone() + timedelta(minutes=30),
                           "il rinnovo sposta la scadenza avanti di un TTL")

    def test_non_tocca_un_lease_fresco(self):
        self._claim()
        prima = self.ref.json_path.read_bytes()
        self.assertFalse(self.claims.rinnova_se_necessario(self.ref))
        self.assertEqual(prima, self.ref.json_path.read_bytes(),
                         "un lease fresco non scrive il grafo")

    def test_la_cadenza_rispetta_la_soglia_di_meta_ttl(self):
        self._claim()
        meta = self.ws.config["agent"]["lease_ttl_seconds"] // 2
        self._invecchia("F01", meta + 1)     # manca piu' della meta': nessun rinnovo
        self.assertFalse(self.claims.rinnova_se_necessario(self.ref))
        self._invecchia("F01", meta - 1)     # manca meno della meta': il rinnovo scatta
        self.assertTrue(self.claims.rinnova_se_necessario(self.ref))

    def test_non_rinnova_i_claim_di_un_altro(self):
        self._claim()
        with self.store.transaction(self.ref.json_path) as data:
            claim = self.model.node_of(data, "F01")["claim"]
            claim["host"] = "altra-macchina"
            claim["lease_until"] = (datetime.now().astimezone()
                                    + timedelta(seconds=-60)).isoformat(timespec="seconds")
        self.assertFalse(self.claims.rinnova_se_necessario(self.ref))
        claim = self.model.node_of(self.store.load(self.ref.json_path), "F01")["claim"]
        self.assertEqual("altra-macchina", claim["host"], "un claim altrui non si tocca")

    def test_il_percorso_e_local_only(self):
        self._claim()
        self._invecchia("F01", -60)
        self.assertTrue(self.claims.rinnova_se_necessario(self.ref))
        self.assertGreater(datetime.fromisoformat(self._lease("F01")),
                           datetime.now().astimezone())

    def test_senza_identita_non_rinnova_niente(self):
        self._claim()
        self._invecchia("F01", -60)
        os.environ.pop("ATLAS_IDENTITY", None)
        self.assertFalse(self.claims.rinnova_se_necessario(self.ref))
        self.assertLess(datetime.fromisoformat(self._lease("F01")),
                        datetime.now().astimezone(), "il lease resta stantio")

    def test_un_claim_senza_lease_until_si_migra(self):
        self._claim()
        with self.store.transaction(self.ref.json_path) as data:
            del self.model.node_of(data, "F01")["claim"]["lease_until"]
        self.assertTrue(self.claims.rinnova_se_necessario(self.ref))
        self.assertIn("lease_until", self.model.node_of(
            self.store.load(self.ref.json_path), "F01")["claim"])

    def test_status_da_cli_rinnova_un_lease_stantio(self):
        from core import cli
        self._claim()
        self._invecchia("F01", -60)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, cli.main(["status"]))
        self.assertGreater(datetime.fromisoformat(self._lease("F01")),
                           datetime.now().astimezone())

    def test_status_da_cli_non_scrive_su_un_lease_fresco(self):
        from core import cli
        self._claim()
        prima = self.ref.json_path.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, cli.main(["status"]))
        self.assertEqual(prima, self.ref.json_path.read_bytes(),
                         "status con lease fresco non riscrive il grafo")
