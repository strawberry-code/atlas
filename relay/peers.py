"""Chi ascolta l'avviso 'qualcosa e' cambiato' per un progetto condiviso (E01,
docs/atlas-relay-design.md SS11-bis).

Il relay non conosce ne' il nome ne' il contenuto di un progetto (SS4-bis):
qui l'unica chiave e' il codice opaco che il progetto porta con se'
(payload/core/project_code.py), e l'unico valore sono le installazioni che
lo hanno gia' usato per avvisare. Nessuna autorizzazione nasce da qui: sapere
chi avvisare non e' sapere chi puo' decidere o cosa e' cambiato, quel potere
resta dove sta gia' (la firma per-richiesta di relay_identity, o il bearer
del tunnel) - questo store instrada un messaggio muto, punto.

Persistito su disco come pairing.py, stesso motivo: un riavvio del servizio
non deve dimenticare chi e' membro di quale progetto.
"""
from __future__ import annotations

import json
import os
import threading
import urllib.error
from collections.abc import Mapping
from pathlib import Path
from typing import Callable

TESTO_AVVISO = ("Qualcosa e' cambiato in un progetto condiviso: conviene "
                "allinearsi (git pull).")

ENV_STATE_DIR = "ATLAS_RELAY_STATE_DIR"

InviaMessaggio = Callable[[int, str], None]
AvvisoPeer = Callable[[str, str], None]


def _percorso_stato_default() -> Path:
    return Path(__file__).resolve().parent / "state" / "peers.json"


class RegistroPeer:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def _leggi(self) -> dict:
        try:
            dati = json.loads(self._path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            dati = {}
        dati.setdefault("membri", {})
        return dati

    def _scrivi(self, dati: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(dati), encoding="utf-8")
        os.replace(tmp, self._path)

    def osserva_e_ottieni_pari(self, project_code: str, installation_id: str) -> list[str]:
        """Registra questa installazione come membro del codice, e torna le
        altre installazioni gia' note per lo stesso codice (mai questa
        stessa): sono quelle da avvisare, non quelle a cui chiedere il via
        libera."""
        with self._lock:
            dati = self._leggi()
            membri = dati["membri"].setdefault(project_code, [])
            pari = [m for m in membri if m != installation_id]
            if installation_id not in membri:
                membri.append(installation_id)
                self._scrivi(dati)
            return pari


def costruisci_avviso(registro: RegistroPeer, chat_id_di: Callable[[str], "int | None"],
                      invia_messaggio: InviaMessaggio) -> AvvisoPeer:
    """La chiusura che l'endpoint /peers/notify chiama: registra chi ha
    avvisato e spinge il testo fisso (mai il nome del progetto, mai quello
    del nodo) a ogni pari gia' noto che ha una chat associata. Un pari senza
    chat (approvazione mai completata) si scarta in silenzio, come ogni push
    best-effort di questo relay."""
    def _avvisa(project_code: str, installation_id: str) -> None:
        for pari in registro.osserva_e_ottieni_pari(project_code, installation_id):
            chat_id = chat_id_di(pari)
            if chat_id is None:
                continue
            try:
                invia_messaggio(chat_id, TESTO_AVVISO)
            except (OSError, urllib.error.URLError):
                # Un pari non e' un altro: Telegram giu' per uno non deve
                # inghiottire l'avviso agli altri, ne' far fallire la
                # richiesta di chi ha chiuso il nodo (best-effort, come ogni
                # altro push di questo relay).
                continue
    return _avvisa


def costruisci_da_ambiente(env: Mapping[str, str], state_path: Path | None = None) -> RegistroPeer:
    if state_path is not None:
        percorso = state_path
    elif env.get(ENV_STATE_DIR):
        percorso = Path(env[ENV_STATE_DIR]) / "peers.json"
    else:
        percorso = _percorso_stato_default()
    return RegistroPeer(percorso)
