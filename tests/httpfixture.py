"""Server HTTP fittizio locale, condiviso da test_self_update.py e test_install_sh.py.

Serve risposte preregistrate su una porta effimera: niente rete vera, niente mock
di libreria terza, solo http.server della stdlib.
"""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Fixture:
    def __init__(self, routes: dict[str, tuple[int, bytes, str]]):
        self.routes = routes
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def _handler(fixture):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                voce = fixture.routes.get(self.path)
                if voce is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                stato, corpo, tipo = voce
                self.send_response(stato)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

            def log_message(self, *args):
                pass  # niente rumore nell'output dei test

        return Handler

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()  # shutdown() ferma il loop, non chiude il socket in ascolto
