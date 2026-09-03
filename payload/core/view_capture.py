"""La foto della pagina alleggerita (D02, S6-bis/12-13): il primo browser
headless gia' installato che risponde, mai un download. Nessuna libreria:
un sottoprocesso il cui esito e' un PNG non vuoto conta come "ha risposto",
qualunque altra cosa (nessun browser trovato, timeout, exit diverso da
zero) e' il segnale per telegram_view.py di mandare la pagina come allegato
invece della foto (S7-bis/9).

I candidati divergono per sistema operativo (path noti su macOS e Windows,
nomi sul PATH altrove): stesso sys.platform delle altre divergenze POSIX/
Windows di questo motore. Il comando no: Chrome, Chromium ed Edge capiscono
tutti '--headless=new --screenshot=...'; Firefox usa da tempo lo stesso
'--screenshot' con un flag diverso per l'headless.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

LARGHEZZA, ALTEZZA = 1280, 900
TIMEOUT = 15.0


def _candidati() -> list[str]:
    """Un eseguibile per riga, nell'ordine deciso (S6-bis/13): Chrome prima,
    poi gli altri browser gia' installati sulla macchina."""
    if sys.platform == "darwin":
        return [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Firefox.app/Contents/MacOS/firefox",
        ]
    if sys.platform == "win32":
        return [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
        ]
    return ["google-chrome", "chromium", "chromium-browser", "microsoft-edge", "firefox"]


def _comando(eseguibile: str, html_path: Path, out_path: Path) -> list[str]:
    if "firefox" in eseguibile.lower():
        return [eseguibile, "--headless", "--screenshot", str(out_path),
                f"--window-size={LARGHEZZA},{ALTEZZA}", html_path.as_uri()]
    return [eseguibile, "--headless=new", "--disable-gpu", f"--screenshot={out_path}",
            f"--window-size={LARGHEZZA},{ALTEZZA}", html_path.as_uri()]


def scatta(html_path: Path, *, runner=subprocess.run, candidati: list[str] | None = None
          ) -> bytes | None:
    """None se nessun candidato ha prodotto un PNG, mai un'eccezione: un
    browser assente (FileNotFoundError/OSError) o troppo lento
    (TimeoutExpired) sono lo stesso esito di 'nessun browser risponde',
    non un guasto da far risalire."""
    out_path = html_path.with_suffix(".png")
    for eseguibile in (candidati if candidati is not None else _candidati()):
        try:
            esito = runner(_comando(eseguibile, html_path, out_path),
                           timeout=TIMEOUT, capture_output=True)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if esito.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 0:
            dati = out_path.read_bytes()
            out_path.unlink()
            return dati
    return None
