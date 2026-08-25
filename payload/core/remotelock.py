"""Il lucchetto remoto come lo vede il motore: esiti tipizzati, protocollo, holder.

Confine di L04: la semantica del lucchetto remoto sta qui, nel motore, offline; il
trasporto (git-refs verso un remote condiviso) sta in atlascli, dove la rete e'
consentita, e al boot qualcuno lo inietta con set_trasporto(). Finche' non lo fa,
attivo() e' falso e claims.py non tocca la rete: il lucchetto resta quello locale.

La regola di convivenza con claims.py e' una sola: la verita' remota sta nella ref,
quella locale nel claim di graph.json, e il claim locale si scrive solo se la ref e'
libera o scaduta. Qui stanno gli esiti con cui claims.py decide; il trasporto esegue
transizioni e riporta cosa vede, non prende decisioni.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .config import Graph

# Gli esiti tipizzati. Sono dati, mai eccezioni: il chiamante li legge e decide,
# e il messaggio arriva dal catalogo, non da un traceback.
DISATTIVO = "Disattivo"    # nessun trasporto: il lucchetto remoto non esiste
ACQUISITO = "Acquisito"    # la transizione richiesta e' andata a buon fine
TENUTO = "Tenuto"          # la ref esiste e qualcuno la tiene: host + scadenza
NON_SCADUTO = "NonScaduto" # furto rifiutato: la lock e' fresca
NON_TUO = "NonTuo"         # rilascio/rinnovo rifiutato: di un altro e fresca
GARA = "Gara"              # la ref si e' mossa da quando l'ho letta: rileggi e riprova
RETE = "Rete"              # errore di trasporto: rete assente, remote ignoto, git rotto


@dataclass(frozen=True)
class Esito:
    """Un esito tipizzato. host e scadenza (epoch) accompagnano Tenuto, e a volte
    NonScaduto o NonTuo, cosi' claims.py nomina il possessore senza interrogare
    git; nome accompagna gli esiti di elenca, per dire quale ref si sta guardando."""
    kind: str
    host: str | None = None
    scadenza: int | None = None
    nome: str | None = None


@runtime_checkable
class RemoteLock(Protocol):
    """Il trasporto come lo consuma il motore: transizioni su una ref, esiti come dati."""
    def acquire(self, nome: str, host: str, scadenza: int) -> Esito: ...
    def ruba(self, nome: str, host: str, scadenza: int) -> Esito: ...
    def rilascia(self, nome: str, host: str) -> Esito: ...
    def rinnova(self, nome: str, host: str, scadenza: int) -> Esito: ...
    def stato(self, nome: str) -> Esito: ...
    def elenca(self) -> list[Esito] | Esito: ...


def nome_lock(ref: Graph, node_id: str) -> str:
    """Il nome della ref remota di un nodo: per grafo e per nodo, cosi' due grafi
    con gli stessi id non condividono la serratura."""
    return f"{ref.slug}/{node_id}"


def scadenza_epoch(ttl: int) -> int:
    """L'expiry di una ref remota: epoch (secondi), come lo parla git."""
    return int(time.time()) + ttl


def fresco(scadenza: int | None) -> bool:
    """Vero se un'expiry e' ancora nel futuro. Un'expiry assente vale come fresco:
    nel dubbio si lascia lavorare chi tiene, mai lo si dichiara morto (L02)."""
    return scadenza is None or scadenza > int(time.time())


_trasporto: RemoteLock | None = None


def set_trasporto(trasporto: RemoteLock | None) -> None:
    """Inietta o toglie il trasporto. Lo chiama il layer di gestione al boot se la
    config dichiara lock.remote; i test lo usano per iniettare uno stub."""
    global _trasporto
    _trasporto = trasporto


def attivo() -> bool:
    """Vero se c'e' un trasporto: solo allora claims.py consulta la ref remota."""
    return _trasporto is not None


def acquire(nome: str, host: str, scadenza: int) -> Esito:
    return _trasporto.acquire(nome, host, scadenza) if _trasporto else Esito(DISATTIVO)


def ruba(nome: str, host: str, scadenza: int) -> Esito:
    return _trasporto.ruba(nome, host, scadenza) if _trasporto else Esito(DISATTIVO)


def rilascia(nome: str, host: str) -> Esito:
    return _trasporto.rilascia(nome, host) if _trasporto else Esito(DISATTIVO)


def rinnova(nome: str, host: str, scadenza: int) -> Esito:
    return _trasporto.rinnova(nome, host, scadenza) if _trasporto else Esito(DISATTIVO)


def stato(nome: str) -> Esito:
    return _trasporto.stato(nome) if _trasporto else Esito(DISATTIVO)


def elenca() -> list[Esito] | Esito:
    return _trasporto.elenca() if _trasporto else Esito(DISATTIVO)
