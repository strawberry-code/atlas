"""Toglie dalla nebbia la nota su F01 che il polling/webhook risolve.

Si esegue con:  atlas exec .atlas/scripts/013-fog-webhook-chiusa.py

La nota (indice 2 della nebbia di 260902-atlas-relay) segnalava che il codice
ereditato da D04 riceveva gli aggiornamenti Telegram via webhook HTTPS invece
del polling deciso dal disegno. E' la stessa nota che 011-relay-polling.py ha
gia' promossa in G01/G02/G03: G01 ha scritto il polling, G02 ha smontato il
webhook e i suoi prerequisiti. Non descrive piu' un buco senza nodo.
"""
from core import mutate

NEEDLE = "riceve gli aggiornamenti Telegram via webhook HTTPS"


def run(g):
    mutate.fog_drop(g, NEEDLE)
