"""A03: render_edges.edges() innesta la geometria di edge_geometry (A01) sulla
mappa. Il difetto silenzioso di questa geometria e' l'arco che sparisce (un
NaN nel path che non da' errore): qui si verifica che ogni relazione blockedBy
produca un path non vuoto, che l'arco in avanti usi smooth_step_path e quello
di ritorno loop_path con corsia e tratteggio, e che le porte multiple sullo
stesso bordo non si sovrappongano.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))

from core import render_edges
from core.edge_geometry import LOOP_DASH


def _nodo(node_id: str, blocked_by: list[str], status: str = "open") -> dict:
    return {"id": node_id, "status": status, "blockedBy": blocked_by}


class ArcoInAvanti(unittest.TestCase):
    """Il caso comune: il bloccato sta sotto il blocker nel layout a righe."""

    def test_usa_smooth_step_path_senza_corsia(self):
        data = {"nodes": [_nodo("A01", []), _nodo("A02", ["A01"])]}
        pos = {"A01": (100, 0), "A02": (100, 200)}
        svg = render_edges.edges(data, pos, front_ids={"A01"})
        self.assertIn('data-from="A01" data-to="A02"', svg)
        self.assertNotIn("loop", svg)
        self.assertNotIn(f'stroke-dasharray="{LOOP_DASH}"', svg)
        # nessun NaN: l'arco non e' sparito
        self.assertNotIn("nan", svg.lower())

    def test_ogni_dipendenza_produce_un_path(self):
        # una card con molti archi entranti: nessuno deve mancare
        deps = [f"B{i:02d}" for i in range(6)]
        data = {"nodes": [_nodo(d, [], status="closed") for d in deps]
                + [_nodo("C01", deps)]}
        pos = {d: (i * 260, 0) for i, d in enumerate(deps)}
        pos["C01"] = (650, 200)
        svg = render_edges.edges(data, pos, front_ids=set())
        for d in deps:
            self.assertIn(f'data-from="{d}" data-to="C01"', svg)
        # nessun path con la d vuota o con NaN
        for m in re.finditer(r'd="([^"]*)"', svg):
            self.assertTrue(m.group(1), "un path con d vuota e' un arco sparito")
            self.assertNotIn("nan", m.group(1).lower())


class ArcoDiRitorno(unittest.TestCase):
    """Il bloccato non sta sotto il blocker (rango pari o a monte): C08 dice che
    e' sempre un ritorno, e A01 lo vuole su loop_path con corsia e tratteggio."""

    def test_usa_loop_path_con_corsia_e_tratteggio(self):
        # B blocca A, ma nel layout A sta sopra B: back-edge
        data = {"nodes": [_nodo("B01", []), _nodo("A01", ["B01"])]}
        pos = {"B01": (100, 200), "A01": (100, 0)}
        svg = render_edges.edges(data, pos, front_ids={"B01"})
        self.assertIn('class="edge loop da-frontier"', svg)
        self.assertIn(f'stroke-dasharray="{LOOP_DASH}"', svg)
        self.assertNotIn("nan", svg.lower())

    def test_stessa_riga_e_trattata_come_ritorno(self):
        # stesso rango (nessuna delle due righe e' sotto l'altra): non deve
        # passare per smooth_step_path, che presume il bersaglio piu' in basso
        data = {"nodes": [_nodo("B01", []), _nodo("A01", ["B01"])]}
        pos = {"B01": (100, 100), "A01": (400, 100)}
        svg = render_edges.edges(data, pos, front_ids={"B01"})
        self.assertIn("loop", svg)


class Porte(unittest.TestCase):
    """_slots via edges(): due o piu' porte sullo stesso bordo non coincidono."""

    def test_porte_multiple_non_si_sovrappongono(self):
        deps = [f"B{i:02d}" for i in range(4)]
        data = {"nodes": [_nodo(d, [], status="closed") for d in deps]
                + [_nodo("C01", deps)]}
        pos = {d: (i * 260, 0) for i, d in enumerate(deps)}
        pos["C01"] = (390, 200)
        svg = render_edges.edges(data, pos, front_ids=set())
        cx = [float(m.group(1)) for m in re.finditer(r'cx="([\d.]+)"', svg)]
        self.assertEqual(len(cx), len(set(cx)), "due porte sullo stesso bordo coincidono")


if __name__ == "__main__":
    unittest.main()
