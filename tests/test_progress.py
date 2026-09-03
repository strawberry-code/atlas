"""Il segnale di avanzamento (H01/4, H02): 'atlas progress' scrive il passo e il
battito dentro il claim gia' esistente. Qui si prova che l'insieme dei passi e'
chiuso, che il segnale costa poco (niente refresh degli artefatti derivati, ne'
tocco a lease_until), che una nota scomoda si normalizza invece di far fallire
la chiamata, e che il comando CLI non esce mai in errore anche quando il segnale
stesso fallisce (nodo non piu' rivendicato, passo fuori elenco).
"""
from __future__ import annotations

import contextlib
import io
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "payload"))

from tests.test_motore import Base  # noqa: E402


class Progress(Base):
    def setUp(self):
        super().setUp()
        self.popola()
        self.claims.claim(self.ref, "F01")

    def _claim(self, node_id="F01"):
        return self.model.node_of(self.store.load(self.ref.json_path), node_id)["claim"]

    def test_scrive_passo_e_battito(self):
        self.claims.progress(self.ref, "F01", "implementing", "a meta' del lavoro")
        claim = self._claim()
        self.assertEqual("implementing", claim["progress"]["step"])
        self.assertEqual("a meta' del lavoro", claim["progress"]["note"])
        self.assertIn("at", claim["progress"])
        self.assertEqual(claim["progress"]["at"], claim["heartbeat"])

    def test_nota_facoltativa(self):
        self.claims.progress(self.ref, "F01", "investigating")
        self.assertIsNone(self._claim()["progress"]["note"])

    def test_nota_normalizzata_non_fallisce(self):
        rumorosa = "riga uno\ncon   spazi\tstrani\n" + ("x" * 300)
        self.claims.progress(self.ref, "F01", "verifying", rumorosa)
        nota = self._claim()["progress"]["note"]
        self.assertNotIn("\n", nota)
        self.assertLessEqual(len(nota), 200)

    def test_sovrascrive_senza_cronologia(self):
        self.claims.progress(self.ref, "F01", "investigating", "primo")
        self.claims.progress(self.ref, "F01", "implementing", "secondo")
        claim = self._claim()
        self.assertEqual("implementing", claim["progress"]["step"])
        self.assertEqual("secondo", claim["progress"]["note"])

    def test_non_tocca_lease_until(self):
        prima = self._claim()["lease_until"]
        self.claims.progress(self.ref, "F01", "implementing")
        self.assertEqual(prima, self._claim()["lease_until"],
                         "il lease segue rinnova_se_necessario, non ogni progress")

    def test_passo_fuori_elenco_rifiutato(self):
        with self.assertRaises(self.store.StateError):
            self.claims.progress(self.ref, "F01", "facendo-cose")

    def test_nodo_non_rivendicato_rifiutato(self):
        with self.assertRaises(self.store.StateError):
            self.claims.progress(self.ref, "F02", "investigating")

    def test_non_rigenera_gli_artefatti_derivati(self):
        dati = self.store.load(self.ref.json_path)
        self.docs.write_stubs(self.ref, dati)
        self.render.write(self.ref, dati)
        prima_dashboard = self.ref.dashboard_path.read_bytes()
        prima_ticket = self.ref.ticket_path("F01").read_bytes()
        self.claims.progress(self.ref, "F01", "implementing", "nota")
        self.assertEqual(prima_dashboard, self.ref.dashboard_path.read_bytes(),
                         "progress non deve rigenerare la dashboard")
        self.assertEqual(prima_ticket, self.ref.ticket_path("F01").read_bytes(),
                         "progress non deve riscrivere il ticket")


class SilentFor(Base):
    """claims.silent_for (H03): il segnale che il runner guarda a fette invece di
    aspettare il tetto assoluto in un colpo solo."""

    def setUp(self):
        super().setUp()
        self.popola()
        self.claims.claim(self.ref, "F01")

    def _node(self):
        return self.model.node_of(self.store.load(self.ref.json_path), "F01")

    def test_nessun_passo_mai_dichiarato_e_none(self):
        """Senza un primo passo il silenzio non si distingue da un lavoro lecito
        che non parla: chi chiama resta col solo tetto assoluto a difesa."""
        self.assertIsNone(self.claims.silent_for(self._node()))

    def test_passo_appena_dichiarato_e_quasi_zero(self):
        self.claims.progress(self.ref, "F01", "implementing")
        fermo = self.claims.silent_for(self._node())
        self.assertIsNotNone(fermo)
        self.assertLess(fermo.total_seconds(), 2)

    def test_battito_invecchiato_dopo_un_passo_conta_il_silenzio_vero(self):
        self.claims.progress(self.ref, "F01", "implementing")
        vecchio = (datetime.now().astimezone() - timedelta(minutes=90)).isoformat(timespec="seconds")
        with self.store.transaction(self.ref.json_path) as data:
            self.model.node_of(data, "F01")["claim"]["heartbeat"] = vecchio
        fermo = self.claims.silent_for(self._node())
        self.assertGreaterEqual(fermo.total_seconds(), 90 * 60 - 5)


class ProgressCLI(Base):
    def setUp(self):
        super().setUp()
        self.popola()
        self.claims.claim(self.ref, "F01")

    def _run(self, *argv):
        from core import cli
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            codice = cli.main(list(argv))
        return codice, buffer.getvalue()

    def test_comando_scrive_e_stampa(self):
        codice, uscita = self._run("progress", "F01", "implementing", "quasi fatto")
        self.assertEqual(0, codice)
        self.assertIn("F01", uscita)
        self.assertIn("implementing", uscita)
        self.assertIn("quasi fatto", uscita)

    def test_comando_non_fallisce_su_nodo_non_rivendicato(self):
        """La garanzia esplicita del nodo: un segnale che fallisce non deve far
        fallire il lavoro. 'F02' non e' rivendicato: il comando lo dice e comunque
        esce con successo, invece di restituire un errore al chiamante."""
        codice, uscita = self._run("progress", "F02", "investigating")
        self.assertEqual(0, codice)
        self.assertIn("F02", uscita)

    def test_comando_rifiuta_un_passo_fuori_elenco_in_fase_di_parsing(self):
        """Il vincolo sintattico lo ferma argparse, prima ancora del motore: e' un
        errore di battitura correggibile subito, non un guasto a runtime."""
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self._run("progress", "F01", "facendo-cose")
