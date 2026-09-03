"""D02 (260902-atlas-relay): '/view' risponde con uno sguardo sul progetto
senza spedire i ticket (S11/4, S7-bis/9). La pagina alleggerita
(render_lite.build) e' la sola cosa che lascia questa macchina: grafo,
titoli e stati, mai il testo di un ticket o di un'Interazione aperta (S5).

Le due uscite condividono questa stessa costruzione (S7-bis, "vanno
progettate insieme, non come due funzioni diverse"): una foto, se un
browser di sistema risponde (view_capture.scatta), la pagina stessa come
allegato altrimenti - Atlas la sa gia' costruire, quindi il ripiego non ha
bisogno di nessun browser (S7-bis/9).

Stesso stile di telegram_status.py: rilegge il grafo al momento della
domanda, risponde sulla stessa linea gia' aperta di questa installazione,
gira nello stesso thread del tunnel (autopilot.py lo combina con
telegram_actions.gestore e telegram_status.gestore).
"""
from __future__ import annotations

import tempfile
from collections.abc import Mapping
from pathlib import Path

from . import relay_client, render_lite, view_capture
from .config import Graph
from .store import load

COMANDO_VIEW = "/view"


def gestore(graph: Graph, installation_id: str, config: relay_client.TunnelConfig,
           *, opener=None, screenshot=view_capture.scatta) -> relay_client.OnEvent:
    def _on_event(evento: Mapping[str, object]) -> None:
        if evento.get("kind") != "message" or evento.get("text") != COMANDO_VIEW:
            return
        data = load(graph.json_path)
        html = render_lite.build(graph, data)
        contenuto, mime, kind = _cattura(html, screenshot)
        filename = f"{graph.slug}.{'png' if kind == 'photo' else 'html'}"
        kwargs = {} if opener is None else {"opener": opener}
        relay_client.invia_file(config, installation_id, filename, contenuto, mime, kind, **kwargs)
    return _on_event


def _cattura(html: str, screenshot) -> tuple[bytes, str, str]:
    """La pagina alleggerita va scritta su disco anche per la sola foto: un
    browser headless non puo' scattare una stringa, gli serve un file://
    (S6-bis/12). La directory temporanea sparisce con lo screenshot gia'
    letto in memoria, prima che invia_file lo spedisca."""
    with tempfile.TemporaryDirectory(prefix="atlas-view-") as tmp:
        path = Path(tmp) / "dashboard.html"
        path.write_text(html, encoding="utf-8")
        foto = screenshot(path)
        if foto is not None:
            return foto, "image/png", "photo"
    return html.encode("utf-8"), "text/html", "document"
