"""Geometria pura degli archi (A01): arco in avanti ortogonale (smooth_step_path)
e arco di ritorno su corsia laterale (loop_path). Nessun browser: si verifica
solo che il path SVG generato sia valido e che nessun caso produca un NaN, che
altrimenti farebbe sparire l'arco dal canvas senza dare errore.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))

from core import edge_geometry as eg


def _senza_nan(path: str) -> bool:
    return "nan" not in path.lower()


class ArcoInAvanti(unittest.TestCase):
    """smooth_step_path: sorgente sul bordo basso, bersaglio sul bordo alto."""

    def test_arco_dritto(self):
        # stessa x: nessun gomito, il path e' una sola tratta verticale
        d = eg.smooth_step_path(100, 0, 100, 200)
        self.assertTrue(_senza_nan(d))
        self.assertTrue(d.startswith("M100 0"))
        self.assertTrue(d.endswith("L100 200"))
        # nessuna curva Q: e' dritto per tutta la tratta
        self.assertNotIn("Q", d)

    def test_arco_a_gomito(self):
        # x diverse: due segmenti raccordati da due curve
        d = eg.smooth_step_path(100, 0, 300, 200)
        self.assertTrue(_senza_nan(d))
        self.assertTrue(d.startswith("M100 0"))
        self.assertTrue(d.endswith("L300 200"))
        self.assertIn("Q", d)

    def test_raccordo_piu_lungo_del_segmento(self):
        # source e target vicinissimi: il raccordo (corner=10) supera la meta'
        # di ogni segmento, deve clampare invece di sforare o dividere per zero
        d = eg.smooth_step_path(0, 0, 3, 3, corner=10)
        self.assertTrue(_senza_nan(d))
        self.assertTrue(d)

    def test_punti_coincidenti_sorgente_e_bersaglio(self):
        # caso degenere: stesso punto due volte, nessuna divisione deve fallire
        d = eg.smooth_step_path(50, 50, 50, 50)
        self.assertTrue(_senza_nan(d))
        self.assertTrue(d)

    def test_ramo_verso_lalto_resta_robusto(self):
        # il canvas non chiama mai smooth_step_path per un back-edge (passa da
        # loop_path), ma la funzione non deve comunque sparire in NaN se qualcuno
        # la invoca con il bersaglio sopra la sorgente
        d = eg.smooth_step_path(100, 200, 300, 0)
        self.assertTrue(_senza_nan(d))
        self.assertTrue(d)


class RoundedPath(unittest.TestCase):
    """rounded_path: la funzione di piu' basso livello, dove il commento di
    Nodavia avvisa che un NaN qui non da' errore."""

    def test_punti_coincidenti_vengono_scartati(self):
        d = eg.rounded_path([(0, 0), (0, 0), (0, 50), (50, 50), (50, 50)])
        self.assertTrue(_senza_nan(d))
        self.assertTrue(d)

    def test_meno_di_due_punti_utili_da_path_vuoto(self):
        self.assertEqual(eg.rounded_path([(10, 10), (10, 10)]), "")
        self.assertEqual(eg.rounded_path([(10, 10)]), "")

    def test_raccordo_piu_lungo_del_segmento(self):
        d = eg.rounded_path([(0, 0), (2, 0), (2, 2)], corner=10)
        self.assertTrue(_senza_nan(d))
        self.assertTrue(d)


class CorsiaDeiRitorni(unittest.TestCase):
    """loop_path e loop_lane: il back-edge esce dal fondo della sorgente,
    scavalca su una corsia laterale e rientra dall'alto nel bersaglio."""

    def test_corsia_a_destra_quando_la_sorgente_e_a_destra(self):
        # sourceX >= targetX: la corsia sta oltre il piu' a destra dei due
        lane = eg.loop_lane(source_x=300, target_x=100)
        self.assertEqual(lane, 300 + eg.LANE)

    def test_corsia_a_sinistra_quando_la_sorgente_e_a_sinistra(self):
        lane = eg.loop_lane(source_x=100, target_x=300)
        self.assertEqual(lane, 100 - eg.LANE)

    def test_loop_path_senza_nan(self):
        r = eg.loop_path(100, 300, 300, 50)
        self.assertTrue(_senza_nan(r["d"]))
        self.assertTrue(r["d"])
        self.assertIn(str(r["lane"]), r["d"])

    def test_due_versi_producono_due_path_distinti(self):
        # due nodi legati in entrambi i versi (A->B e B->A): le corsie devono
        # cadere su lati opposti, non sovrapporsi sulla stessa riga
        a = (100.0, 300.0)
        b = (300.0, 50.0)
        r_ab = eg.loop_path(a[0], a[1], b[0], b[1])
        r_ba = eg.loop_path(b[0], b[1], a[0], a[1])
        self.assertNotEqual(r_ab["d"], r_ba["d"])
        self.assertNotEqual(r_ab["lane"], r_ba["lane"])
        self.assertTrue(_senza_nan(r_ab["d"]))
        self.assertTrue(_senza_nan(r_ba["d"]))

    def test_rientro_cresce_con_la_lunghezza_del_giro(self):
        # due ritorni piu' lunghi devono rientrare piu' in alto (labelY minore
        # a parita' di target), cosi' piu' archi convergenti non si accavallano
        corto = eg.loop_path(100, 300, 130, 50)
        lungo = eg.loop_path(100, 300, 500, 50)
        self.assertLess(lungo["label_y"], corto["label_y"])


if __name__ == "__main__":
    unittest.main()
