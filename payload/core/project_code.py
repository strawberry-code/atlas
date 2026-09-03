"""Codice opaco del progetto verso l'Atlas Relay (E01, docs/atlas-relay-design.md
SS11-bis): risolve la contraddizione trovata nella revisione del grafo fra "il
relay non conosce i progetti" (SS4-bis) e "avvisa quando un collega chiude un
pezzo di un progetto condiviso" (decisione 9 di SS11).

Vincolo stretto deciso il 2026-09-02: questo codice instrada SOLO l'avviso
generico di aggiornamento (payload/core/peer_notify.py). Non e' una capability
e non autorizza a ricevere ne' a risolvere una decisione: quelle restano
legate all'identita' d'installazione (relay_identity.py, A01). Non porta il
nome del progetto ne' il suo contenuto, e' un token opaco, muto per chi lo
legge.

Vive in '.atlas/config.json' (chiave 'projectCode'), che a differenza di
relay_identity.py NON e' l'identita' di una macchina: e' dato di progetto,
versionato come il resto di config.json, quindi uguale su ogni copia clonata
dello stesso repository (grilling: due macchine che condividono un
'projectCode' condiviso via git, non due macchine che negoziano un segreto).
Un'installazione nuova su un progetto esistente lo eredita da git al primo
pull, non lo rigenera: solo la primissima copia lo crea, all'installazione
(atlascli/install_cmd.py) o, per un progetto che aggiorna da una versione
senza questa funzione, al primo tentativo di avvisare (carica_o_crea, patch
chirurgica come Installer.imposta_lingua).
"""
from __future__ import annotations

import json
import secrets

from .config import Workspace, leggi_json

CHIAVE = "projectCode"


def genera() -> str:
    return secrets.token_urlsafe(16)


def carica_o_crea(ws: Workspace) -> str:
    """Il codice di questo progetto: lo legge da config.json se c'e' gia',
    altrimenti lo genera e lo scrive li' con una patch sulla sola chiave,
    senza toccare il resto del file."""
    path = ws.root / "config.json"
    dati = leggi_json(path) if path.is_file() else {}
    if codice := dati.get(CHIAVE):
        return codice
    codice = genera()
    dati[CHIAVE] = codice
    path.write_text(json.dumps(dati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return codice
