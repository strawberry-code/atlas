"""I conflitti di merge lasciati irrisolti: doctor li segnala, 'atlas conflicts'
li mostra e 'atlas conflicts --resolve' li dichiara risolti togliendo il campo.

Il campo 'conflicts' lo scrive il merge driver (provato in test_merge.Driver);
qui si prova il giro che segue, cioe' che chi legge un grafo conflittuale ha gli
strumenti per vederlo e per uscirne. Lavorano su un workspace vero (Base di
test_motore): il campo si inietta come farebbe il driver, scrivendo graph.json.
"""
from __future__ import annotations

import contextlib
import io
import unittest

from tests.test_motore import Base


class ConflittiInUnGrafo(Base):
    """Un grafo popolato con il campo 'conflicts' iniettato come farebbe merge."""

    def conflitto(self, nodo="X", campo="title", tipo="value conflict") -> dict:
        return {"node": nodo, "field": campo, "type": tipo}

    def inietta(self, *conflitti: dict) -> None:
        with self.store.transaction(self.ref.json_path) as data:
            data["conflicts"] = list(conflitti)


class DoctorSegnala(ConflittiInUnGrafo):
    """doctor e' l'attrezzo che serve proprio quando qualcosa e' rotto: un grafo
    con conflitti irrisolti deve essere segnalato, mai far morire la diagnosi."""

    def avvisi(self) -> list[str]:
        return self.doctor.doctor_avvisi(self.store.load(self.ref.json_path),
                                         self.ref, self.ws.config["agent"])

    def test_segnala_i_conflitti_irrisolti_senza_morire(self):
        self.popola()
        self.inietta(self.conflitto(),
                     self.conflitto(nodo="Y", campo="close", tipo="concurrent close"))
        testo = " ".join(self.avvisi())
        self.assertIn("X", testo)
        self.assertIn("Y", testo)
        self.assertIn("close", testo)
        # Il rimedio nomina il comando con cui si esce dal conflitto.
        self.assertIn("conflicts --resolve", testo)

    def test_un_grafo_senza_conflitti_non_ne_parla(self):
        self.popola()
        testo = " ".join(self.avvisi())
        self.assertNotIn("conflitt", testo)


class ComandoConflicts(ConflittiInUnGrafo):
    def chiama(self, *argv: str) -> tuple[int, str]:
        from core import cli
        args = cli.build_parser().parse_args(list(argv))
        uscita = io.StringIO()
        with contextlib.redirect_stdout(uscita):
            rc = cli.dispatch(self.ws, args)
        return rc, uscita.getvalue()

    def test_mostra_i_conflitti_del_grafo(self):
        self.popola()
        self.inietta(self.conflitto(),
                     self.conflitto(nodo="Y", campo="claim.identity", tipo="concurrent claim"))
        rc, testo = self.chiama("conflicts")
        self.assertEqual(0, rc)
        self.assertIn("X", testo)
        self.assertIn("Y", testo)
        self.assertIn("claim.identity", testo)
        self.assertIn("--resolve", testo)

    def test_senza_conflitti_dice_che_non_ce_ne_sono(self):
        self.popola()
        rc, testo = self.chiama("conflicts")
        self.assertEqual(0, rc)
        self.assertIn("nessun", testo)

    def test_resolve_toglie_il_campo_dal_grafo(self):
        self.popola()
        self.inietta(self.conflitto(), self.conflitto(nodo="Y", campo="status", tipo="divergent state"))
        rc, testo = self.chiama("conflicts", "--resolve")
        self.assertEqual(0, rc)
        self.assertIn("X", testo)
        self.assertNotIn("conflicts", self.store.load(self.ref.json_path))
        # Il grafo resta sano e leggibile dopo la risoluzione dichiarata.
        self.doctor.doctor_avvisi(self.store.load(self.ref.json_path),
                                  self.ref, self.ws.config["agent"])

    def test_resolve_senza_conflitti_non_scrive_niente(self):
        self.popola()
        rc, testo = self.chiama("conflicts", "--resolve")
        self.assertEqual(0, rc)
        self.assertIn("nessun", testo)
        self.assertNotIn("conflicts", self.store.load(self.ref.json_path))

    def test_il_parser_accetta_il_comando(self):
        from core import cli
        args = cli.build_parser().parse_args(["conflicts", "--resolve"])
        self.assertEqual("conflicts", args.cmd)
        self.assertTrue(args.resolve)


if __name__ == "__main__":
    unittest.main()
