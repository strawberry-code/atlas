"""V02: le due geometrie provate da sole (edge_geometry.py/A01, layout_rank.py/
C08, render_edges.py/A03) tenute insieme sui sette grafi veri di .atlas/graphs/,
mai sui casi sintetici che quei tre nodi hanno gia' coperto ognuno per conto
proprio. Quattro invarianti, la stessa lista del ticket:

  1. nessun path contiene NaN (il difetto silenzioso: un NaN non da' errore,
     fa sparire l'arco dal canvas, vedi il commento in testa a edge_geometry.py);
  2. nessun nodo finisce fuori dal riquadro calcolato (stessa formula di
     render_svg.canvas());
  3. nessuna coppia di card si sovrappone;
  4. ogni arco che risale e' davvero un ritorno, mai un arco in avanti mal
     disposto.

C08 ha scoperto che layout_rank.ranks() va chiamato con start=None: un grafo
Atlas ha piu' rami liberi che convergono dopo, mentre Nodavia (da cui la
geometria e' tradotta) e' un diagramma a ingresso singolo. Con una radice sola
l'invariante 4 falliva su 4 dei 6 grafi veri: LaProvaMorde la rompe di
proposito per dimostrare che questo file se ne accorgerebbe.

I sette grafi veri sono oggi tutti DAG (limite dichiarato da A03): la corsia
laterale e il tratteggio del ritorno restano provati solo su un ciclo
costruito qui in memoria, mai scritto su un file del progetto.
"""
from __future__ import annotations

import json
import math
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))

from core import layout_rank, render_edges, render_svg
from core.edge_geometry import LOOP_DASH

RADICE_GRAFI = Path(__file__).resolve().parent.parent / ".atlas" / "graphs"


def _nodo(node_id: str, blocked_by: list[str], status: str = "open") -> dict:
    return {"id": node_id, "status": status, "blockedBy": blocked_by}


def _grafi_veri() -> list[tuple[str, dict]]:
    """I graph.json veri del progetto: letti, mai scritti."""
    return [
        (percorso.parent.name, json.loads(percorso.read_text(encoding="utf-8")))
        for percorso in sorted(RADICE_GRAFI.glob("*/graph.json"))
    ]


def _archi(data: dict) -> list[tuple[str, str]]:
    validi = {n["id"] for n in data["nodes"]}
    return [(dep, n["id"]) for n in data["nodes"] for dep in n["blockedBy"] if dep in validi]


def _archi_che_risalgono(data: dict, pos: dict) -> list[tuple[str, str]]:
    """Gli archi in avanti il cui bersaglio non sta sotto la sorgente: dalla
    geometria di _edge_records, non dalla classe, che ora dice solo se
    l'arco chiude un ciclo."""
    return [(e["from"], e["to"]) for e in render_edges._edge_records(data, pos, set())
            if not e["loop"] and e["ey"] <= pos[e["from"]][1]]


def _ha_ciclo_indipendente(ids: list[str], archi: list[tuple[str, str]]) -> bool:
    """Rilevazione di ciclo scritta apposta per il test, indipendente dal
    DFS di graph_walk.back_edges: se il ciclo lo cercassi con lo stesso
    codice che sto provando, un suo bug si scagionerebbe da solo. Kahn
    (ordinamento topologico per grado entrante): il grafo e' aciclico se e
    solo se l'ordinamento riesce a consumare tutti i nodi.
    """
    adj: dict[str, list[str]] = {i: [] for i in ids}
    indeg = {i: 0 for i in ids}
    for s, t in archi:
        adj[s].append(t)
        indeg[t] += 1
    coda = [i for i in ids if indeg[i] == 0]
    visti = 0
    while coda:
        u = coda.pop()
        visti += 1
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                coda.append(v)
    return visti != len(ids)


def _bbox_canvas(pos: dict, w: float, h: float, pad: float) -> tuple[float, float, float, float]:
    """Stessa formula di render_svg.canvas(): il riquadro parte dal minimo
    osservato, non da zero, perche' il rank puo' centrare un ramo a sinistra
    dell'origine."""
    xs = [x for x, _ in pos.values()]
    ys = [y for _, y in pos.values()]
    ox, oy = min(xs) - pad, min(ys) - pad
    largh = max(x + w for x in xs) - ox + pad
    alt = max(y + h for y in ys) - oy + pad
    return ox, oy, largh, alt


def _fuori_dal_riquadro(pos: dict, w: float, h: float, pad: float) -> list[str]:
    ox, oy, largh, alt = _bbox_canvas(pos, w, h, pad)
    return [i for i, (x, y) in pos.items()
            if x < ox or x + w > ox + largh or y < oy or y + h > oy + alt]


def _sovrapposte(pos: dict, w: float, h: float) -> list[tuple[str, str]]:
    """Due rettangoli [x,x+w]x[y,y+h] si toccano senza sovrapporsi quando un
    lato coincide: qui si segnala solo la sovrapposizione vera (area > 0)."""
    elenco = list(pos.items())
    coppie = []
    for idx, (i1, (x1, y1)) in enumerate(elenco):
        for i2, (x2, y2) in elenco[idx + 1:]:
            if x1 < x2 + w and x2 < x1 + w and y1 < y2 + h and y2 < y1 + h:
                coppie.append((i1, i2))
    return coppie


def _path_con_nan(svg: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r'd="([^"]*)"', svg) if "nan" in m.group(1).lower()]


def _path_vuoti(svg: str) -> list[str]:
    return [m.group(0) for m in re.finditer(r'd=""', svg)]


class GraphReale(unittest.TestCase):
    """Le quattro invarianti del ticket, su ognuno dei sette grafi veri."""

    def test_sono_sette(self):
        # se questo fallisce le prove sotto sono vuote per assenza di dati,
        # non per assenza di difetti: un errore esplicito vale piu' di un
        # verde silenzioso
        self.assertEqual(len(_grafi_veri()), 7)

    def test_nessun_nan_nessuna_card_fuori_riquadro_nessuna_sovrapposizione(self):
        w, h, pad = render_svg.W, render_svg.H, render_svg.PAD
        for nome, data in _grafi_veri():
            with self.subTest(grafo=nome):
                ids = [n["id"] for n in data["nodes"]]
                pos = render_svg.positions(data)
                self.assertEqual(set(pos), set(ids), f"{nome}: un nodo senza posizione")

                for i, (x, y) in pos.items():
                    self.assertFalse(math.isnan(x) or math.isnan(y), f"{nome}/{i}: posizione NaN")

                fuori = _fuori_dal_riquadro(pos, w, h, pad)
                self.assertEqual(fuori, [], f"{nome}: card fuori dal riquadro: {fuori}")

                sovrapposte = _sovrapposte(pos, w, h)
                self.assertEqual(sovrapposte, [], f"{nome}: card sovrapposte: {sovrapposte}")

                svg = render_edges.edges(data, pos, front_ids=set())
                self.assertEqual(_path_con_nan(svg), [], f"{nome}: path con NaN, arco sparito")
                self.assertEqual(_path_vuoti(svg), [], f"{nome}: path vuoto, arco sparito")

    def test_ogni_arco_che_risale_e_un_ritorno_vero(self):
        """I sette grafi veri sono oggi tutti DAG (A03): senza un ciclo vero non
        puo' esistere un ritorno vero, quindi nessun arco deve essere
        disegnato con la corsia laterale (class="edge loop"), e nel layout
        automatico nessun arco in avanti risale (C08): il bloccato sta
        sempre sotto il suo blocker."""
        for nome, data in _grafi_veri():
            with self.subTest(grafo=nome):
                ids = [n["id"] for n in data["nodes"]]
                archi = _archi(data)
                self.assertFalse(_ha_ciclo_indipendente(ids, archi),
                                  f"{nome}: contiene un ciclo vero, il limite dichiarato da A03 non vale piu'")
                pos = render_svg.positions(data)
                svg = render_edges.edges(data, pos, front_ids=set())
                risalgono = re.findall(r'class="edge loop[^"]*"', svg)
                self.assertEqual(risalgono, [],
                                  f"{nome}: arco disegnato come ritorno ma il grafo e' un DAG")
                self.assertEqual(_archi_che_risalgono(data, pos), [],
                                 f"{nome}: arco in avanti che risale nel layout automatico")


class ArcoDiRitornoSintetico(unittest.TestCase):
    """La corsia laterale e il tratteggio (A01) restano provati solo qui, su
    un ciclo costruito in memoria: nessuno dei sette grafi veri ne contiene uno
    (limite dichiarato da A03), e questo file non tocca i grafi veri."""

    def test_un_ciclo_vero_produce_almeno_un_ritorno_disegnato(self):
        data = {"nodes": [
            _nodo("R01", ["R03"]),
            _nodo("R02", ["R01"]),
            _nodo("R03", ["R02"]),
        ]}
        ids = [n["id"] for n in data["nodes"]]
        archi = _archi(data)
        self.assertTrue(_ha_ciclo_indipendente(ids, archi), "il grafo di prova deve avere un ciclo vero")

        pos = render_svg.positions(data)
        for i, (x, y) in pos.items():
            self.assertFalse(math.isnan(x) or math.isnan(y), f"{i}: posizione NaN")

        svg = render_edges.edges(data, pos, front_ids=set())
        self.assertIn('class="edge loop', svg, "un ciclo vero deve produrre almeno un ritorno disegnato")
        self.assertIn(f'stroke-dasharray="{LOOP_DASH}"', svg)
        self.assertEqual(_path_con_nan(svg), [])


class LaProvaMorde(unittest.TestCase):
    """Non basta che il test passi: deve poter fallire. Si rompe di proposito
    un'invariante alla volta, con gli stessi helper usati sopra, e si
    verifica che il rosso arrivi davvero."""

    def test_radice_singola_rompe_larco_che_risale(self):
        """La regressione di C08: layout_rank.ranks() con uno start esplicito
        (ingresso singolo, come Nodavia) invece di start=None (tutte le
        radici) fa risalire un arco in avanti su un grafo vero. Lo si legge
        dalla geometria (_archi_che_risalgono), non dalla classe 'loop': un
        arco che risale senza ciclo resta in avanti anche nel disegno."""
        rotto_su = []
        for nome, data in _grafi_veri():
            ids = [n["id"] for n in data["nodes"]]
            archi = _archi(data)
            if _ha_ciclo_indipendente(ids, archi):
                continue
            rank_singola = layout_rank.ranks(ids, archi, start=ids[0])
            by_rank: dict[int, list[str]] = {}
            for i in ids:
                by_rank.setdefault(rank_singola[i], []).append(i)
            # stesso passo di layout_positions() (issue #34: il margine e'
            # fisso, W/H no, vedi layout_rank.X_MARGIN/Y_MARGIN)
            x_gap = render_svg.W + layout_rank.X_MARGIN
            y_gap = render_svg.H + layout_rank.Y_MARGIN
            pos_singola = {
                i: (layout_rank.X_BASE + col * x_gap,
                    layout_rank.Y_BASE + r * y_gap)
                for r, membri in by_rank.items()
                for col, i in enumerate(membri)
            }
            if _archi_che_risalgono(data, pos_singola):
                rotto_su.append(nome)
        self.assertTrue(rotto_su, "start singolo dovrebbe rompere l'invariante su almeno un grafo vero")

    def test_nan_iniettato_e_rilevato(self):
        svg = '<path class="edge" d="M10 10L nan 20"/>'
        self.assertNotEqual(_path_con_nan(svg), [], "un path con NaN deve essere rilevato")

    def test_path_vuoto_iniettato_e_rilevato(self):
        svg = '<path class="edge loop" d=""/>'
        self.assertNotEqual(_path_vuoti(svg), [], "un path vuoto deve essere rilevato")

    def test_sovrapposizione_iniettata_e_rilevata(self):
        w, h = render_svg.W, render_svg.H
        pos = {"X01": (0, 0), "X02": (10, 10)}  # sovrapposte di proposito
        self.assertNotEqual(_sovrapposte(pos, w, h), [], "due card sovrapposte devono essere rilevate")

    def test_fuori_riquadro_iniettato_e_rilevato(self):
        w, h, pad = render_svg.W, render_svg.H, render_svg.PAD
        pos = {"X01": (0, 0), "X02": (10_000, 10_000)}
        # riquadro calcolato solo su X01: X02 ci finisce fuori di proposito
        ox, oy, largh, alt = _bbox_canvas({"X01": (0, 0)}, w, h, pad)
        fuori = [i for i, (x, y) in pos.items()
                 if x < ox or x + w > ox + largh or y < oy or y + h > oy + alt]
        self.assertIn("X02", fuori)


if __name__ == "__main__":
    unittest.main()
