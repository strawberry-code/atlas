"""Test della registrazione del merge driver git al momento dell'install.

La registrazione scrive due cose quando il progetto e' una repo git: la riga in
.gitattributes (radice del working tree) e la voce nel config git locale. Niente
da scrivere, e nessun errore, quando il progetto non e' una repo. Tutto avviene
in cartelle temporanee; le worktree vere chiedono git, e si saltano se manca.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from atlascli import install_cmd  # noqa: E402
from atlascli.install_cmd import (ATTRIBUTI_MERGE, config_con_driver,  # noqa: E402
                                  config_gia_registrato)

HA_GIT = shutil.which("git") is not None


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


class RegistraMergeDriver(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _installer(self, dry_run: bool = False) -> install_cmd.Installer:
        return install_cmd.Installer(self.dir, SimpleNamespace(dry_run=dry_run), "it")

    def _repo(self) -> Path:
        esito = _git("init", "-q", cwd=self.dir)
        if esito.returncode != 0:
            self.skipTest(f"git init non disponibile: {esito.stderr}")
        return self.dir

    def test_repo_registra_config_e_attributi(self):
        self._repo()
        self._installer().registra_merge_driver()
        attr = (self.dir / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn(ATTRIBUTI_MERGE, attr)
        self.assertIn("merge=atlas-graph", attr)
        cfg = (self.dir / ".git" / "config").read_text(encoding="utf-8")
        self.assertIn('[merge "atlas-graph"]', cfg)
        self.assertIn("driver = atlas merge-graph %O %A %B", cfg)

    def test_ripetuto_non_duplica(self):
        self._repo()
        for _ in range(2):
            self._installer().registra_merge_driver()
        attr = (self.dir / ".gitattributes").read_text(encoding="utf-8")
        self.assertEqual(1, attr.count(ATTRIBUTI_MERGE))
        cfg = (self.dir / ".git" / "config").read_text(encoding="utf-8")
        self.assertEqual(1, cfg.count('[merge "atlas-graph"]'))
        self.assertEqual(1, cfg.count("atlas merge-graph %O %A %B"))

    def test_non_repo_non_fa_nulla_senza_errori(self):
        self._installer().registra_merge_driver()
        self.assertFalse((self.dir / ".gitattributes").exists())

    def test_gitattributes_esistente_viene_esteso(self):
        self._repo()
        (self.dir / ".gitattributes").write_text("*.py linguist-language=Python\n", encoding="utf-8")
        self._installer().registra_merge_driver()
        testo = (self.dir / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("*.py linguist-language=Python", testo)
        self.assertIn(ATTRIBUTI_MERGE, testo)

    def test_gitattributes_ha_la_riga_resta_com_era(self):
        self._repo()
        (self.dir / ".gitattributes").write_text(ATTRIBUTI_MERGE + "\n", encoding="utf-8")
        self._installer().registra_merge_driver()
        self.assertEqual(ATTRIBUTI_MERGE + "\n",
                         (self.dir / ".gitattributes").read_text(encoding="utf-8"))

    def test_config_esistente_non_viene_sovrascritto(self):
        self._repo()
        config = self.dir / ".git" / "config"
        prima = config.read_text(encoding="utf-8")
        self._installer().registra_merge_driver()
        dopo = config.read_text(encoding="utf-8")
        self.assertIn(prima, dopo)  # il contenuto preesistente resta intero
        self.assertIn("driver = atlas merge-graph %O %A %B", dopo)

    def test_dry_run_dice_e_non_scrive(self):
        self._repo()
        inst = self._installer(dry_run=True)
        inst.registra_merge_driver()
        self.assertFalse((self.dir / ".gitattributes").exists())
        cfg = (self.dir / ".git" / "config").read_text(encoding="utf-8")
        self.assertNotIn("atlas merge-graph", cfg)
        self.assertTrue(any("scriverebbe" in r for r in inst.fatti))

    @unittest.skipUnless(HA_GIT, "git non disponibile")
    def test_worktree_registra_sul_config_comune(self):
        self._repo()
        wt = self.dir / "wt"
        esito = _git("worktree", "add", "-q", "-b", "wt-branch", str(wt), cwd=self.dir)
        if esito.returncode != 0:
            self.skipTest(f"git worktree non disponibile: {esito.stderr}")
        install_cmd.Installer(wt, SimpleNamespace(dry_run=False), "it").registra_merge_driver()
        # il config del repo principale porta il driver, condiviso dalle worktree
        cfg = (self.dir / ".git" / "config").read_text(encoding="utf-8")
        self.assertIn("driver = atlas merge-graph %O %A %B", cfg)
        # e il .gitattributes sta nella radice del working tree del progetto
        self.assertIn(ATTRIBUTI_MERGE, (wt / ".gitattributes").read_text(encoding="utf-8"))


class ConfigHelpers(unittest.TestCase):
    def test_config_gia_registrato_riconosce_la_sezione_giusta(self):
        con = '[merge "atlas-graph"]\n\tdriver = atlas merge-graph %O %A %B\n'
        self.assertTrue(config_gia_registrato(con))
        altro = '[merge "other"]\n\tdriver = atlas merge-graph %O %A %B\n'
        self.assertFalse(config_gia_registrato(altro))
        niente = "[core]\n\trepositoryformatversion = 0\n"
        self.assertFalse(config_gia_registrato(niente))

    def test_config_con_driver_aggiunge_la_sezione_in_coda(self):
        risultato = config_con_driver("[core]\n\trepositoryformatversion = 0\n")
        self.assertIn("[core]", risultato)
        self.assertIn('[merge "atlas-graph"]', risultato)
        self.assertIn("driver = atlas merge-graph %O %A %B", risultato)
        # da vuoto parte la sezione, senza riga bianca di testa
        self.assertFalse(config_con_driver("").startswith("\n"))


if __name__ == "__main__":
    unittest.main()
