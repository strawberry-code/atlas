"""D02: render_lite.build() e' l'unica pagina che puo' lasciare la macchina
per '/view' (S11/4). Il test principale e' negativo: verifica che il testo
di un ticket (la domanda di un nodo) e il riassunto di un'Interazione
aperta non compaiano da nessuna parte nella pagina, mentre grafo, titoli e
stati restano leggibili."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))

from core import interactions, mutate, render, render_lite
from core.config import Workspace
from core.store import load

DOMANDA_SEGRETA = "Una domanda dettagliata che non deve mai finire sul telefono XYZZY42"
RIASSUNTO_SEGRETO = "Riassunto di una decisione da non mandare mai al telefono ZQXW77"


def _grafo(tmp: Path):
    ws = Workspace(tmp / ".atlas")
    ref = mutate.create_graph(ws, "prova", "Il Progetto", "Verifica D02")
    with mutate.editing(ref) as graph:
        mutate.add_node(graph, "A01", "Primo nodo", "A", DOMANDA_SEGRETA)
    return ref


class RenderLite(unittest.TestCase):
    def setUp(self):
        import shutil
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.ref = _grafo(self.tmp)

    def _html(self) -> str:
        return render_lite.build(self.ref, load(self.ref.json_path))

    def test_la_domanda_del_nodo_non_compare(self):
        self.assertNotIn(DOMANDA_SEGRETA, self._html())

    def test_il_riassunto_di_una_interazione_aperta_non_compare(self):
        exp = "2099-01-01T00:00:00+00:00"
        with mutate.editing(self.ref) as graph:
            interactions.open_interaction(
                graph, run_id="run-01", node_id="A01", event="decision-required",
                summary=RIASSUNTO_SEGRETO,
                allowed_actions=[{"id": "confirm", "label": "Conferma", "effect": "resume"}],
                expires_at=exp, idempotency_key="run-01:A01:decision")
        self.assertNotIn(RIASSUNTO_SEGRETO, self._html())

    def test_niente_data_island_ne_dashboard_js(self):
        """Niente sheet, niente '#atlas-data': non c'e' nessun ticket da
        aprire su questa pagina (S11/4, 'per leggere un ticket si va al
        computer'), e senza data island lo script della dashboard vera
        andrebbe in errore al primo avvio."""
        html = self._html()
        self.assertNotIn("atlas-data", html)
        self.assertNotIn("<script>", html)

    def test_titolo_id_e_stato_restano_leggibili(self):
        html = self._html()
        self.assertIn("Primo nodo", html)
        self.assertIn("A01", html)
        self.assertIn("Il Progetto", html)

    def test_la_dashboard_vera_non_e_toccata(self):
        """Non regressione: render.build() (senza 'lite') continua a portare
        la domanda del nodo come sempre, dentro la data island per la
        scheda del ticket."""
        html = render.build(self.ref, load(self.ref.json_path))
        self.assertIn(DOMANDA_SEGRETA, html)


if __name__ == "__main__":
    unittest.main()
