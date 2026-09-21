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
import unittest.mock
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
    """Un ritorno e' un arco che chiude un ciclo (graph_walk.back_edges), e
    A01 lo vuole su loop_path con corsia e tratteggio. Non lo decide la
    geometria: prima bastava trascinare una card sopra il suo blocker perche'
    un arco in avanti diventasse un finto ritorno tratteggiato."""

    def test_un_ciclo_usa_loop_path_con_corsia_e_tratteggio(self):
        # A01 e B01 si bloccano a vicenda: uno dei due archi e' un ritorno
        data = {"nodes": [_nodo("B01", ["A01"]), _nodo("A01", ["B01"])]}
        pos = {"B01": (100, 0), "A01": (100, 200)}
        svg = render_edges.edges(data, pos, front_ids={"B01"})
        self.assertEqual(len(re.findall(r'class="edge loop', svg)), 1)
        self.assertIn(f'stroke-dasharray="{LOOP_DASH}"', svg)
        self.assertNotIn("nan", svg.lower())

    def test_un_arco_che_risale_senza_ciclo_resta_in_avanti(self):
        # B blocca A e nel disegno A sta sopra B (una card trascinata): niente
        # ciclo, quindi niente corsia ne' tratteggio, e il path esiste lo stesso
        data = {"nodes": [_nodo("B01", []), _nodo("A01", ["B01"])]}
        for pos in ({"B01": (100, 200), "A01": (100, 0)}, {"B01": (100, 100), "A01": (400, 100)}):
            with self.subTest(pos=pos):
                svg = render_edges.edges(data, pos, front_ids={"B01"})
                self.assertNotIn("loop", svg)
                self.assertNotIn("stroke-dasharray", svg)
                m = re.search(r' d="([^"]*)"', svg)
                self.assertTrue(m and m.group(1))
                self.assertNotIn("nan", svg.lower())


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


class TrasparenzaSottoLeCard(unittest.TestCase):
    """render_svg.canvas() disegna lo stato a riposo di backing e ritagli dentro
    due contenitori fissi: ghosts.js li svuota e li rifa' a ogni trascinamento,
    quindi devono esserci anche quando a riposo non contengono niente."""

    def test_i_contenitori_esistono_e_il_ritaglio_segue_la_card(self):
        from core import render_svg
        # A01 -> A03 passa sotto A02, messa in colonna fra i due
        def nodo(i, deps):
            return {**_nodo(i, deps), "title": i, "question": "?", "mode": "HITL", "branch": "b", "type": "task"}
        data = {"nodes": [nodo("A01", []), nodo("A02", []), nodo("A03", ["A01"])], "branches": {"b": {}}}
        pos = {"A01": (100, 0), "A02": (100, 200), "A03": (100, 400)}
        with unittest.mock.patch.object(render_svg, "positions", return_value=pos):
            svg = render_svg.canvas(data, front_ids=set(), gruppi={})
        self.assertIn('<g class="edge-backings"><rect class="edge-backing" x="100" y="200"', svg)
        self.assertIn('<g class="edge-ghosts"><clipPath id="clip-A02">', svg)
        self.assertIn('data-ghost-from="A01" data-ghost-to="A03"', svg)
        with unittest.mock.patch.object(render_svg, "positions", return_value={**pos, "A02": (600, 200)}):
            svg = render_svg.canvas(data, front_ids=set(), gruppi={})
        self.assertIn('<g class="edge-backings"></g>', svg)
        self.assertIn('<g class="edge-ghosts"></g>', svg)
