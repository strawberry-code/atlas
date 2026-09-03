"""Identita' dell'installazione verso l'Atlas Relay (A01, modello di
docs/atlas-relay-design.md SS4-bis). Sostituisce il bearer di progetto: non
esiste piu' un segreto da configurare per repository, esiste un segreto
dell'installazione, generato in locale al primo utilizzo e mai esposto a un
umano (nessun comando lo stampa, nessun log lo scrive).

Nascita: la prima volta che un qualunque componente di Atlas prova a parlare
col relay su questa macchina, carica_o_crea() trova il file d'identita'
assente e ne genera uno nuovo con secrets.token_bytes (stdlib): 16 byte per
l'id (pubblico, e' come l'installazione si fa riconoscere) e 32 byte per il
secret (privato, non lascia mai la macchina in chiaro). Le chiamate
successive rileggono lo stesso file: un'installazione ha un'unica identita'
per tutti i progetti presenti e futuri di quella macchina (grilling 9).

Dove vive (decisione 8 di SS7): fuori da ogni repository, in
'~/.config/atlas/relay-identity.json' di default, cosi' nessun progetto -
nemmeno un progetto pubblico - puo' rivelarne l'esistenza. Il path e'
sovrascrivibile con la variabile ATLAS_INSTALL_HOME (test, profili multipli),
mai con una variabile che punti dentro il repo corrente.

Come si presenta a ogni richiesta: cinque header HTTP, mai un bearer statico.
'X-Atlas-Install' porta l'id pubblico, 'X-Atlas-Protocol' la versione di
protocollo che questa installazione parla (servira' a E02 per avvisare prima
di smettere di servirla), 'X-Atlas-Timestamp' e 'X-Atlas-Nonce' rendono ogni
richiesta irripetibile, 'X-Atlas-Signature' e' l'HMAC-SHA256 (chiave: il
secret) del messaggio canonico

    installation_id '\\n' metodo '\\n' percorso '\\n' timestamp '\\n' nonce '\\n' sha256(corpo)

Il secret non attraversa mai la rete: solo la firma che dimostra di
conoscerlo. Il relay (A02) verifica con verifica_richiesta(), stesso
messaggio canonico, guardando il secret che tiene per quell'installation_id
e scartando timestamp fuori tolleranza o nonce gia' visto (stesso schema
difensivo del jti in capability.py, qui sull'intera richiesta).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ENV_INSTALL_HOME = "ATLAS_INSTALL_HOME"

PROTOCOLLO = 1

INTESTAZIONE_INSTALL = "X-Atlas-Install"
INTESTAZIONE_PROTOCOLLO = "X-Atlas-Protocol"
INTESTAZIONE_TIMESTAMP = "X-Atlas-Timestamp"
INTESTAZIONE_NONCE = "X-Atlas-Nonce"
INTESTAZIONE_FIRMA = "X-Atlas-Signature"

TOLLERANZA_SECONDI = 300   # 5 minuti di deriva d'orologio ammessa, come i capability token


class IdentitaRelayRifiutata(ValueError):
    """La richiesta non porta una firma valida: timestamp fuori tolleranza,
    nonce gia' consumato, o HMAC che non torna."""


@dataclass(frozen=True)
class Installazione:
    installation_id: str   # pubblico: e' come il relay riconosce questa macchina
    secret: str             # privato: non lascia mai la macchina, solo firma


def percorso_predefinito(env: Mapping[str, str] | None = None) -> Path:
    """'~/.config/atlas/relay-identity.json', mai dentro il repository di un
    progetto: e' un'identita' di macchina, non di progetto (grilling 9)."""
    ambiente = env if env is not None else os.environ
    if override := ambiente.get(ENV_INSTALL_HOME):
        return Path(override).expanduser() / "relay-identity.json"
    return Path.home() / ".config" / "atlas" / "relay-identity.json"


def _genera() -> Installazione:
    return Installazione(
        installation_id=secrets.token_urlsafe(16),
        secret=secrets.token_urlsafe(32),
    )


def _scrivi(path: Path, installazione: Installazione) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({
        "installationId": installazione.installation_id,
        "secret": installazione.secret,
    }), encoding="utf-8")
    if sys.platform != "win32":
        os.chmod(tmp, 0o600)   # il secret non deve essere leggibile da altri utenti della macchina
    os.replace(tmp, path)


def carica_o_crea(path: Path | None = None, env: Mapping[str, str] | None = None) -> Installazione:
    """L'identita' di questa installazione: la legge se esiste gia', altrimenti
    la genera e la persiste. Idempotente fra processi diversi sulla stessa
    macchina solo nella misura in cui non corrono in parallelo al primissimo
    avvio: non c'e' lock, coerente con un file scritto una sola volta nella
    vita di un'installazione e poi solo riletto."""
    percorso = path or percorso_predefinito(env)
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
        return Installazione(installation_id=dati["installationId"], secret=dati["secret"])
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass
    installazione = _genera()
    _scrivi(percorso, installazione)
    return installazione


def _messaggio(installation_id: str, metodo: str, percorso: str, timestamp: str, nonce: str,
              corpo: bytes) -> bytes:
    hash_corpo = hashlib.sha256(corpo).hexdigest()
    return "\n".join((installation_id, metodo.upper(), percorso, timestamp, nonce, hash_corpo)).encode("utf-8")


def _firma(secret: str, messaggio: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), messaggio, hashlib.sha256).hexdigest()


def intestazioni_richiesta(installazione: Installazione, metodo: str, percorso: str,
                           corpo: bytes = b"", *, timestamp: str | None = None,
                           nonce: str | None = None) -> dict[str, str]:
    """Gli header da attaccare a ogni richiesta verso il relay: nessun bearer,
    solo la prova di conoscere il secret e la versione di protocollo che
    questa installazione parla."""
    ts = timestamp or str(int(time.time()))
    nc = nonce or secrets.token_urlsafe(12)
    messaggio = _messaggio(installazione.installation_id, metodo, percorso, ts, nc, corpo)
    return {
        INTESTAZIONE_INSTALL: installazione.installation_id,
        INTESTAZIONE_PROTOCOLLO: str(PROTOCOLLO),
        INTESTAZIONE_TIMESTAMP: ts,
        INTESTAZIONE_NONCE: nc,
        INTESTAZIONE_FIRMA: _firma(installazione.secret, messaggio),
    }


class NonceVisti:
    """Nonce gia' consumati, tenuti solo finche' restano dentro la tolleranza
    di orologio: oltre quella finestra un timestamp scaduto li rifiuta gia'
    per conto suo, quindi conservarli piu' a lungo non aggiungerebbe difesa.
    Stessa forma di ConsumatiJti in capability.py, applicata alla richiesta
    intera invece che al singolo tap."""

    def __init__(self) -> None:
        self._visti: dict[str, float] = {}

    def consuma(self, nonce: str, now_epoch: float, tolleranza: float) -> bool:
        soglia = now_epoch - tolleranza
        scaduti = [chiave for chiave, epoca in self._visti.items() if epoca < soglia]
        for chiave in scaduti:
            del self._visti[chiave]
        if nonce in self._visti:
            return False
        self._visti[nonce] = now_epoch
        return True


def verifica_richiesta(secret: str, installation_id: str, intestazioni: Mapping[str, str],
                       metodo: str, percorso: str, corpo: bytes = b"", *,
                       nonces: NonceVisti, now: float | None = None,
                       tolleranza: float = TOLLERANZA_SECONDI) -> None:
    """Solleva IdentitaRelayRifiutata se la richiesta non e' autentica, fresca
    e non ripetuta. Chi chiama (il relay, A02) ha gia' risolto 'secret' da
    'installation_id' prima di arrivare qui: questa funzione non conosce
    nessuno store, e' solo il verificatore del contratto."""
    ts = intestazioni.get(INTESTAZIONE_TIMESTAMP)
    nonce = intestazioni.get(INTESTAZIONE_NONCE)
    firma = intestazioni.get(INTESTAZIONE_FIRMA)
    if not ts or not nonce or not firma:
        raise IdentitaRelayRifiutata("header mancanti")
    try:
        istante = float(ts)
    except ValueError as errore:
        raise IdentitaRelayRifiutata("timestamp non valido") from errore
    istante_attuale = now if now is not None else time.time()
    if abs(istante_attuale - istante) > tolleranza:
        raise IdentitaRelayRifiutata("timestamp fuori tolleranza")
    messaggio = _messaggio(installation_id, metodo, percorso, ts, nonce, corpo)
    if not hmac.compare_digest(firma, _firma(secret, messaggio)):
        raise IdentitaRelayRifiutata("firma non valida")
    if not nonces.consuma(nonce, istante_attuale, tolleranza):
        raise IdentitaRelayRifiutata("nonce gia' consumato")
