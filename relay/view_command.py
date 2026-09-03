"""Il comando '/view' al bot (D02, docs/atlas-relay-design.md S11/4,
S7-bis/9): la stessa domanda dei tre comandi di stato (D01, status_commands.
py), ma la risposta di chi risponde non e' testo. E' una foto scattata dal
browser di sistema, o se nessun browser risponde la pagina alleggerita
stessa come allegato: payload/core/telegram_view.py sceglie quale delle due
(S7-bis, "le due uscite condividono la stessa domanda al client").

Il relay si ferma alla stessa domanda di status_commands.py: riconosce solo
che il testo e' '/view' e lo instrada sulla linea gia' aperta
dell'installazione (A05), con la stessa 'non in linea' quando non la trova
(S7-ter/2, grilling 8: nessuna coda ne' ritentativo). Un comando a parte,
non aggiunto al closed set dei tre di D01: quello resta l'elenco chiuso che
S11/6 ha deciso, '/view' e' un nodo distinto del grafo (D02) con una
risposta di natura diversa (un file, non un messaggio).
"""
from __future__ import annotations

from collections.abc import Callable

COMANDO_VIEW = "/view"

OFFLINE = ("Nessun lavoro in corso su questa installazione in questo momento: "
          "'/view' risponde solo mentre un run e' acceso.")

RisolviInstallazione = Callable[[int], "str | None"]
Push = Callable[[str, dict], bool]
InviaMessaggio = Callable[[int, str], None]
ComandoView = Callable[[str, int], bool]


def costruisci_comando_view(risolvi: RisolviInstallazione, push: Push,
                            invia_messaggio: InviaMessaggio) -> ComandoView:
    """Vero se il testo era '/view' (a prescindere dall'esito della
    consegna): dice a GestoreWebhook (D04) se fermarsi qui o proseguire come
    per un messaggio qualunque. Stesso principio di
    status_commands.costruisci_comando_stato: nessuna coda, un push senza
    installazione risolta o senza linea aperta e' lo stesso 'non in linea'."""
    def _comando(testo: str, chat_id: int) -> bool:
        if testo != COMANDO_VIEW:
            return False
        installation_id = risolvi(chat_id)
        consegnato = installation_id is not None and push(
            installation_id, {"kind": "message", "chat_id": chat_id, "text": testo})
        if not consegnato:
            invia_messaggio(chat_id, OFFLINE)
        return True
    return _comando
