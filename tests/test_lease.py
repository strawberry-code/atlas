"""Il lease entra nel lucchetto: host e lease_until, la lente remota, e il consumo
del lucchetto remoto attraverso l'holder di remotelock.py.

Si prova il motore: senza trasporto iniettato il percorso resta local-only
(comportamento di prima, piu' i campi nuovi del claim), con uno stub iniettato
take/close/release consultano la ref remota e non scrivono due verita' sullo
stesso nodo. Il trasporto git-refs vero si prova in test_remotelock.py.
"""
from __future__ import annotations

import importlib
import os
import socket
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "payload"))

from core.remotelock import (ACQUISITO, DISATTIVO, Esito, NON_SCADUTO,  # noqa: E402
                             NON_TUO, RETE, TENUTO)
from tests.test_motore import Base  # noqa: E402


class StubTrasporto:
    """Un trasporto finto: ogni metodo risponde con l'esito assegnato e registra
    le chiamate, cosi' i test vedono cosa ha consultato il motore."""

    def __init__(self):
        self.acquisto = Esito(ACQUISITO)
        self.furto = Esito(ACQUISITO)
        self.rilascio = Esito(ACQUISITO)
        self.rinnovo = Esito(ACQUISITO)
        self.lettura = Esito(ACQUISITO)
        self.chiamate = {"acquire": [], "ruba": [], "rilascia": [], "rinnova": [], "stato": []}

    def acquire(self, nome, host, scadenza):
        self.chiamate["acquire"].append((nome, host, scadenza))
        return self.acquisto

    def ruba(self, nome, host, scadenza):
        self.chiamate["ruba"].append((nome, host, scadenza))
        return self.furto

    def rilascia(self, nome, host):
        self.chiamate["rilascia"].append((nome, host))
        return self.rilascio

    def rinnova(self, nome, host, scadenza):
        self.chiamate["rinnova"].append((nome, host, scadenza))
        return self.rinnovo

    def stato(self, nome):
        self.chiamate["stato"].append(nome)
        return self.lettura

    def elenca(self):
        return []


def _modulo_remotelock():
    """Il modulo core.remotelock della sandbox corrente: Base ne ricarica una copia
    fresca a ogni test, e un riferimento tenuto a livello di modulo punterebbe alla
    sandbox precedente, ormai cancellata."""
    return importlib.import_module("core.remotelock")


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

    def test_senza_trasporto_il_percorso_e_local_only(self):
        self.assertFalse(_modulo_remotelock().attivo())
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        nodo, _ = self.claims.close(self.ref, "F01", "fatto")
        self.assertEqual("closed", nodo["status"])

    def test_reclaim_rinnova_il_lease(self):
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


class LeaseRemoto(Base):
    """Con un trasporto iniettato take/close/release consultano la ref remota, e
    nessuna transizione locale avviene se la ref remota dice di no."""

    def setUp(self):
        super().setUp()
        os.environ["ATLAS_HOST"] = "macchina-test"
        self.stub = StubTrasporto()
        self.remotelock = _modulo_remotelock()
        self.remotelock.set_trasporto(self.stub)

    def tearDown(self):
        self.remotelock.set_trasporto(None)
        os.environ.pop("ATLAS_HOST", None)
        super().tearDown()

    def _futuro(self):
        return int(time.time()) + 3600

    def test_claim_consulta_la_ref_remota(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        self.assertEqual(1, len(self.stub.chiamate["acquire"]))
        nome, host, scadenza = self.stub.chiamate["acquire"][0]
        self.assertIn("F01", nome)
        self.assertEqual("macchina-test", host)
        self.assertGreater(scadenza, int(time.time()))
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("macchina-test", nodo["claim"]["host"])

    def test_claim_rifiuta_una_ref_fresca_di_un_altro(self):
        self.popola()
        self.stub.acquisto = Esito(TENUTO, host="altra-macchina", scadenza=self._futuro())
        with self.assertRaises(self.store.StateError):
            self.claims.claim(self.ref, "F01")
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("open", nodo["status"])
        self.assertEqual([], self.stub.chiamate["ruba"], "una lock fresca non si ruba")

    def test_claim_ruba_una_ref_scaduta(self):
        self.popola()
        self.stub.acquisto = Esito(TENUTO, host="altra-macchina",
                                   scadenza=int(time.time()) - 1)
        self.claims.claim(self.ref, "F01")
        self.assertEqual(1, len(self.stub.chiamate["ruba"]))
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("claimed", nodo["status"])

    def test_claim_rifiuta_se_la_ruba_trova_la_lock_fresca(self):
        self.popola()
        self.stub.acquisto = Esito(TENUTO, host="altra-macchina",
                                   scadenza=int(time.time()) - 1)
        self.stub.furto = Esito(NON_SCADUTO, host="altra-macchina")
        with self.assertRaises(self.store.StateError):
            self.claims.claim(self.ref, "F01")
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("open", nodo["status"])

    def test_claim_fail_closed_se_il_trasporto_risponde_rete(self):
        self.popola()
        self.stub.acquisto = Esito(RETE)
        with self.assertRaises(self.store.StateError):
            self.claims.claim(self.ref, "F01")
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("open", nodo["status"])

    def test_reclaim_rinnova_anche_la_ref_remota(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        self.claims.claim(self.ref, "F01")
        self.assertEqual(1, len(self.stub.chiamate["rinnova"]))

    def test_reclaim_rifiuta_se_la_ref_e_di_un_altro(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        self.stub.rinnovo = Esito(NON_TUO, host="altra-macchina")
        with self.assertRaises(self.store.StateError):
            self.claims.claim(self.ref, "F01")

    def test_release_libera_la_ref_remota(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        self.claims.release(self.ref, "F01")
        self.assertEqual(1, len(self.stub.chiamate["rilascia"]))
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("open", nodo["status"])

    def test_release_rifiuta_se_la_ref_e_di_un_altro_fresca(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        self.stub.rilascio = Esito(NON_TUO, host="altra-macchina")
        with self.assertRaises(self.store.StateError):
            self.claims.release(self.ref, "F01")
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("claimed", nodo["status"])

    def test_release_fail_closed_se_il_trasporto_risponde_rete(self):
        self.popola()
        self.claims.claim(self.ref, "F01")
        self.stub.rilascio = Esito(RETE)
        with self.assertRaises(self.store.StateError):
            self.claims.release(self.ref, "F01")
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("claimed", nodo["status"])

    def test_close_consulta_la_ref_e_rifiuta_se_altrui_fresca(self):
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        self.stub.lettura = Esito(TENUTO, host="altra-macchina", scadenza=self._futuro())
        with self.assertRaises(self.store.StateError):
            self.claims.close(self.ref, "F01", "fatto")

    def test_close_libera_la_ref_dopo_la_chiusura(self):
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        self.stub.lettura = Esito(TENUTO, host="macchina-test", scadenza=self._futuro())
        nodo, _ = self.claims.close(self.ref, "F01", "fatto")
        self.assertEqual("closed", nodo["status"])
        self.assertEqual(1, len(self.stub.chiamate["rilascia"]))

    def test_trasporto_nullo_disattiva_il_remoto(self):
        self.assertTrue(self.remotelock.attivo())
        self.remotelock.set_trasporto(None)
        self.assertFalse(self.remotelock.attivo())
