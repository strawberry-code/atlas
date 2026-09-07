"""Test di layout_rank.py: catena, ventaglio, ciclo, frammento staccato, catena
lunga a sufficienza da far esplodere una versione ricorsiva di Tarjan/DFS."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))

from core.layout_rank import layout_positions, ranks  # noqa: E402


class Catena(unittest.TestCase):
    def test_rango_cresce_di_uno_per_arco(self):
        ids = ["a", "b", "c", "d"]
        edges = [("a", "b"), ("b", "c"), ("c", "d")]
        r = ranks(ids, edges)
        self.assertEqual(r, {"a": 0, "b": 1, "c": 2, "d": 3})

    def test_posizioni_scendono_e_restano_centrate(self):
        ids = ["a", "b", "c"]
        edges = [("a", "b"), ("b", "c")]
        pos = layout_positions(ids, edges)
        self.assertLess(pos["a"][1], pos["b"][1])
        self.assertLess(pos["b"][1], pos["c"][1])
        self.assertEqual(pos["a"][0], pos["b"][0])
        self.assertEqual(pos["b"][0], pos["c"][0])


class Ventaglio(unittest.TestCase):
    def test_i_figli_condividono_il_rango_e_si_centrano(self):
        ids = ["root", "l", "m", "r"]
        edges = [("root", "l"), ("root", "m"), ("root", "r")]
        r = ranks(ids, edges)
        self.assertEqual(r["root"], 0)
        self.assertEqual({r["l"], r["m"], r["r"]}, {1})
        pos = layout_positions(ids, edges)
        # il figlio centrale sta sull'asse della radice, gli altri due simmetrici
        self.assertEqual(pos["m"][0], pos["root"][0])
        self.assertAlmostEqual(pos["root"][0] - pos["l"][0], pos["r"][0] - pos["root"][0])

    def test_confluenza_prende_il_rango_del_predecessore_piu_basso(self):
        # a -> b -> d, a -> c -> ... -> d con un ramo piu' lungo: d deve stare
        # sotto il predecessore piu' profondo (longest-path), non il primo che
        # lo raggiunge (BFS lo metterebbe al rango 2).
        ids = ["a", "b", "c", "e", "d"]
        edges = [("a", "b"), ("b", "d"), ("a", "c"), ("c", "e"), ("e", "d")]
        r = ranks(ids, edges)
        self.assertEqual(r["d"], 3)


class Ciclo(unittest.TestCase):
    def test_la_componente_ciclica_occupa_piu_righe_e_non_si_appiattisce(self):
        # x <-> y <-> z e' un ciclo di 3; w pende da z e deve stare SOTTO
        # l'ultima riga della componente, non in fila con uno dei suoi membri
        # (il difetto di repo-compare-swarm descritto in layout.ts).
        ids = ["start", "x", "y", "z", "w"]
        edges = [("start", "x"), ("x", "y"), ("y", "z"), ("z", "x"), ("z", "w")]
        r = ranks(ids, edges, start="start")
        componente = {r["x"], r["y"], r["z"]}
        self.assertEqual(len(componente), 3, "il ciclo deve occupare tre righe distinte")
        self.assertGreater(r["w"], max(componente))

    def test_nessun_arco_in_avanti_risale(self):
        # Un arco a valle della componente ciclica che punta a un rango sopra
        # quello del suo mittente sarebbe indistinguibile da un ritorno vero.
        ids = ["start", "x", "y", "z", "w", "fuori"]
        edges = [("start", "x"), ("x", "y"), ("y", "z"), ("z", "x"),
                 ("z", "w"), ("start", "fuori"), ("fuori", "w")]
        r = ranks(ids, edges, start="start")
        for src, dst in edges:
            if dst == "x" and src == "z":
                continue  # il vero back-edge del ciclo: quello puo' risalire
            self.assertLessEqual(r[src], r[dst], f"{src}->{dst} risale: {r[src]} -> {r[dst]}")


class RadiciMultiple(unittest.TestCase):
    """Un grafo Atlas non e' un diagramma di flusso a ingresso singolo: piu'
    rami liberi (nessun predecessore) che convergono dopo sono normali, non
    frammenti staccati. E' il bug trovato validando sui sei grafi veri di
    .atlas/graphs: con una sola radice arbitraria (il primo id della lista,
    come fa layout.ts) un ramo indipendente restava fuori dalla visita di
    raggiungibilita' e veniva spinto sotto tutto il resto, cosi' un arco in
    avanti verso di lui risaliva. ``start=None`` (il default) usa tutti i
    nodi senza predecessori come radici e risolve il caso."""

    def test_due_rami_liberi_che_convergono_restano_al_loro_rango(self):
        ids = ["r1", "a", "r2", "b", "c", "fine"]
        edges = [("r1", "a"), ("a", "fine"), ("r2", "b"), ("b", "c"), ("c", "fine")]
        r = ranks(ids, edges)  # start=None: radici = r1 e r2, entrambe indegree 0
        self.assertEqual(r["r1"], 0)
        self.assertEqual(r["r2"], 0)
        for src, dst in edges:
            self.assertLessEqual(r[src], r[dst], f"{src}->{dst} risale: {r[src]} -> {r[dst]}")


class FrammentoStaccato(unittest.TestCase):
    def test_scende_sotto_tutto_il_resto_e_mantiene_l_ordine(self):
        ids = ["start", "a", "b", "isolato1", "isolato2"]
        edges = [("start", "a"), ("a", "b"), ("isolato1", "isolato2")]
        r = ranks(ids, edges, start="start")
        raggiungibile_max = max(r["start"], r["a"], r["b"])
        self.assertGreater(r["isolato1"], raggiungibile_max)
        self.assertGreater(r["isolato2"], r["isolato1"])


class CatenaLunga(unittest.TestCase):
    def test_stack_esplicito_non_esplode_il_limite_di_ricorsione(self):
        n = 6000
        ids = [str(i) for i in range(n)]
        edges = [(str(i), str(i + 1)) for i in range(n - 1)]
        self.assertLess(sys.getrecursionlimit(), n)
        r = ranks(ids, edges)
        self.assertEqual(r["0"], 0)
        self.assertEqual(r[str(n - 1)], n - 1)

    def test_stack_esplicito_regge_anche_con_un_ciclo_in_coda(self):
        n = 4000
        ids = [str(i) for i in range(n)] + ["c1", "c2"]
        edges = [(str(i), str(i + 1)) for i in range(n - 1)]
        edges += [(str(n - 1), "c1"), ("c1", "c2"), ("c2", "c1")]
        pos = layout_positions(ids, edges)
        self.assertEqual(len(pos), len(ids))


if __name__ == "__main__":
    unittest.main()
