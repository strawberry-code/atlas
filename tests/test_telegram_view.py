"""D02: '/view' lato client. render_lite.build() alimenta view_capture.scatta
(iniettato nei test): una foto se risponde, altrimenti la pagina alleggerita
stessa come allegato (S7-bis/9). Le due uscite condividono lo stesso
gestore, mai due funzioni diverse (S7-bis)."""
from __future__ import annotations

import base64
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "payload"))

from core import mutate, relay_client, telegram_view
from core.config import Workspace

INSTALLAZIONE = "la-macchina"


class TelegramViewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.ws = Workspace(self.tmp / ".atlas")
        self.ref = mutate.create_graph(self.ws, "prova", "Il Progetto", "Verifica D02")
        with mutate.editing(self.ref) as graph:
            mutate.add_node(graph, "A01", "Primo nodo", "A", "Domanda segreta XYZZY")
        self.config = relay_client.TunnelConfig(base_url="https://relay.test", token="bearer")
        self.inviati = []

    def _opener(self):
        def opener(richiesta, timeout=None):
            class _Vuota:
                status = 200

                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    return False
            self.inviati.append(json.loads(richiesta.data))
            return _Vuota()
        return opener

    def _gestore(self, screenshot):
        return telegram_view.gestore(self.ref, INSTALLAZIONE, self.config,
                                     opener=self._opener(), screenshot=screenshot)

    def test_evento_non_message_ignorato(self):
        self._gestore(lambda path: None)({"kind": "callback", "chat_id": 1, "text": "/view"})
        self.assertEqual(self.inviati, [])

    def test_testo_diverso_da_view_ignorato(self):
        self._gestore(lambda path: None)({"kind": "message", "chat_id": 1, "text": "/stato"})
        self.assertEqual(self.inviati, [])

    def test_browser_risponde_manda_una_foto(self):
        self._gestore(lambda path: b"\x89PNG")({"kind": "message", "chat_id": 1, "text": "/view"})
        self.assertEqual(len(self.inviati), 1)
        corpo = self.inviati[0]
        self.assertEqual(corpo["installation"], INSTALLAZIONE)
        self.assertEqual(corpo["kind"], "photo")
        self.assertEqual(corpo["mime"], "image/png")
        self.assertTrue(corpo["filename"].endswith(".png"))
        self.assertEqual(base64.b64decode(corpo["content"]), b"\x89PNG")

    def test_nessun_browser_manda_la_pagina_alleggerita_come_documento(self):
        self._gestore(lambda path: None)({"kind": "message", "chat_id": 1, "text": "/view"})
        self.assertEqual(len(self.inviati), 1)
        corpo = self.inviati[0]
        self.assertEqual(corpo["kind"], "document")
        self.assertEqual(corpo["mime"], "text/html")
        self.assertTrue(corpo["filename"].endswith(".html"))
        html = base64.b64decode(corpo["content"]).decode("utf-8")
        self.assertIn("Primo nodo", html)
        self.assertNotIn("Domanda segreta XYZZY", html)

    def test_lo_screenshot_riceve_un_file_html_vero_su_disco(self):
        visti = []

        def screenshot(path):
            visti.append(path.read_text(encoding="utf-8"))
            return None

        self._gestore(screenshot)({"kind": "message", "chat_id": 1, "text": "/view"})
        self.assertEqual(len(visti), 1)
        self.assertIn("Primo nodo", visti[0])


if __name__ == "__main__":
    unittest.main()
