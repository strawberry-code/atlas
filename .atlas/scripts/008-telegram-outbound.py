"""Aggiunge il nodo D07: il canale Telegram che manda il primo messaggio.

D01 aveva assegnato a D04 la consegna iniziale con i bottoni, ma D04 ha
costruito solo la meta' lato relay. Senza il lato client nessuno chiama
capability.emetti() fuori dai test: un tap arriva fino al ledger, ma il
messaggio su cui premerlo oggi non parte. END aspetta anche questo.

Si esegue con: atlas exec .atlas/scripts/008-telegram-outbound.py
"""
from core import mutate


def run(g):
    mutate.add_node(
        g,
        id="D07",
        title="Manda la notifica Telegram con i bottoni",
        branch="D",
        question=(
            "Costruisci il canale Telegram in uscita che consegna una Interazione "
            "aperta come messaggio con i bottoni delle azioni ammesse, emettendo "
            "una capability per ciascuno. Deve passare dal coordinatore notifiche "
            "di C01 e dal tunnel di D03, registrare l'esito della consegna e "
            "rispettare la deduplica gia' in vigore."
        ),
        type="task",
        mode="AFK",
        blockedBy=["C01", "D04", "D05", "D06"],
    )
    mutate.link(g, "END", "D07")
