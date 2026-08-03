"""Test di install.sh: server HTTP fittizio locale, ATLAS_INSTALL_DIR/ATLAS_INSTALL_URL
puntati a valori di test - nessuna scrittura fuori da cartelle temporanee.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.httpfixture import Fixture  # noqa: E402

INSTALL_SH = ROOT / "install.sh"


class InstallSh(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.fixture = Fixture({"/download/atlas": (200, b"#!/usr/bin/env python3\nfinto\n",
                                                      "application/octet-stream")})
        self.fixture.start()

    def tearDown(self):
        self.fixture.stop()
        shutil.rmtree(self.dir, ignore_errors=True)

    def _lancia(self, **env_extra) -> subprocess.CompletedProcess:
        env = dict(os.environ, ATLAS_INSTALL_DIR=str(self.dir),
                   ATLAS_INSTALL_URL=f"{self.fixture.base_url}/download/atlas", **env_extra)
        return subprocess.run(["sh", str(INSTALL_SH)], env=env, capture_output=True, text=True)

    def test_scarica_e_installa_eseguibile(self):
        esito = self._lancia()
        self.assertEqual(0, esito.returncode, esito.stderr)
        atlas = self.dir / "atlas"
        self.assertTrue(atlas.is_file())
        self.assertTrue(atlas.stat().st_mode & stat.S_IXUSR)
        self.assertIn(b"finto", atlas.read_bytes())

    def test_idempotente(self):
        self._lancia()
        secondo = self._lancia()
        self.assertEqual(0, secondo.returncode, secondo.stderr)
        self.assertTrue((self.dir / "atlas").is_file())

    def test_avviso_path_quando_dir_non_in_path(self):
        # PATH minimo ma reale (curl/sh/mv devono restare raggiungibili): esclude
        # solo self.dir, non spacca lo script.
        esito = self._lancia(PATH="/usr/bin:/bin")
        self.assertEqual(0, esito.returncode, esito.stderr)
        self.assertIn(str(self.dir), esito.stdout)


if __name__ == "__main__":
    unittest.main()
