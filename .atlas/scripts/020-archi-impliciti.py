"""Gli ultimi archi che ripetono quel che un altro cammino gia' garantisce.

F01 attende F03, che a sua volta attende F02: dirlo due volte non aggiunge niente.
Q02 attende V03, che sono le foto della dashboard, e quelle non esistono finche'
canvas e archi non sono finiti: attendere anche C12 e A05 e' lo stesso vincolo scritto
due volte.
"""
from core import mutate


def run(g):
    mutate.unlink(g, "F01", "F02")
    mutate.unlink(g, "Q02", "C12")
    mutate.unlink(g, "Q02", "A05")
