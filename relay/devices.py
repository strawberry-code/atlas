"""Elenco dei computer collegati e distacco (C02, docs/atlas-relay-design.md
S7-ter/5): chi cambia Mac o reinstalla lascerebbe il vecchio collegamento
appeso per sempre, e il relay non puo' accorgersene da solo. Il rimedio non e'
un battito periodico (S7-ter dice esplicitamente che manca, per scelta): e'
mostrare a chi guarda quando ha visto per l'ultima volta ciascuna
installazione, e lasciargli staccare quella morta con un tap.

'ultima vista' non nasce da un ping dedicato, nasce dal segnale di attivita'
che il relay gia' osserva: ogni volta che un'installazione apre una linea sul
tunnel (D03/S6-bis/32, la linea resta aperta solo mentre un lavoro gira),
'atlas_relay._tunnel' chiama 'pairing.GestorePairing.segna_vista'. Nessun
traffico a vuoto in piu', nessun processo residente in piu' su nessuna delle
due macchine.

Il comando e' per chi lo chiede, non per il gestore (S11/3 riguarda
l'ingresso, non questo): elenca e stacca solo le installazioni della chat che
lo invoca ('pairing.installazioni_di'), mai quelle di un'altra chat. Lo
stesso slot 'admin_decision' di GestoreWebhook che gia' porta i tap del
gestore (A03) e dell'appello dell'utente (C01) porta anche questo: non un
potere del gestore, ma un gesto sul proprio collegamento, come 'utente:appello:'.
"""
from __future__ import annotations

import time
from collections.abc import Callable

import pairing

COMANDO = "/computer"
PREFISSO_STACCA = "utente:stacca:"

InviaMessaggio = Callable[[int, str], None]
InviaBottoni = Callable[[int, str, list], None]
ModificaMessaggio = Callable[[int, int, str], None]
ComandoDispositivi = Callable[[int], None]
DispositiviDecision = Callable[[str, int, int], bool]


def _fa_quanto(secondi: float) -> str:
    """'ultima volta vista', in parole umane dal secondo al mese: chi legge
    l'elenco deve capire se una macchina e' viva o morta, non fare i conti su
    un timestamp grezzo (S0)."""
    if secondi < 60:
        return "pochi istanti fa"
    minuti = int(secondi // 60)
    if minuti < 60:
        return f"{minuti} minut{'o' if minuti == 1 else 'i'} fa"
    ore = int(secondi // 3600)
    if ore < 24:
        return f"{ore} or{'a' if ore == 1 else 'e'} fa"
    giorni = int(secondi // 86400)
    if giorni < 30:
        return f"{giorni} giorn{'o' if giorni == 1 else 'i'} fa"
    mesi = int(giorni // 30)
    return f"{mesi} mes{'e' if mesi == 1 else 'i'} fa"


def costruisci_comando(store: pairing.GestorePairing, invia_messaggio: InviaMessaggio,
                        invia_bottoni: InviaBottoni,
                        clock: Callable[[], float] = time.time) -> ComandoDispositivi:
    """'/computer': le installazioni di questa chat, la piu' di recente vista
    prima (stesso ordine di 'installazioni_di'), un bottone 'Stacca' per
    ciascuna. Zero installazioni non e' un errore: e' lo stato legittimo di
    una chat mai appaiata, o gia' staccata da tutte."""
    def _elenca(chat_id: int) -> None:
        installazioni = store.installazioni_di(chat_id)
        if not installazioni:
            invia_messaggio(chat_id, "Nessun computer collegato a questa chat.")
            return
        adesso = clock()
        righe = []
        bottoni = []
        for installation_id in installazioni:
            vista = store.ultima_vista(installation_id)
            quando = _fa_quanto(adesso - vista) if vista is not None else "mai vista da quando si e' collegata"
            righe.append(f"{installation_id}: vista {quando}")
            bottoni.append((f"Stacca {installation_id}", f"{PREFISSO_STACCA}{installation_id}"))
        invia_messaggio(chat_id, "\n".join(righe))
        invia_bottoni(chat_id, "Stacca un collegamento:", bottoni)
    return _elenca


def costruisci_decision(store: pairing.GestorePairing, invia_messaggio: InviaMessaggio,
                         modifica_messaggio: ModificaMessaggio) -> DispositiviDecision:
    """Il tap su 'Stacca <installazione>': stesso protocollo di
    'pairing.costruisci_admin_decision', ma il controllo di appartenenza e'
    sulla chat che tocca, non sul gestore (S7-ter/5: e' un gesto dell'utente
    sul proprio collegamento). Un tap su un'installazione che non e' (piu')
    di questa chat e' assorbito senza traccia ne' effetto, stesso principio
    gia' in uso per un tap del gestore da una chat sbagliata."""
    def _decidi(dato: str, chat_id: int, message_id: int) -> bool:
        if not dato.startswith(PREFISSO_STACCA):
            return False
        installation_id = dato[len(PREFISSO_STACCA):]
        if installation_id not in store.installazioni_di(chat_id):
            return True
        store.stacca(installation_id)
        modifica_messaggio(chat_id, message_id, f"Staccato: {installation_id}.")
        invia_messaggio(chat_id, f"Non ricevi piu' notifiche da {installation_id}.")
        return True
    return _decidi
