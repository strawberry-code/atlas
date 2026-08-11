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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from atlascli import registry, self_update  # noqa: E402
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


class CheckForUpdate(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture({})
        self.fixture.start()
        os.environ["ATLAS_UPDATE_BASE_URL"] = self.fixture.base_url
        # Usa una cartella temporanea per il registro, non il file reale dell'utente
        self.home = Path(tempfile.mkdtemp())
        os.environ["ATLAS_CONFIG"] = str(self.home / "atlas.json")

    def tearDown(self):
        self.fixture.stop()
        os.environ.pop("ATLAS_UPDATE_BASE_URL", None)
        os.environ.pop("ATLAS_CONFIG", None)
        shutil.rmtree(self.home, ignore_errors=True)

    def _pubblica_release(self, tag: str) -> None:
        """Pubblica una release fittizia nel fixture HTTP."""
        release = {
            "tag_name": tag,
            "assets": [
                {"name": "atlas", "browser_download_url": f"{self.fixture.base_url}/asset/atlas"},
            ],
        }
        self.fixture.routes["/repos/strawberry-code/atlas/releases/latest"] = (
            200, json.dumps(release).encode("utf-8"), "application/json")

    def test_nessun_cache_chiama_la_rete(self):
        """Senza cache, check_for_update() chiama la rete."""
        self._pubblica_release("v9.9.9")
        risultato = self_update.check_for_update()
        # Se la versione corrente è inferiore a 9.9.9, ritorna la nuova versione
        self.assertIsNotNone(risultato)
        self.assertEqual("9.9.9", risultato)
        # Verifica che il cache sia stato scritto
        data = registry.load()
        self.assertIn("last_update_check", data)
        self.assertIn("latest_known_version", data)

    def test_cache_fresca_non_chiama_rete(self):
        """Con cache fresca (< 24h), check_for_update() non chiama la rete."""
        # Prepara il cache
        data = registry.load()
        data["last_update_check"] = self_update._adesso()
        data["latest_known_version"] = "9.9.9"
        registry.save(data)

        # Non registrare nessuna route HTTP: se viene chiamata, il test fallisce
        risultato = self_update.check_for_update()
        self.assertEqual("9.9.9", risultato)

    def test_cache_fresca_versione_corrente_ritorna_none(self):
        """Con cache fresca ma versione corrente >= nuova, ritorna None."""
        # Prepara il cache con una versione uguale o più vecchia di quella corrente
        # (la versione corrente in test è 0.0.0-dev che viene parsata come 0.0.0)
        data = registry.load()
        data["last_update_check"] = self_update._adesso()
        data["latest_known_version"] = "0.0.0"
        registry.save(data)

        risultato = self_update.check_for_update()
        self.assertIsNone(risultato)

    def test_cache_scaduta_richiama_rete(self):
        """Con cache scaduta (> 24h), check_for_update() richiama la rete."""
        # Prepara il cache con un timestamp vecchio (> 24h fa)
        data = registry.load()
        adesso = datetime.now(timezone.utc)
        vecchio = (adesso - timedelta(hours=25)).isoformat()
        data["last_update_check"] = vecchio
        data["latest_known_version"] = "0.0.1"
        registry.save(data)

        # Pubblica una release nuova nel fixture
        self._pubblica_release("v9.9.9")
        risultato = self_update.check_for_update()
        self.assertEqual("9.9.9", risultato)

    def test_errore_rete_ritorna_none(self):
        """Errore di rete (nessuna route): check_for_update() ritorna None."""
        # Non registrare nessuna route: /repos/strawberry-code/atlas/releases/latest
        # non esiste nel fixture, quindi avremo un 404
        risultato = self_update.check_for_update()
        self.assertIsNone(risultato)

    def test_errore_rete_registra_timestamp(self):
        """Errore di rete: registra comunque last_update_check per evitare retry infiniti."""
        # Non registrare nessuna route: avremo un errore di rete
        risultato = self_update.check_for_update()
        self.assertIsNone(risultato)
        # Verifica che il timestamp sia stato scritto comunque
        data = registry.load()
        self.assertIn("last_update_check", data)
        # Non deve aver scritto latest_known_version in caso di errore
        # (restava quello che c'era prima, se mai c'era)
        self.assertNotIn("latest_known_version", data)

    def test_risposta_json_malformata_ritorna_none(self):
        """JSON malformato: check_for_update() ritorna None silenziosamente."""
        self.fixture.routes["/repos/strawberry-code/atlas/releases/latest"] = (
            200, b"{ malformed json", "application/json")
        risultato = self_update.check_for_update()
        self.assertIsNone(risultato)


if __name__ == "__main__":
    unittest.main()
