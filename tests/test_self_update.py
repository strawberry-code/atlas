"""Test di self_update.py: server HTTP fittizio locale, nessuna rete vera.

'ATLAS_UPDATE_BASE_URL' punta il modulo al fixture invece che a api.github.com;
sys.argv[0] punta a un eseguibile finto in una cartella temporanea, cosi' lo
scambio atomico non tocca niente di reale.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from atlascli import self_update  # noqa: E402
from tests.httpfixture import Fixture  # noqa: E402


class SelfUpdate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.target = self.tmp / "atlas"
        self.target.write_bytes(b"vecchia versione\n")
        self.target.chmod(0o755)
        self._argv0 = sys.argv[0]
        sys.argv[0] = str(self.target)
        self.fixture = Fixture({})
        self.fixture.start()
        os.environ["ATLAS_UPDATE_BASE_URL"] = self.fixture.base_url

    def tearDown(self):
        self.fixture.stop()
        sys.argv[0] = self._argv0
        os.environ.pop("ATLAS_UPDATE_BASE_URL", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _pubblica(self, tag: str, blob: bytes, sha_giusto: bool = True) -> None:
        digest = hashlib.sha256(blob).hexdigest() if sha_giusto else "0" * 64
        release = {
            "tag_name": tag,
            "assets": [
                {"name": "atlas", "browser_download_url": f"{self.fixture.base_url}/asset/atlas"},
                {"name": "atlas.sha256",
                 "browser_download_url": f"{self.fixture.base_url}/asset/atlas.sha256"},
            ],
        }
        self.fixture.routes["/repos/strawberry-code/atlas/releases/latest"] = (
            200, json.dumps(release).encode("utf-8"), "application/json")
        self.fixture.routes["/asset/atlas"] = (200, blob, "application/octet-stream")
        self.fixture.routes["/asset/atlas.sha256"] = (
            200, f"{digest}  atlas\n".encode("utf-8"), "text/plain")

    def test_nessuna_versione_nuova_non_scarica_nulla(self):
        self._pubblica("v0.0.0-dev", b"qualsiasi")
        self.assertEqual(0, self_update.cmd_update(None))
        self.assertEqual(b"vecchia versione\n", self.target.read_bytes())

    def test_versione_nuova_sostituisce_atomicamente(self):
        nuovo = b"nuova versione\n"
        self._pubblica("v9.9.9", nuovo)
        self.assertEqual(0, self_update.cmd_update(None))
        self.assertEqual(nuovo, self.target.read_bytes())
        self.assertTrue(self.target.stat().st_mode & 0o111)

    def test_sha_mismatch_rifiuta(self):
        self._pubblica("v9.9.9", b"nuova versione\n", sha_giusto=False)
        self.assertEqual(1, self_update.cmd_update(None))
        self.assertEqual(b"vecchia versione\n", self.target.read_bytes())

    def test_404_messaggio_pulito_senza_traceback(self):
        self.assertEqual(1, self_update.cmd_update(None))  # nessuna route registrata


if __name__ == "__main__":
    unittest.main()
