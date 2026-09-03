"""Avviso di fine servizio per protocollo vecchio (E02, S7-ter/6): il giorno
in cui questo relay smette di intendere una versione vecchia di
'X-Atlas-Protocol' (A01, relay_identity.PROTOCOLLO lato client), un'installazione
rimasta indietro se ne accorgerebbe tutta d'un colpo, e solo dalla dashboard
del suo computer: il posto dove chi lavora non sta guardando in quel momento.

SOGLIA_SOTTO_LA_QUALE_AVVISA, quando il gestore la alza a mano e ridistribuisce
il relay (stesso stile di SOGLIA_ORARIA in throttle.py: un solo punto
leggibile, nessuna leva a runtime), segna la versione che sta per smettere di
essere servita. Chi dichiara meno riceve un avviso su Telegram con
l'indicazione di come aggiornare, prima che il relay smetta davvero. None (il
default, nessuna deprecazione ancora annunciata) non avvisa mai nessuno.
"""
from __future__ import annotations

import threading
from collections.abc import Callable

SOGLIA_SOTTO_LA_QUALE_AVVISA: int | None = None

INTESTAZIONE_PROTOCOLLO = "X-Atlas-Protocol"   # stesso nome di relay_identity.INTESTAZIONE_PROTOCOLLO (A01)

MESSAGGIO = ("Il tuo Atlas parla una versione di protocollo che questo relay "
             "sta per smettere di servire. Aggiorna con: atlas update")

InviaMessaggio = Callable[[int, str], None]
AvvisaProtocollo = Callable[[str, "int | None"], None]


class AvvisoProtocollo:
    """Un avviso a installazione per la vita di questo processo: le
    riconnessioni del tunnel (backoff, D03) non devono mandarlo ogni pochi
    secondi. Si marca come avvisata solo dopo un invio riuscito
    (costruisci_avviso sotto): un'installazione non ancora appaiata puo'
    ancora riceverlo alla prossima connessione, invece di perderlo per
    sempre."""

    def __init__(self, soglia: int | None = SOGLIA_SOTTO_LA_QUALE_AVVISA) -> None:
        self._soglia = soglia
        self._avvisate: set[str] = set()
        self._lock = threading.Lock()

    def da_avvisare(self, installation_id: str, versione_dichiarata: int | None) -> bool:
        if self._soglia is None or versione_dichiarata is None or versione_dichiarata >= self._soglia:
            return False
        with self._lock:
            return installation_id not in self._avvisate

    def segna_avvisata(self, installation_id: str) -> None:
        with self._lock:
            self._avvisate.add(installation_id)


def costruisci_avviso(avviso: AvvisoProtocollo, gestore_pairing,
                       invia_messaggio: InviaMessaggio) -> AvvisaProtocollo:
    """Chiamalo a ogni apertura di tunnel (A05), stesso punto di
    'segna_vista' (C02): se l'installazione parla una versione sotto soglia,
    non e' gia' stata avvisata e ha una chat appaiata, le manda il messaggio
    con l'indicazione di come aggiornare."""
    def _avvisa(installation_id: str, versione_dichiarata: int | None) -> None:
        if not avviso.da_avvisare(installation_id, versione_dichiarata):
            return
        chat_id = gestore_pairing.chat_id_di(installation_id)
        if chat_id is None:
            return
        invia_messaggio(chat_id, MESSAGGIO)
        avviso.segna_avvisata(installation_id)
    return _avvisa
