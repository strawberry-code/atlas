"""Freno automatico oltre soglia (C01, S11/5): il rischio di questa fase non
e' l'abuso umano, e' un Atlas che va in loop e chiede troppi invii Telegram,
facendo limitare il bot da Telegram e lasciando senza notifiche tutte le
altre installazioni. La soglia si sceglie senza dati d'uso (S11, rischi
accettati): va tenuta molto alta e in un solo punto leggibile ('SOGLIA_ORARIA'
qui sotto), per essere ritarata sui numeri veri alla fine del primo giro.

'FrenoOrario' e' una finestra scorrevole per installazione: oltre la soglia
di invii nell'ultima ora il relay smette di servire quella linea (non
registra altri tentativi, che quindi non allungano il blocco), finche' i
tentativi piu' vecchi non escono da soli dalla finestra o il gestore non
sblocca a mano.

Chi viene fermato deve avere una via per rispondere (S7-ter, punto scoperto:
senza appello il blocco automatico e' la sorpresa peggiore del sistema): il
messaggio di blocco porta un bottone 'Chiedi sblocco' che rimanda la
richiesta al gestore, oltre al bottone 'Sblocca' che il gestore riceve gia'
al primo blocco.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

SOGLIA_ORARIA = 300   # invii per installazione per ora: alta apposta, si ritara a fine primo giro (S11/5)
FINESTRA_SECONDI = 3600.0

PREFISSO_SBLOCCA = "gestore:sblocca:"
PREFISSO_APPELLO = "utente:appello:"

InviaMessaggio = Callable[[int, str], None]
InviaBottoni = Callable[[int, str, list], None]
NotificaBlocco = Callable[[str, int], None]
AdminDecision = Callable[[str, int, int], bool]


class FrenoOrario:
    """Conta i tentativi di deliver per installazione nell'ultima ora e dice
    se questa linea va ancora servita. Non persiste su disco: un riavvio del
    relay riparte con la finestra vuota, coerente con una soglia pensata come
    presidio contro un loop in corso, non come registro storico."""

    def __init__(self, soglia: int = SOGLIA_ORARIA, finestra: float = FINESTRA_SECONDI,
                 clock: Callable[[], float] = time.time) -> None:
        self._soglia = soglia
        self._finestra = finestra
        self._clock = clock
        self._lock = threading.Lock()
        self._tentativi: dict[str, deque[float]] = defaultdict(deque)
        self._bloccate: set[str] = set()

    def _pota(self, tentativi: deque[float], adesso: float) -> None:
        limite = adesso - self._finestra
        while tentativi and tentativi[0] < limite:
            tentativi.popleft()

    def consenti(self, installation_id: str) -> str:
        """'ok' e registra il tentativo se sotto soglia. 'nuovo_blocco' la
        prima volta che un'installazione supera la soglia (chi chiama manda
        l'avviso una volta sola). 'gia_bloccata' ai tentativi successivi,
        senza registrarli: un flusso che continua a incalzare non impedisce
        cosi' alla finestra di svuotarsi da sola."""
        adesso = self._clock()
        with self._lock:
            tentativi = self._tentativi[installation_id]
            self._pota(tentativi, adesso)
            if len(tentativi) >= self._soglia:
                if installation_id in self._bloccate:
                    return "gia_bloccata"
                self._bloccate.add(installation_id)
                return "nuovo_blocco"
            tentativi.append(adesso)
            self._bloccate.discard(installation_id)
            return "ok"

    def sblocca(self, installation_id: str) -> None:
        """Il tap del gestore su 'Sblocca' (o un appello accolto): azzera la
        finestra, la linea torna servita subito invece di aspettare che i
        tentativi vecchi scadano da soli."""
        with self._lock:
            self._tentativi[installation_id].clear()
            self._bloccate.discard(installation_id)


def costruisci_notifica_blocco(store, invia_messaggio: InviaMessaggio,
                                invia_bottoni: InviaBottoni) -> NotificaBlocco:
    """Lo dice sia a chi e' stato fermato sia al gestore (S11/5), nello
    stesso istante in cui 'FrenoOrario.consenti' torna 'nuovo_blocco'. Il
    bottone 'Chiedi sblocco' sul messaggio della macchina fermata e' la via
    di risposta richiesta da S7-ter: senza di esso il blocco automatico
    sarebbe una notifica a senso unico."""
    def _notifica(installation_id: str, chat_bloccata: int) -> None:
        invia_messaggio(chat_bloccata,
                         "Troppi invii da questa macchina nell'ultima ora: il relay si e' "
                         "fermato per proteggere il bot per tutti. Se non e' un loop, chiedi "
                         "al gestore di sbloccarti.")
        invia_bottoni(chat_bloccata, "Vuoi che il gestore lo veda subito?",
                      [("Chiedi sblocco", f"{PREFISSO_APPELLO}{installation_id}")])
        gestore_chat = store.gestore_chat_id()
        if gestore_chat is not None:
            invia_bottoni(gestore_chat,
                          f"Installazione fermata per troppi invii nell'ultima ora: {installation_id}.",
                          [("Sblocca", f"{PREFISSO_SBLOCCA}{installation_id}")])
    return _notifica


def costruisci_admin_decision(freno: FrenoOrario, store, invia_messaggio: InviaMessaggio,
                               invia_bottoni: InviaBottoni) -> AdminDecision:
    """Il tap su 'Sblocca' (gestore) o su 'Chiedi sblocco' (chi e' stato
    fermato). Stesso protocollo di 'pairing.costruisci_admin_decision': torna
    True se il callback_data era per questo cancello, a prescindere
    dall'esito, cosi' GestoreWebhook sa fermarsi qui."""
    def _decidi(dato: str, chat_id: int, message_id: int) -> bool:
        if dato.startswith(PREFISSO_SBLOCCA):
            if chat_id != store.gestore_chat_id():
                return True
            installation_id = dato[len(PREFISSO_SBLOCCA):]
            freno.sblocca(installation_id)
            invia_messaggio(chat_id, f"Sbloccato: {installation_id}.")
            chat_bloccata = store.chat_id_di(installation_id)
            if chat_bloccata is not None:
                invia_messaggio(chat_bloccata, "Il gestore ti ha sbloccato: le notifiche riprendono.")
            return True
        if dato.startswith(PREFISSO_APPELLO):
            installation_id = dato[len(PREFISSO_APPELLO):]
            gestore_chat = store.gestore_chat_id()
            if gestore_chat is not None:
                invia_bottoni(gestore_chat, f"{installation_id} chiede lo sblocco.",
                              [("Sblocca", f"{PREFISSO_SBLOCCA}{installation_id}")])
            invia_messaggio(chat_id, "Richiesta inoltrata al gestore.")
            return True
        return False
    return _decidi
