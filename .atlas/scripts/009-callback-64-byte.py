"""Aggiunge il nodo D08: la capability non entra nel callback di Telegram.

D01 ha messo il token capability dentro 'callback_data', D06 lo ha ereditato e
D07 lo ha misurato: circa 270 byte contro i 64 che Telegram accetta. Ogni invio
di bottoni fallirebbe al primo deploy reale. Il rimedio sta nel protocollo, non
nel canale: nel callback un identificativo corto, la capability nello store del
relay che la risolve alla ricezione.

Si esegue con: atlas exec .atlas/scripts/009-callback-64-byte.py
"""
from core import mutate


def run(g):
    mutate.add_node(
        g,
        id="D08",
        title="Fai stare il callback Telegram in 64 byte",
        branch="D",
        question=(
            "Cambia il trasporto della capability nei bottoni Telegram: nel "
            "callback_data va un identificativo corto e opaco, la capability "
            "resta nello store del relay che la risolve quando il tap arriva. "
            "Le garanzie di D01 (monouso, scadenza, firma non interpretata dal "
            "relay) devono restare intatte, e un identificativo sconosciuto o "
            "gia' speso va rifiutato come oggi."
        ),
        type="task",
        mode="AFK",
        blockedBy=["D06", "D07"],
    )
    mutate.link(g, "END", "D08")
