"""Canale locale (avvisi di sistema): l'unico che C01 lascia sempre attivo,
perche' non chiede ne' credenziali ne' configurazione, solo l'utility di
notifica gia' sul sistema operativo. Zero dipendenze come il resto del
motore: un processo del sistema (osascript, notify-send, PowerShell), mai una
libreria di terze parti.

'riportare alla card giusta' (C02) qui e' un limite dichiarato: nessuno dei
tre comandi supporta un click che apra un url senza un aiuto esterno (un
demone D-Bus per notify-send, terminal-notifier per macOS). Il titolo porta
quindi l'id del nodo, cosi' chi legge l'avviso sa gia' quale card cercare
quando torna sulla dashboard; il collegamento cliccabile resta il canale
browser (dashboard.js), che vive nella stessa pagina della card.
"""
from __future__ import annotations

import base64
import subprocess
import sys
from collections.abc import Mapping

from .channels import ChannelRegistry
from .retry import PermanentError

IDENTITY = "local"
TITOLO = "Atlas"


def _applescript_str(testo: str) -> str:
    escapato = testo.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escapato}"'


def _comando_darwin(titolo: str, corpo: str) -> list[str]:
    script = f"display notification {_applescript_str(corpo)} with title {_applescript_str(titolo)}"
    return ["osascript", "-e", script]


def _comando_linux(titolo: str, corpo: str) -> list[str]:
    return ["notify-send", "--", titolo, corpo]


def _comando_windows(titolo: str, corpo: str) -> list[str]:
    """Lo script viaggia intero in '-EncodedCommand', e titolo/corpo dentro lo
    script viaggiano a loro volta in base64: cosi' il testo di un'Interaction
    (scritto da un agente, mai da questo modulo) non puo' mai uscire dalla
    stringa che lo contiene, qualunque carattere porti."""
    titolo_b64 = base64.b64encode(titolo.encode("utf-8")).decode("ascii")
    corpo_b64 = base64.b64encode(corpo.encode("utf-8")).decode("ascii")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "Add-Type -AssemblyName System.Drawing;"
        f"$t=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{titolo_b64}'));"
        f"$b=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{corpo_b64}'));"
        "$n=New-Object System.Windows.Forms.NotifyIcon;"
        "$n.Icon=[System.Drawing.SystemIcons]::Information;"
        "$n.Visible=$true;"
        "$n.ShowBalloonTip(6000,$t,$b,[System.Windows.Forms.ToolTipIcon]::Info);"
        "Start-Sleep -Seconds 6;"
        "$n.Dispose()"
    )
    codificato = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
            "-EncodedCommand", codificato]


def _comando(titolo: str, corpo: str) -> list[str]:
    if sys.platform == "darwin":
        return _comando_darwin(titolo, corpo)
    if sys.platform == "win32":
        return _comando_windows(titolo, corpo)
    return _comando_linux(titolo, corpo)


def _esegui(argv: list[str]) -> None:
    """osascript e notify-send rispondono subito, un'uscita diversa da zero e'
    un guasto vero. Su Windows il processo deve invece restare vivo per tutta
    la durata del fumetto (e' lui che lo disegna): non c'e' un esito sensato
    da attendere oltre il suo avvio, quindi si lancia e si lascia andare."""
    try:
        if sys.platform == "win32":
            subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        else:
            subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                           timeout=5, check=True)
    except FileNotFoundError as errore:
        # L'utility non e' installata: nessun tentativo futuro la fara' comparire,
        # quindi non e' un guasto da ritentare (vedi retry.PermanentError).
        raise PermanentError(f"notify helper not installed: {argv[0]}") from errore


class DesktopChannel:
    """Consegna una notifica di sistema. 'runner' e' il punto di iniezione dei
    test: di default esegue davvero, senza doverne mockare l'intero modulo."""

    identity = IDENTITY

    def __init__(self, runner=None) -> None:
        self._runner = runner or _esegui

    def deliver(self, interaction: Mapping[str, object]) -> None:
        titolo = f"{TITOLO} · {interaction['nodeId']}"
        corpo = str(interaction["summary"])
        self._runner(_comando(titolo, corpo))


def registry(channel: DesktopChannel | None = None) -> ChannelRegistry:
    return ChannelRegistry((channel or DesktopChannel(),))
