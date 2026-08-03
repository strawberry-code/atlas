"""Test di registry.py e dispatch.py: nessuno tocca ~/.atlas reale.

ATLAS_HOME punta sempre a una cartella temporanea, impostata in setUp e tolta
in tearDown - stesso principio di isolamento di ATLAS_ROOT nei test del motore.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from atlascli import dispatch, registry  # noqa: E402


class Registry(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        os.environ["ATLAS_HOME"] = str(self.home)
        self.progetti = Path(tempfile.mkdtemp())

    def tearDown(self):
        os.environ.pop("ATLAS_HOME", None)
        shutil.rmtree(self.home, ignore_errors=True)
        shutil.rmtree(self.progetti, ignore_errors=True)

    def _finto_progetto(self, nome: str) -> Path:
        path = self.progetti / nome
        (path / ".atlas" / "core").mkdir(parents=True)
        (path / ".atlas" / "VERSION").write_text("0.1.0\n", encoding="utf-8")
        return path

    def test_slugify(self):
        self.assertEqual("mio-progetto", registry.slugify("Mio Progetto"))
        self.assertEqual("a-b-c", registry.slugify("a_b__c!!"))
        self.assertEqual("progetto", registry.slugify("///"))

    def test_round_trip(self):
        path = self._finto_progetto("alfa")
        slug = registry.register(path)
        self.assertEqual("alfa", slug)
        self.assertEqual(path.resolve(), registry.resolve("alfa"))

    def test_stesso_path_riusa_la_voce(self):
        path = self._finto_progetto("beta")
        registry.register(path, slug="beta")
        slug = registry.register(path)  # nessuno slug esplicito, path gia' noto
        self.assertEqual("beta", slug)
        self.assertEqual(1, len(registry.load()["projects"]))

    def test_collisione_slug_yes_rifiuta(self):
        p1, p2 = self._finto_progetto("g1"), self._finto_progetto("g2")
        registry.register(p1, slug="stesso")
        with self.assertRaises(registry.RegistryError):
            registry.register(p2, slug="stesso", yes=True)
        self.assertEqual(p1.resolve(), registry.resolve("stesso"))

    def test_collisione_slug_interattiva_annulla(self):
        p1, p2 = self._finto_progetto("g3"), self._finto_progetto("g4")
        registry.register(p1, slug="stesso")
        with self.assertRaises(registry.RegistryError):
            registry.register(p2, slug="stesso", chiedi=lambda _: "n")
        self.assertEqual(p1.resolve(), registry.resolve("stesso"))

    def test_collisione_slug_interattiva_conferma(self):
        p1, p2 = self._finto_progetto("g5"), self._finto_progetto("g6")
        registry.register(p1, slug="stesso")
        registry.register(p2, slug="stesso", chiedi=lambda _: "y")
        self.assertEqual(p2.resolve(), registry.resolve("stesso"))

    def test_prune_rimuove_path_mancanti(self):
        vivo = self._finto_progetto("vivo")
        morto = self._finto_progetto("morto")
        registry.register(vivo)
        registry.register(morto)
        shutil.rmtree(morto)
        tolti = registry.prune()
        self.assertEqual(["morto"], tolti)
        self.assertIsNone(registry.resolve("morto"))
        self.assertIsNotNone(registry.resolve("vivo"))

    def test_status_of(self):
        path = self._finto_progetto("gamma")
        self.assertEqual(registry.STATO_OK, registry.status_of(path))
        self.assertEqual(registry.STATO_MANCANTE, registry.status_of(self.progetti / "mai-esistito"))
        shutil.rmtree(path / ".atlas" / "core")
        self.assertEqual(registry.STATO_NON_VALIDO, registry.status_of(path))


class Dispatch(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        os.environ["ATLAS_HOME"] = str(self.home)

    def tearDown(self):
        os.environ.pop("ATLAS_HOME", None)
        shutil.rmtree(self.home, ignore_errors=True)

    def test_riservato_prevale_su_tutto(self):
        self.assertIn("install", dispatch.RESERVED)
        self.assertIn("update", dispatch.RESERVED)
        self.assertIn("uninstall", dispatch.RESERVED)
        self.assertIn("list", dispatch.RESERVED)

    def test_radice_locale_risale_le_cartelle(self):
        base = Path(tempfile.mkdtemp())
        try:
            (base / ".atlas" / "core").mkdir(parents=True)
            profonda = base / "a" / "b" / "c"
            profonda.mkdir(parents=True)
            self.assertEqual(base, dispatch._radice_locale(profonda))
            self.assertIsNone(dispatch._radice_locale(Path(tempfile.gettempdir())))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_comando_sconosciuto_ritorna_1(self):
        vuota = Path(tempfile.mkdtemp())
        try:
            cwd = os.getcwd()
            os.chdir(vuota)
            try:
                self.assertEqual(1, dispatch.main(["comando-inesistente"]))
            finally:
                os.chdir(cwd)
        finally:
            shutil.rmtree(vuota, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
