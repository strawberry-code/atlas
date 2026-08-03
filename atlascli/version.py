"""Versione del CLI globale: quella impacchettata in _payload.py da build.py.

_payload.py e' generato e gitignored (vedi build.py: build_cli()); in sorgente,
prima di una build, semplicemente non esiste, e current_version() ricade sul
fallback. Nessun placeholder da sostituire in questo file.
"""
from __future__ import annotations

FALLBACK_VERSION = "0.0.0-dev"


def current_version() -> str:
    try:
        from . import _payload
    except ImportError:
        return FALLBACK_VERSION
    return _payload.VERSION
