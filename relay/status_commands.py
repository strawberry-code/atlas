"""I tre comandi di stato al bot (D01, docs/atlas-relay-design.md S11/6):
'/stato' (a che punto e' il lavoro), '/aspetta' (cosa aspetta una persona),
'/storto' (cos'e' andato storto). Elenco chiuso, non uno di piu'.

Il relay non conserva lo stato di nessun progetto (grilling 7): riconosce
solo che il testo e' uno dei tre comandi e lo spinge, come un tap qualunque
(A05), sulla sola linea gia' aperta dell'installazione di questa chat. Chi
risponde davvero e' il client (payload/core/telegram_status.py), che compone
il testo dal ledger locale e lo rimanda con un 'invia_messaggio' proprio, lo
stesso canale d'uscita gia' usato da ogni notifica (D07).

La linea resta aperta solo mentre un lavoro gira (S6-bis/32): se il push non
trova nessuno, il relay lo dice subito invece di tacere o far aspettare
(S7-ter/2), con lo stesso segnale gia' verificato per un tap (grilling 8,
'RegistroTunnel.push' torna falso senza coda ne' ritentativo).
"""
from __future__ import annotations

from collections.abc import Callable

COMANDO_STATO = "/stato"
COMANDO_ASPETTA = "/aspetta"
COMANDO_STORTO = "/storto"
COMANDI = frozenset({COMANDO_STATO, COMANDO_ASPETTA, COMANDO_STORTO})

OFFLINE = ("Nessun lavoro in corso su questa installazione in questo momento: "
          "questi comandi rispondono solo mentre un run e' acceso.")

RisolviInstallazione = Callable[[int], "str | None"]
Push = Callable[[str, dict], bool]
InviaMessaggio = Callable[[int, str], None]
ComandoStato = Callable[[str, int], bool]


def costruisci_comando_stato(risolvi: RisolviInstallazione, push: Push,
                             invia_messaggio: InviaMessaggio) -> ComandoStato:
    """Vero se il testo era uno dei tre comandi (a prescindere dall'esito
    della consegna): dice a GestoreWebhook (D04) se fermarsi qui o
    proseguire come per un messaggio qualunque. Nessuna coda: un push senza
    installazione risolta o senza linea aperta e' lo stesso 'non in linea'
    (S7-ter/2), risposto subito, mai lasciato scoprire da solo."""
    def _comando(testo: str, chat_id: int) -> bool:
        if testo not in COMANDI:
            return False
        installation_id = risolvi(chat_id)
        consegnato = installation_id is not None and push(
            installation_id, {"kind": "message", "chat_id": chat_id, "text": testo})
        if not consegnato:
            invia_messaggio(chat_id, OFFLINE)
        return True
    return _comando
