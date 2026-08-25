"""I bordi del lucchetto fra macchine (L07): la finestra condivisa vede anche la
verita' remota, e senza rete il lucchetto degrada invece di fingere.

Due frontiere si provano qui. La finestra condivisa: _condiviso consulta le ref
remote via elenca(), e una ref presa da un'altra macchina durante la lavorazione
e' una collisione come una chiusura locale. L'assenza di rete: le letture (status,
rinnovo-su-lettura) degradano con avviso senza morire, le mutazioni (take nuovo,
close, release) restano fail-closed perche' scrivere senza sapere creerebbe due
verita' sullo stesso nodo, e doctor riferisce lo stato del lucchetto senza morire.
"""
from __future__ import annotations

import contextlib
import importlib
import io
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "payload"))

from core.remotelock import ACQUISITO, Esito, RETE, TENUTO  # noqa: E402
from tests.test_motore import Base  # noqa: E402


class StubTrasporto:
    """Un trasporto finto che risponde agli esiti assegnati e registra le chiamate.

    elenca() e' configurabile: un Esito (RETE) o una lista per la finestra remota,
    oppure un'eccezione per provare il trasporto che alza invece di rispondere."""

    def __init__(self):
        self.acquisto = Esito(ACQUISITO)
        self.furto = Esito(ACQUISITO)
        self.rilascio = Esito(ACQUISITO)
        self.rinnovo = Esito(ACQUISITO)
        self.lettura = Esito(ACQUISITO)
        self.elenco: list | Esito | Exception = []
        self.chiamate = {"acquire": [], "ruba": [], "rilascia": [],
                         "rinnova": [], "stato": [], "elenca": 0}

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
        self.chiamate["elenca"] += 1
        if isinstance(self.elenco, Exception):
            raise self.elenco
        return self.elenco


def _modulo_remotelock():
    """Il modulo core.remotelock della sandbox corrente, ricaricato a ogni test."""
    return importlib.import_module("core.remotelock")


class FinestraCondivisaRemota(Base):
    """La finestra condivisa vede anche le ref remote: una lock presa da un'altra
    macchina durante la lavorazione e' una collisione per la deduzione degli artefatti,
    anche quando il grafo locale e' in ritardo di sync (la ref e' la verita' remota)."""

    def setUp(self):
        super().setUp()
        os.environ["ATLAS_HOST"] = "macchina-io"
        os.environ["ATLAS_IDENTITY"] = "io"
        self.stub = StubTrasporto()
        self.remotelock = _modulo_remotelock()
        self.remotelock.set_trasporto(self.stub)
        self.popola()
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")

    def tearDown(self):
        self.remotelock.set_trasporto(None)
        os.environ.pop("ATLAS_HOST", None)
        os.environ.pop("ATLAS_IDENTITY", None)
        super().tearDown()

    def _ttl(self):
        return self.ws.config["agent"]["lease_ttl_seconds"]

    def _ref(self, node_id, host, scadenza):
        return Esito(TENUTO, host=host, scadenza=scadenza,
                     nome=f"{self.ref.slug}/{node_id}")

    def _condiviso(self, da=None):
        data = self.store.load(self.ref.json_path)
        return self.claims._condiviso(self.ref, data, "F01",
                                      da or datetime.now().astimezone())

    def test_ref_remota_nella_finestra_e_collisione(self):
        """Una lock presa da un'altra macchina durante la finestra blocca la deduzione
        e l'avviso nomina il nodo, come per una chiusura locale."""
        self.stub.elenco = [self._ref("F02", "altra-macchina",
                                      int(time.time()) + self._ttl())]
        nodo, avviso = self.claims.close(self.ref, "F01", "fatto")
        self.assertEqual([], nodo["artifacts"])
        self.assertIsNotNone(avviso)
        self.assertIn("F02", avviso)
        self.assertIn("--artefatti", avviso)

    def test_ref_remota_antecedente_la_finestra_ignorata(self):
        """Una lock presa prima della presa non sporca la finestra: era gia' li'."""
        prima = datetime.now().astimezone() - timedelta(minutes=5)
        self.stub.elenco = [self._ref("F02", "altra-macchina",
                                      int(time.time()) - 2 * self._ttl())]
        self.assertIsNone(self._condiviso(prima))

    def test_ref_di_un_altro_grafo_ignorata(self):
        """Le ref degli altri grafi non sporcano la finestra di questo."""
        self.stub.elenco = [Esito(TENUTO, host="altra-macchina",
                                  scadenza=int(time.time()) + self._ttl(),
                                  nome="altro-grafo/F02")]
        self.assertIsNone(self._condiviso())

    def test_ref_della_mia_macchina_ignorata(self):
        """Le nostre ref non sono una collisione: le teniamo noi."""
        self.stub.elenco = [self._ref("F02", "macchina-io",
                                      int(time.time()) + self._ttl())]
        self.assertIsNone(self._condiviso())

    def test_ref_sul_nodo_che_si_chiude_ignorata(self):
        """La ref del nodo in chiusura non conta: la sta liberando la chiusura."""
        self.stub.elenco = [self._ref("F01", "altra-macchina",
                                      int(time.time()) + self._ttl())]
        self.assertIsNone(self._condiviso())

    def test_senza_trasporto_la_finestra_e_di_oggi(self):
        """Col lucchetto remoto spento elenca non viene nemmeno consultato."""
        self.remotelock.set_trasporto(None)
        self.assertIsNone(self._condiviso())
        self.assertEqual(0, self.stub.chiamate["elenca"])

    def test_elenca_rete_vale_come_collisione(self):
        """Un remote che non risponde non permette di escludere il lavoro altrui:
        artefatti non dedotti, e la deduzione non muore."""
        self.stub.elenco = Esito(RETE)
        nodo, avviso = self.claims.close(self.ref, "F01", "fatto")
        self.assertEqual([], nodo["artifacts"])
        self.assertIsNotNone(avviso)
        self.assertIn("--artefatti", avviso)

    def test_elenca_che_alza_vale_come_collisione(self):
        """Un trasporto che alza invece di rispondere non fa morire close."""
        self.stub.elenco = RuntimeError("rete rotta")
        nodo, avviso = self.claims.close(self.ref, "F01", "fatto")
        self.assertEqual([], nodo["artifacts"])
        self.assertIsNotNone(avviso)


class SenzaRete(Base):
    """Senza rete il lucchetto non finge: le letture degradano con avviso, le
    mutazioni restano fail-closed, doctor riferisce lo stato senza morire."""

    def setUp(self):
        super().setUp()
        os.environ["ATLAS_IDENTITY"] = "senza-rete"
        os.environ["ATLAS_HOST"] = "macchina-senza-rete"
        self.stub = StubTrasporto()
        self.remotelock = _modulo_remotelock()
        self.remotelock.set_trasporto(self.stub)
        self.popola()

    def tearDown(self):
        self.remotelock.set_trasporto(None)
        os.environ.pop("ATLAS_IDENTITY", None)
        os.environ.pop("ATLAS_HOST", None)
        super().tearDown()

    def _claim_stantio(self):
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        with self.store.transaction(self.ref.json_path) as data:
            claim = self.model.node_of(data, "F01")["claim"]
            claim["lease_until"] = (datetime.now().astimezone()
                                    + timedelta(seconds=-60)).isoformat(timespec="seconds")

    def _lease(self):
        return self.model.node_of(self.store.load(self.ref.json_path), "F01")["claim"]["lease_until"]

    def test_status_degrada_con_avviso_senza_rete(self):
        """Il difetto di L06: status moriva se la ref non si rinnovava e la rete non
        rispondeva. Ora degrada: stato locale, avviso chiaro, zero traceback."""
        self._claim_stantio()
        self.stub.rinnovo = Esito(RETE)
        from core import cli
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(0, cli.main(["status"]))
        self.assertIn("remote non raggiungibile", buffer.getvalue())
        self.assertLess(datetime.fromisoformat(self._lease()),
                        datetime.now().astimezone(),
                        "il lease locale non si allunga: non si finge una lock rinnovata")

    def test_rinnovo_degrada_senza_scrivere(self):
        self._claim_stantio()
        self.stub.rinnovo = Esito(RETE)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertFalse(self.claims.rinnova_se_necessario(self.ref))
        self.assertIn("remote non raggiungibile", buffer.getvalue())
        self.assertLess(datetime.fromisoformat(self._lease()),
                        datetime.now().astimezone(), "il claim resta stantio")

    def test_reclaim_degrada_senza_rete(self):
        """take sul proprio nodo con la rete giu': il nodo resta nostro, il lease
        non si allunga, e non si alza (il reclaim non crea nessuna verita' nuova)."""
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        self.stub.rinnovo = Esito(RETE)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            nodo = self.claims.claim(self.ref, "F01")
        self.assertIn("remote non raggiungibile", buffer.getvalue())
        self.assertEqual("claimed", nodo["status"])

    def test_take_nuovo_fail_closed_senza_rete(self):
        """take su un nodo libero con la rete giu' non scrive: senza la ref non sai
        chi lo tiene, e due macchine che si pestano e' il fallimento da evitare."""
        self.stub.acquisto = Esito(RETE)
        with self.assertRaises(self.store.StateError):
            self.claims.claim(self.ref, "F01")
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("open", nodo["status"])

    def test_release_fail_closed_senza_rete(self):
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        self.stub.rilascio = Esito(RETE)
        with self.assertRaises(self.store.StateError):
            self.claims.release(self.ref, "F01")
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("claimed", nodo["status"])

    def test_close_fail_closed_senza_rete(self):
        self.rispondi("F01")
        self.claims.claim(self.ref, "F01")
        self.stub.lettura = Esito(RETE)
        with self.assertRaises(self.store.StateError):
            self.claims.close(self.ref, "F01", "fatto")
        nodo = self.model.node_of(self.store.load(self.ref.json_path), "F01")
        self.assertEqual("claimed", nodo["status"])

    def test_close_forzato_degrada_con_avviso_senza_rete(self):
        """Con --force close salta la consulta remota, ma la deduzione degli artefatti
        non puo' escludere il lavoro altrui e si dichiara: niente attribuzione cieca."""
        self._claim_stantio()
        self.stub.rinnovo = Esito(RETE)
        self.stub.lettura = Esito(RETE)
        self.stub.elenco = Esito(RETE)
        nodo, avviso = self.claims.close(self.ref, "F01", "fatto", force=True)
        self.assertEqual("closed", nodo["status"])
        self.assertIsNotNone(avviso)
        self.assertIn("--artefatti", avviso)

    def test_doctor_non_muore_e_riferisce_la_rete(self):
        self.stub.elenco = Esito(RETE)
        data = self.store.load(self.ref.json_path)
        avvisi = self.doctor.doctor_avvisi(data, self.ref, self.ws.config["agent"])
        self.assertTrue(any("remoto" in a for a in avvisi),
                        "doctor deve dire che il remote non risponde")

    def test_doctor_silenzio_con_remoto_raggiungibile(self):
        self.stub.elenco = []
        data = self.store.load(self.ref.json_path)
        avvisi = self.doctor.doctor_avvisi(data, self.ref, self.ws.config["agent"])
        self.assertFalse(any("remoto" in a or "lock.remote" in a for a in avvisi))

    def test_doctor_riferisce_spento_se_dichiarato_ma_non_attivo(self):
        """Config dichiara lock.remote ma il trasporto non e' stato iniettato: le
        macchine non si proteggono a vicenda, e doctor lo dice."""
        self.remotelock.set_trasporto(None)
        (self.root / "config.json").write_text(
            '{"project": "prova", "lock": {"remote": "file:///fake"}}', encoding="utf-8")
        data = self.store.load(self.ref.json_path)
        avvisi = self.doctor.doctor_avvisi(data, self.ref, self.ws.config["agent"])
        self.assertTrue(any("lock.remote" in a for a in avvisi))
