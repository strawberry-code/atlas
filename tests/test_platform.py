"""Test di registry.py e dispatch.py: nessuno tocca ~/.config/atlas.json reale.

ATLAS_CONFIG punta sempre a un file temporaneo, impostato in setUp e tolto
in tearDown - stesso principio di isolamento di ATLAS_ROOT nei test del motore.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from atlascli import dispatch, install_cmd, registry  # noqa: E402
from atlascli import strings as atlascli_strings  # noqa: E402


class Registry(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        os.environ["ATLAS_CONFIG"] = str(self.home / "atlas.json")
        self.progetti = Path(tempfile.mkdtemp())

    def tearDown(self):
        os.environ.pop("ATLAS_CONFIG", None)
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

    def test_lingua_default_globale(self):
        self.assertEqual("it", registry.language_for())
        registry.set_language("en")
        self.assertEqual("en", registry.language_for())

    def test_lingua_override_per_progetto(self):
        path = self._finto_progetto("delta")
        registry.register(path, slug="delta")
        registry.set_language("it")
        self.assertEqual("it", registry.language_for("delta"))  # eredita il default globale
        registry.set_language("en", slug="delta")
        self.assertEqual("en", registry.language_for("delta"))  # override
        self.assertEqual("it", registry.language_for())  # il default globale non cambia

    def test_lingua_su_slug_non_registrato_solleva(self):
        with self.assertRaises(registry.RegistryError):
            registry.set_language("en", slug="mai-registrato")


class Dispatch(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        os.environ["ATLAS_CONFIG"] = str(self.home / "atlas.json")

    def tearDown(self):
        os.environ.pop("ATLAS_CONFIG", None)
        shutil.rmtree(self.home, ignore_errors=True)
        atlascli_strings.set_language("it")  # dispatch.main() muta uno stato di modulo globale

    def test_riservato_prevale_su_tutto(self):
        self.assertIn("install", dispatch.RESERVED)
        self.assertIn("update", dispatch.RESERVED)
        self.assertIn("uninstall", dispatch.RESERVED)
        self.assertIn("list", dispatch.RESERVED)
        self.assertIn("lang", dispatch.RESERVED)

    def test_lang_globale_query_e_set(self):
        self.assertEqual(0, dispatch.main(["lang", "en"]))
        self.assertEqual("en", registry.language_for())
        self.assertEqual(0, dispatch.main(["lang"]))

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


class CollegaSkill(unittest.TestCase):
    """collega_skill() preferisce sempre il symlink: il fallback a copia (install_cmd.py)
    serve solo quando symlink_to non e' permesso, come su Windows senza admin/developer mode."""

    def setUp(self):
        self.target = Path(tempfile.mkdtemp())
        self.root = self.target / ".atlas"
        (self.root / "skills" / "atlas-work").mkdir(parents=True)
        (self.root / "skills" / "atlas-work" / "SKILL.md").write_text("contenuto", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.target, ignore_errors=True)

    def _installer(self) -> install_cmd.Installer:
        return install_cmd.Installer(self.target, SimpleNamespace(dry_run=False), "it")

    def test_symlink_quando_possibile(self):
        self._installer().collega_skill()
        link = self.target / ".claude" / "skills" / "atlas-work"
        self.assertTrue(link.is_symlink())

    def test_fallback_a_copia_se_symlink_fallisce(self):
        with mock.patch.object(Path, "symlink_to", side_effect=OSError("niente symlink qui")):
            self._installer().collega_skill()
        link = self.target / ".claude" / "skills" / "atlas-work"
        self.assertFalse(link.is_symlink())
        self.assertTrue((link / install_cmd.MARCATORE).is_file())
        self.assertEqual("contenuto", (link / "SKILL.md").read_text(encoding="utf-8"))

    def test_copia_si_rigenera_al_reinstall(self):
        with mock.patch.object(Path, "symlink_to", side_effect=OSError("niente symlink qui")):
            self._installer().collega_skill()
        (self.root / "skills" / "atlas-work" / "SKILL.md").write_text("aggiornato", encoding="utf-8")
        with mock.patch.object(Path, "symlink_to", side_effect=OSError("niente symlink qui")):
            self._installer().collega_skill()
        link = self.target / ".claude" / "skills" / "atlas-work"
        self.assertEqual("aggiornato", (link / "SKILL.md").read_text(encoding="utf-8"))

    def test_cartella_estranea_non_simlink_viene_lasciata_stare(self):
        estranea = self.target / ".claude" / "skills" / "atlas-work"
        estranea.mkdir(parents=True)
        (estranea / "roba-mia.txt").write_text("non toccare", encoding="utf-8")
        self._installer().collega_skill()
        self.assertFalse(estranea.is_symlink())
        self.assertTrue((estranea / "roba-mia.txt").is_file())


if __name__ == "__main__":
    unittest.main()
