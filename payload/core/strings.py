"""Meccanismo di lookup dei messaggi del motore: i cataloghi veri e propri stanno
in strings_cli.py, strings_engine.py, strings_docs.py, strings_howto.py, divisi
per chi li usa.

Un processo 'atlas <comando>' e' sempre one-shot: set_language() si chiama una
volta sola in main(), letta da ws.config['language']. Nessuna lingua da passare
attraverso ogni funzione: t() legge la scelta corrente da qui.
"""
from __future__ import annotations

from .strings_cli import STRINGS as _CLI
from .strings_docs import STRINGS as _DOCS
from .strings_engine import STRINGS as _ENGINE
from .strings_howto import STRINGS as _HOWTO

STRINGS: dict[str, dict[str, str]] = {**_CLI, **_ENGINE, **_DOCS, **_HOWTO}

_lingua = "it"


def set_language(lingua: str) -> None:
    global _lingua
    _lingua = lingua if lingua in ("it", "en") else "it"


def current() -> str:
    return _lingua


def t(key: str, **kwargs) -> str:
    return STRINGS[key][_lingua].format(**kwargs)
