"""F06: build.py copia payload/templates/ dentro il pacchetto (build_cli() in
build.py, letto poi da core/risorse.py), ma nessuno verificava che i fogli
citati da leggi_css_dashboard()/leggi_js_dashboard() sopravvivessero davvero
allo staging: un foglio dimenticato si scopriva solo aprendo la dashboard
dell'eseguibile compilato, dopo una release.

Il test costruisce un CLI vero, sempre in una directory temporanea (mai
dist/atlas del repo), e importa core.risorse dal pacchetto cosi' ottenuto con
sys.path.insert() sullo zipapp: e' la stessa via che segue
'atlascli.main:run' in produzione. Girare sui sorgenti non basterebbe: da
sorgente leggi_template() ripiega su Path verso payload/templates/, e un
foglio mancante nello staging resterebbe invisibile dietro quel ripiego.

L'elenco dei fogli non e' ricopiato qui: si chiamano davvero
leggi_css_dashboard()/leggi_js_dashboard(), quindi un foglio aggiunto domani a
quelle funzioni entra nella prova senza toccare questo file.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import build  # noqa: E402

IGNORA = shutil.ignore_patterns("__pycache__", ".DS_Store")

# sys.argv[1] e' il path del CLI, passato come argomento posizionale a 'python3 -c'.
CODICE_IMPORT = (
    "import sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "from core.risorse import leggi_css_dashboard, leggi_js_dashboard\n"
    "css = leggi_css_dashboard()\n"
    "js = leggi_js_dashboard()\n"
    "assert css and js, 'fogli vuoti'\n"
)


def _build_in(dist: Path, *, payload_dir: Path, atlascli_dir: Path, root: Path) -> Path:
    """Richiama il vero build.build_cli(), reindirizzando dove legge e dove
    scrive. build_cli() rilegge questi nomi dal modulo a ogni chiamata (non
    sono parametri ne' variabili chiuse a tempo di definizione), quindi
    sovrascriverli prima della chiamata e ripristinarli dopo basta: i file
    veri del repo (incluso dist/atlas) non vengono mai toccati."""
    originali = (build.ROOT, build.PAYLOAD_DIR, build.ATLASCLI_DIR,
                 build.PAYLOAD_MODULE, build.DIST, build.CLI_OUT, build.CLI_SHA)
    build.ROOT = root
    build.PAYLOAD_DIR = payload_dir
    build.ATLASCLI_DIR = atlascli_dir
    build.PAYLOAD_MODULE = atlascli_dir / "_payload.py"
    build.DIST = dist
    build.CLI_OUT = dist / "atlas"
    build.CLI_SHA = dist / "atlas.sha256"
    try:
        build.build_cli()
    finally:
        (build.ROOT, build.PAYLOAD_DIR, build.ATLASCLI_DIR, build.PAYLOAD_MODULE,
         build.DIST, build.CLI_OUT, build.CLI_SHA) = originali
    return dist / "atlas"


def _importa_dal_pacchetto(cli: Path) -> subprocess.CompletedProcess:
    """Sottoprocesso pulito, senza altro sys.path che quello dello zipapp: la
    stessa importazione che fa render.py per ottenere CSS e JS della dashboard."""
    return subprocess.run([sys.executable, "-c", CODICE_IMPORT, str(cli)],
                           capture_output=True, text=True, timeout=60)


class TemplateNelPacchetto(unittest.TestCase):
    """Ogni test costruisce nella propria directory temporanea: dist/atlas del
    repo non viene mai letto ne' scritto qui."""

    def test_pacchetto_reale_legge_ogni_foglio_dichiarato(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp)
            cli = _build_in(dist, payload_dir=ROOT / "payload",
                             atlascli_dir=ROOT / "atlascli", root=dist)
            esito = _importa_dal_pacchetto(cli)
        self.assertEqual(esito.returncode, 0, esito.stderr)

    def test_foglio_dimenticato_in_staging_fa_fallire_limport(self):
        # Copia isolata di payload/+atlascli/: il foglio si toglie dalla copia,
        # mai dai sorgenti veri, cosi' la prova non lascia il repo modificato
        # nemmeno per la durata del test.
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            sorgente_payload = tmp / "payload"
            sorgente_atlascli = tmp / "atlascli"
            shutil.copytree(ROOT / "payload", sorgente_payload, ignore=IGNORA)
            shutil.copytree(ROOT / "atlascli", sorgente_atlascli, ignore=IGNORA)
            (sorgente_payload / "templates" / "notifiche.css").unlink()

            dist = tmp / "dist"
            cli = _build_in(dist, payload_dir=sorgente_payload,
                             atlascli_dir=sorgente_atlascli, root=tmp)
            esito = _importa_dal_pacchetto(cli)
        self.assertNotEqual(esito.returncode, 0)
        self.assertIn("notifiche.css", esito.stderr)


if __name__ == "__main__":
    unittest.main()
