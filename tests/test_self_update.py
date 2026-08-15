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
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from atlascli import registry, self_update  # noqa: E402
from atlascli.version import current_version  # noqa: E402
from tests.httpfixture import Fixture  # noqa: E402


class Infrastruttura:
    """setUp, tearDown e fixture condivisi. Non e' un TestCase: ereditare da uno
    farebbe rieseguire i suoi test in ogni classe figlia, allungando la suite
    senza provare niente di nuovo."""

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
        # Il registro sotto test dev'essere di questa cartella, non quello vero
        # della macchina. Finche' l'update lo leggeva soltanto la differenza non
        # si vedeva; da quando riallinea i progetti, la suite andrebbe a
        # installare dentro i progetti veri di chi la esegue.
        self._config = os.environ.get("ATLAS_CONFIG")
        os.environ["ATLAS_CONFIG"] = str(self.tmp / "atlas.json")

    def tearDown(self):
        self.fixture.stop()
        sys.argv[0] = self._argv0
        os.environ.pop("ATLAS_UPDATE_BASE_URL", None)
        if self._config is None:
            os.environ.pop("ATLAS_CONFIG", None)
        else:
            os.environ["ATLAS_CONFIG"] = self._config
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


class SelfUpdate(Infrastruttura, unittest.TestCase):
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

    def _pubblica_senza_impronta(self, tag: str, blob: bytes) -> None:
        release = {"tag_name": tag, "assets": [
            {"name": "atlas", "browser_download_url": f"{self.fixture.base_url}/asset/atlas"}]}
        self.fixture.routes["/repos/strawberry-code/atlas/releases/latest"] = (
            200, json.dumps(release).encode("utf-8"), "application/json")
        self.fixture.routes["/asset/atlas"] = (200, blob, "application/octet-stream")

    def test_release_senza_impronta_non_installa_niente(self):
        """Una release pubblicata dimenticando atlas.sha256 non deve diventare un
        aggiornamento cieco: prima passava, saltando la verifica in silenzio."""
        self._pubblica_senza_impronta("v9.9.9", b"binario non verificabile\n")
        self.assertEqual(1, self_update.cmd_update(None))
        self.assertEqual(b"vecchia versione\n", self.target.read_bytes())

    def test_impronta_illeggibile_non_installa_niente(self):
        """Un proxy che risponde con una pagina di errore al posto dello sha256
        produceva IndexError; ora e' un rifiuto motivato."""
        self._pubblica("v9.9.9", b"nuova versione\n")
        self.fixture.routes["/asset/atlas.sha256"] = (
            200, b"<html>errore del proxy</html>", "text/html")
        self.assertEqual(1, self_update.cmd_update(None))
        self.assertEqual(b"vecchia versione\n", self.target.read_bytes())

    def test_asset_su_http_esterno_rifiutato(self):
        """L'indirizzo arriva dal JSON della release: in chiaro verso un host che non
        e' la macchina stessa, chi sta sulla tratta sceglie cosa installiamo."""
        self._pubblica("v9.9.9", b"nuova versione\n")
        release = json.loads(
            self.fixture.routes["/repos/strawberry-code/atlas/releases/latest"][1].decode("utf-8"))
        release["assets"][0]["browser_download_url"] = "http://esempio.invalido/atlas"
        self.fixture.routes["/repos/strawberry-code/atlas/releases/latest"] = (
            200, json.dumps(release).encode("utf-8"), "application/json")
        self.assertEqual(1, self_update.cmd_update(None))
        self.assertEqual(b"vecchia versione\n", self.target.read_bytes())


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

    def test_non_riporta_indietro_il_registro_scritto_nel_frattempo(self):
        """Fra la lettura del registro e il suo salvataggio c'e' una chiamata di rete.
        Un altro comando che registra un progetto in quella finestra non deve sparire:
        prima veniva sovrascritto dalla copia letta prima della chiamata."""
        self._pubblica_release("v9.9.9")
        vero_get_json = self_update._get_json

        def get_json_con_interferenza(url):
            risposta = vero_get_json(url)
            dati = registry.load()                 # l'altro comando, mentre la rete lavora
            dati["projects"]["arrivato-dopo"] = {"path": "/tmp/arrivato-dopo"}
            registry.save(dati)
            return risposta

        with mock.patch.object(self_update, "_get_json", get_json_con_interferenza):
            self_update.check_for_update()
        dopo = registry.load()
        self.assertIn("arrivato-dopo", dopo["projects"], "il progetto registrato nel frattempo resta")
        self.assertIn("last_update_check", dopo, "e la cache viene comunque aggiornata")

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


class Riallineamento(Infrastruttura, unittest.TestCase):
    """'atlas update' rimette in pari i progetti registrati.

    Il binario pubblicato dal fixture e' uno script vero che scrive quali
    argomenti ha ricevuto: cosi' il test dimostra anche che a riallineare e'
    l'eseguibile nuovo, e non questo processo, che porta ancora il payload
    della versione appena sostituita.
    """

    SONDA = ("#!/usr/bin/env python3\n"
             "import pathlib, sys\n"
             "pathlib.Path(sys.argv[2], 'RIALLINEATO').write_text(' '.join(sys.argv[1:]), encoding='utf-8')\n"
             ).encode("utf-8")

    def _versione_registrata(self, slug: str, versione: str | None) -> None:
        """Riscrive (o toglie) la versione con cui il progetto risulta installato.

        Senza il campo si simula un progetto registrato da una versione che ancora
        non lo scriveva: e' lo stato in cui si trova chi aggiorna da una 0.11.0 o
        precedente, cioe' proprio quello che questo comportamento deve coprire.
        """
        dati = registry.load()
        if versione is None:
            dati["projects"][slug].pop("version", None)
        else:
            dati["projects"][slug]["version"] = versione
        registry.save(dati)

    def _progetto(self, nome: str, *, hook: bool = False, claude_md: bool = False) -> Path:
        target = self.tmp / nome
        (target / ".atlas").mkdir(parents=True)
        (target / ".atlas" / "config.json").write_text('{"project": "x"}', encoding="utf-8")
        if hook:
            (target / ".claude").mkdir(exist_ok=True)
            (target / ".claude" / "settings.json").write_text(
                json.dumps({"hooks": {"SessionEnd": [{"hooks": [{"command": "atlas render --all"}]}]}}),
                encoding="utf-8")
        if claude_md:
            (target / "CLAUDE.md").write_text("# x\n<!-- atlas:begin -->\nc\n<!-- atlas:end -->\n",
                                              encoding="utf-8")
        registry.register(target, slug=nome, yes=True)
        return target

    def _aggiorna(self, no_projects: bool = False) -> int:
        self._pubblica("v9.9.9", self.SONDA)
        return self_update.cmd_update(SimpleNamespace(no_projects=no_projects))

    def test_ogni_progetto_registrato_viene_riallineato(self):
        uno, due = self._progetto("uno"), self._progetto("due")
        self.assertEqual(0, self._aggiorna())
        for target in (uno, due):
            with self.subTest(target=target.name):
                self.assertTrue((target / "RIALLINEATO").is_file())
                # il path arriva dal registro, che lo tiene risolto (su macOS /var e' un symlink)
                self.assertIn(f"install {target.resolve()} --yes",
                              (target / "RIALLINEATO").read_text(encoding="utf-8"))

    def test_progetto_sparito_dal_disco_viene_saltato_senza_fermare_gli_altri(self):
        registry.register(self.tmp / "fantasma", slug="fantasma", yes=True)
        vivo = self._progetto("vivo")
        self.assertEqual(0, self._aggiorna())
        self.assertTrue((vivo / "RIALLINEATO").is_file())

    def test_cartella_senza_config_viene_saltata(self):
        """Restare con .atlas/ dopo un uninstall non fa di una cartella un progetto."""
        orfano = self.tmp / "orfano"
        (orfano / ".atlas").mkdir(parents=True)
        registry.register(orfano, slug="orfano", yes=True)
        self.assertEqual(0, self._aggiorna())
        self.assertFalse((orfano / "RIALLINEATO").exists())

    def test_riallineare_non_aggiunge_quel_che_il_progetto_non_aveva(self):
        """Chi era installato senza hook o senza blocco in CLAUDE.md non se li
        ritrova comparire adesso: l'update rinfresca, non reinstalla scelte."""
        nudo = self._progetto("nudo")
        completo = self._progetto("completo", hook=True, claude_md=True)
        self.assertEqual(0, self._aggiorna())
        argomenti = (nudo / "RIALLINEATO").read_text(encoding="utf-8")
        self.assertIn("--no-hooks", argomenti)
        self.assertIn("--no-claude-md", argomenti)
        argomenti = (completo / "RIALLINEATO").read_text(encoding="utf-8")
        self.assertNotIn("--no-hooks", argomenti)
        self.assertNotIn("--no-claude-md", argomenti)

    def test_eseguibile_gia_in_pari_riallinea_comunque_chi_e_indietro(self):
        """Il caso di chi ha aggiornato da una versione che ancora non riallineava:
        l'eseguibile e' all'ultima, i progetti no, e senza questo passaggio ogni
        update successivo direbbe solo 'sei gia' aggiornato' lasciandoli indietro."""
        indietro = self._progetto("indietro")
        self._versione_registrata("indietro", None)
        # niente download in questo scenario: a riallineare e' l'eseguibile gia'
        # installato, quindi la sonda dev'essere quello, non l'asset pubblicato
        self.target.write_bytes(self.SONDA)
        self._pubblica("v0.0.0-dev", self.SONDA)     # stessa versione del processo di prova
        self.assertEqual(0, self_update.cmd_update(SimpleNamespace(no_projects=False)))
        self.assertTrue((indietro / "RIALLINEATO").is_file(), "il progetto indietro viene rimesso in pari")

    def test_eseguibile_e_progetti_in_pari_non_tocca_niente(self):
        """Chi e' gia' allineato non va reinstallato a ogni update: sarebbe lavoro
        inutile su ogni progetto della macchina, e un diff a ogni giro."""
        fermo = self._progetto("fermo")
        self._versione_registrata("fermo", current_version())
        self._pubblica("v0.0.0-dev", self.SONDA)
        self.assertEqual(0, self_update.cmd_update(SimpleNamespace(no_projects=False)))
        self.assertFalse((fermo / "RIALLINEATO").exists())

    def test_no_projects_aggiorna_solo_l_eseguibile(self):
        solo = self._progetto("solo")
        self.assertEqual(0, self._aggiorna(no_projects=True))
        self.assertEqual(self.SONDA, self.target.read_bytes())
        self.assertFalse((solo / "RIALLINEATO").exists())

    def test_settings_illeggibile_non_ferma_il_riallineamento(self):
        rotto = self._progetto("rotto")
        (rotto / ".claude").mkdir(exist_ok=True)
        (rotto / ".claude" / "settings.json").write_text("{ non json", encoding="utf-8")
        self.assertEqual(0, self._aggiorna())
        self.assertIn("--no-hooks", (rotto / "RIALLINEATO").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
