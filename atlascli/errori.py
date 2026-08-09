"""L'errore che il CLI globale mostra invece di far uscire un traceback, e l'unica
lettura che lo produce.

Sta in un modulo suo e non dentro dispatch, che importa mezzo pacchetto: cosi'
registry, install_cmd e progetto possono sollevarlo senza chiudere un ciclo di
import. Il motore ha il suo (core.config.ConfigError) e restano separati, come i
cataloghi: sono due distribuzioni, e un rename di la' non deve rompere un messaggio
di qua.
"""
from __future__ import annotations

import json
from pathlib import Path

from .strings import t


class ErroreAtlas(Exception):
    """Condizione prevista che ferma il comando: dispatch.main la stampa ed esce con 1."""


def leggi_json(path: Path, chiave: str = "errore.config_rotto") -> dict:
    """Un JSON del CLI, con l'errore che nomina il file da aprire.

    Questi file li scrive Atlas ma li modifica anche l'utente, e si leggono all'avvio
    di quasi ogni comando: un JSONDecodeError nudo lascia in mano un traceback senza
    path, e fa morire per primi i comandi che servirebbero a uscirne.
    """
    try:
        dati = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as errore:
        raise ErroreAtlas(t(chiave, path=path, dettaglio=errore)) from errore
    if not isinstance(dati, dict):
        # JSON valido ma della forma sbagliata: senza questo controllo l'errore
        # arriva molto piu' tardi, come AttributeError su una lista.
        raise ErroreAtlas(t(chiave, path=path, dettaglio=t("errore.non_oggetto")))
    return dati
