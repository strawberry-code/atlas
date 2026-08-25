"""Il trasporto git-refs contro un bare repo locale: mai rete vera.

Prova le primitive di L03 portate in Python: acquire vince, la contesa legge il
possessore, ruba solo uno scaduto, rilascia e' idempotente, la rete assente
diventa Rete senza traceback. Il bare repo locale fa da remote condiviso.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "payload"))

from atlascli.remotelock import TrasportoRefsGit  # noqa: E402
from core.remotelock import ACQUISITO, GARA, NON_SCADUTO, NON_TUO, RETE, TENUTO  # noqa: E402


class Trasporto(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.remote = self.tmp / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        self.trasporto = TrasportoRefsGit(str(self.remote), puppet=self.tmp / "puppet")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _futuro(self):
        return int(time.time()) + 3600

    def _passato(self):
        return int(time.time()) - 3600

    def test_acquire_vince_su_una_ref_libera(self):
        esito = self.trasporto.acquire("nodo/F01", "macchina-a", self._futuro())
        self.assertEqual(ACQUISITO, esito.kind)

    def test_la_contesa_legge_il_possessore(self):
        self.trasporto.acquire("nodo/F01", "macchina-a", self._futuro())
        esito = self.trasporto.acquire("nodo/F01", "macchina-b", self._futuro())
        self.assertEqual(TENUTO, esito.kind)
        self.assertEqual("macchina-a", esito.host)

    def test_ruba_solo_una_ref_scaduta(self):
        self.trasporto.acquire("nodo/F01", "macchina-a", self._passato())
        esito = self.trasporto.ruba("nodo/F01", "macchina-b", self._futuro())
        self.assertEqual(ACQUISITO, esito.kind)
        letto = self.trasporto.stato("nodo/F01")
        self.assertEqual(TENUTO, letto.kind)
        self.assertEqual("macchina-b", letto.host)

    def test_ruba_rifiuta_una_ref_fresca(self):
        self.trasporto.acquire("nodo/F01", "macchina-a", self._futuro())
        esito = self.trasporto.ruba("nodo/F01", "macchina-b", self._futuro())
        self.assertEqual(NON_SCADUTO, esito.kind)
        self.assertEqual("macchina-a", esito.host)

    def test_rilascia_la_propria_ref(self):
        self.trasporto.acquire("nodo/F01", "macchina-a", self._futuro())
        esito = self.trasporto.rilascia("nodo/F01", "macchina-a")
        self.assertEqual(ACQUISITO, esito.kind)
        self.assertEqual(ACQUISITO, self.trasporto.stato("nodo/F01").kind)

    def test_rilascia_e_idempotente_su_una_ref_assente(self):
        esito = self.trasporto.rilascia("nodo/F01", "macchina-a")
        self.assertEqual(ACQUISITO, esito.kind)

    def test_rilascia_rifiuta_una_ref_fresca_di_un_altro(self):
        self.trasporto.acquire("nodo/F01", "macchina-a", self._futuro())
        esito = self.trasporto.rilascia("nodo/F01", "macchina-b")
        self.assertEqual(NON_TUO, esito.kind)

    def test_rinnova_allunga_la_propria_ref(self):
        self.trasporto.acquire("nodo/F01", "macchina-a", self._futuro())
        nuova = self._futuro() + 100
        esito = self.trasporto.rinnova("nodo/F01", "macchina-a", nuova)
        self.assertEqual(ACQUISITO, esito.kind)
        letto = self.trasporto.stato("nodo/F01")
        self.assertGreater(letto.scadenza, int(time.time()) + 3500)

    def test_rinnova_rifiuta_una_ref_di_un_altro_fresca(self):
        self.trasporto.acquire("nodo/F01", "macchina-a", self._futuro())
        esito = self.trasporto.rinnova("nodo/F01", "macchina-b", self._futuro())
        self.assertEqual(NON_TUO, esito.kind)

    def test_elenca_le_ref_con_nome_host_e_scadenza(self):
        self.trasporto.acquire("nodo/F01", "macchina-a", self._futuro())
        self.trasporto.acquire("nodo/F02", "macchina-b", self._passato())
        elenco = self.trasporto.elenca()
        self.assertIsInstance(elenco, list)
        self.assertEqual(["nodo/F01", "nodo/F02"], sorted(e.nome for e in elenco))
        per_nome = {e.nome: e for e in elenco}
        self.assertEqual("macchina-a", per_nome["nodo/F01"].host)
        self.assertEqual("macchina-b", per_nome["nodo/F02"].host)

    def test_rete_su_remote_inesistente(self):
        rotto = TrasportoRefsGit(str(self.tmp / "manca.git"))
        self.assertEqual(RETE, rotto.acquire("nodo/F01", "macchina-a", self._futuro()).kind)
        self.assertEqual(RETE, rotto.stato("nodo/F01").kind)
        self.assertEqual(RETE, rotto.rilascia("nodo/F01", "macchina-a").kind)
