"""D02: view_capture.scatta() prova i candidati in ordine e torna il primo
PNG non vuoto; nessun browser trovato, un exit diverso da zero o un
timeout sono lo stesso esito 'nessuno risponde' (None), mai un'eccezione
che risalga a telegram_view.py."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))

from core import view_capture


class Completato:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


class ViewCapture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.html = self.tmp / "dashboard.html"
        self.html.write_text("<html></html>", encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def test_nessun_browser_installato_torna_none(self):
        def runner(comando, timeout=None, capture_output=None):
            raise FileNotFoundError("non installato")
        esito = view_capture.scatta(self.html, runner=runner, candidati=["chrome-inesistente"])
        self.assertIsNone(esito)

    def test_timeout_prova_il_candidato_successivo(self):
        chiamate = []

        def runner(comando, timeout=None, capture_output=None):
            chiamate.append(comando[0])
            if comando[0] == "lento":
                raise subprocess.TimeoutExpired(comando, timeout)
            out_path = self.html.with_suffix(".png")
            out_path.write_bytes(b"PNG")
            return Completato(0)

        esito = view_capture.scatta(self.html, runner=runner, candidati=["lento", "veloce"])
        self.assertEqual(esito, b"PNG")
        self.assertEqual(chiamate, ["lento", "veloce"])

    def test_exit_diverso_da_zero_torna_none(self):
        def runner(comando, timeout=None, capture_output=None):
            return Completato(1)
        esito = view_capture.scatta(self.html, runner=runner, candidati=["chrome"])
        self.assertIsNone(esito)

    def test_successo_torna_i_bytes_del_png_e_lo_ripulisce(self):
        def runner(comando, timeout=None, capture_output=None):
            out_path = self.html.with_suffix(".png")
            out_path.write_bytes(b"\x89PNG\r\n")
            return Completato(0)

        esito = view_capture.scatta(self.html, runner=runner, candidati=["chrome"])
        self.assertEqual(esito, b"\x89PNG\r\n")
        self.assertFalse(self.html.with_suffix(".png").exists())

    def test_png_vuoto_non_conta_come_riuscito(self):
        def runner(comando, timeout=None, capture_output=None):
            self.html.with_suffix(".png").write_bytes(b"")
            return Completato(0)
        esito = view_capture.scatta(self.html, runner=runner, candidati=["chrome"])
        self.assertIsNone(esito)

    def test_comando_firefox_usa_headless_singolo(self):
        catturato = {}

        def runner(comando, timeout=None, capture_output=None):
            catturato["comando"] = comando
            out_path = self.html.with_suffix(".png")
            out_path.write_bytes(b"PNG")
            return Completato(0)

        view_capture.scatta(self.html, runner=runner, candidati=["/usr/bin/firefox"])
        self.assertIn("--headless", catturato["comando"])
        self.assertIn("--screenshot", catturato["comando"])

    def test_comando_chrome_usa_headless_new(self):
        catturato = {}

        def runner(comando, timeout=None, capture_output=None):
            catturato["comando"] = comando
            out_path = self.html.with_suffix(".png")
            out_path.write_bytes(b"PNG")
            return Completato(0)

        view_capture.scatta(self.html, runner=runner, candidati=["/usr/bin/google-chrome"])
        self.assertIn("--headless=new", catturato["comando"])


if __name__ == "__main__":
    unittest.main()
