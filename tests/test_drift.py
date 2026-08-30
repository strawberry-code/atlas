import json
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SORGENTE = Path(__file__).resolve().parent.parent / "payload"


class Drift(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / ".atlas"
        shutil.copytree(SORGENTE, self.root)
        (self.root / "config.json").write_text(json.dumps({"project": "prova"}), encoding="utf-8")
        (self.root / "graphs").mkdir()
        sys.path.insert(0, str(self.root))
        os.environ["ATLAS_ROOT"] = str(self.root)
        from core import config, mutate, drift
        self.config, self.mutate, self.drift = config, mutate, drift
        self.ws = config.workspace(self.tmp)
        self.ref = mutate.create_graph(self.ws, "prova", "Grafo", "Verificare")

    def tearDown(self):
        sys.path.remove(str(self.root))
        os.environ.pop("ATLAS_ROOT", None)
        for modulo in [m for m in sys.modules if m == "core" or m.startswith("core.")]:
            del sys.modules[modulo]
        shutil.rmtree(self.tmp)

    def _graph(self, config=None):
        if config:
            (self.root / "config.json").write_text(json.dumps(config), encoding="utf-8")
        with self.mutate.editing(self.ref) as g:
            self.mutate.add_branch(g, "G", "Drift", "#000000")
            self.mutate.add_node(g, id="G01", branch="G", title="Primo", question="?")
            self.mutate.add_node(g, id="G02", branch="G", title="Secondo", question="?")
        with self.mutate.editing(self.ref) as g:
            g.node("G01").update(status="closed", closedAt="2026-08-30T10:00:00+02:00",
                                  artifacts=["docs/decision.md", "tests/test_flow.py"])
            g.node("G02").update(status="closed", closedAt="2026-08-30T11:00:00+02:00",
                                  artifacts=["docs/decision.md", "tests/test_flow.py"])

    def test_raccoglie_coppia_solo_con_ordine_temporale_valido(self):
        self._graph()
        from core.store import load
        data = load(self.ref.json_path)
        self.assertEqual([{"earlier": "G01", "later": "G02",
                           "artifacts": ["docs/decision.md", "tests/test_flow.py"]}],
                         self.drift.shared_artifacts(self.ref, data))

    def test_esclude_solo_path_configurati_non_estensioni(self):
        self._graph({"project": "prova", "drift": {"collector_paths": ["tests/test_flow.py", ".md"]}})
        from core.store import load
        segnali = self.drift.shared_artifacts(self.ref, load(self.ref.json_path))
        self.assertEqual(["docs/decision.md"], segnali[0]["artifacts"])

    def test_timestamp_uguale_non_e_un_ordine_valido(self):
        self._graph()
        from core.store import load
        with self.mutate.editing(self.ref) as g:
            g.node("G02")["closedAt"] = "2026-08-30T10:00:00+02:00"
        self.assertEqual([], self.drift.shared_artifacts(self.ref, load(self.ref.json_path)))

    def test_timestamp_non_verificabile_non_produce_coppie(self):
        self._graph()
        from core.store import load
        with self.mutate.editing(self.ref) as g:
            g.node("G02")["closedAt"] = "non-una-data"
        self.assertEqual([], self.drift.shared_artifacts(self.ref, load(self.ref.json_path)))

    def test_segnala_arco_mancante_e_conserva_artefatto_prova(self):
        self._graph()
        from core.store import load
        segnali = self.drift.missing_edges(self.ref, load(self.ref.json_path))
        self.assertEqual([{"earlier": "G01", "later": "G02",
                           "artifacts": ["docs/decision.md", "tests/test_flow.py"]}],
                         segnali)

    def test_non_segnala_dipendenza_diretta(self):
        self._graph()
        from core.store import load
        with self.mutate.editing(self.ref) as g:
            g.node("G02")["blockedBy"] = ["G01"]
        self.assertEqual([], self.drift.missing_edges(self.ref, load(self.ref.json_path)))

    def test_non_segnala_dipendenza_transitiva(self):
        self._graph()
        from core.store import load
        with self.mutate.editing(self.ref) as g:
            self.mutate.add_node(g, id="G03", branch="G", title="Terzo", question="?",
                                 blockedBy=["G02"])
            g.node("G03").update(status="closed", closedAt="2026-08-30T12:00:00+02:00",
                                  artifacts=["docs/decision.md"])
            g.node("G02")["blockedBy"] = ["G01"]
        self.assertEqual([], self.drift.missing_edges(self.ref, load(self.ref.json_path)))

    def test_cli_propone_diagnosi_reale_senza_mutare_il_grafo(self):
        self._graph()
        from core.cli import main
        from core.store import load
        prima = load(self.ref.json_path)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, main(["drift"]))
        testo = output.getvalue()
        self.assertIn("G01", testo)
        self.assertIn("G02", testo)
        self.assertIn("docs/decision.md", testo)
        self.assertIn("non è stato modificato", testo)
        self.assertIn("mutate.link", testo)
        self.assertEqual(prima, load(self.ref.json_path))


if __name__ == "__main__":
    unittest.main()
