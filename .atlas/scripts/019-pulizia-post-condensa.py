"""Le scorie della condensazione: archi ridondanti e terminali orfani.

Fondere diciassette nodi ha lasciato due tracce. Archi che ripetono quel che un
altro cammino gia' garantisce (Q02 attende C05 e insieme C12, che da C05 discende),
e due nodi chiusi diventati terminali perche' chi li bloccava e' stato assorbito.
"""
from core import mutate


def run(g):
    # Un arco gia' implicato da un altro cammino appesantisce la lettura e basta.
    for nodo, blocker in (("Q02", "C05"), ("Q02", "A05"), ("Q02", "C12"),
                          ("Q03", "S03"), ("V03", "C01"), ("Q04", "V01"), ("Q04", "V03")):
        mutate.unlink(g, nodo, blocker)
    mutate.link(g, "Q02", "C12")
    mutate.link(g, "Q02", "A05")

    # F02 e F03 sono chiusi, ma la fusione di F07 dentro F01 li ha lasciati senza
    # nessuno che dipenda da loro: due terminali che non convergono nel finale, che
    # e' proprio cio' che 'atlas doctor' segnala. Il lavoro di F01 poggia sul loro.
    mutate.link(g, "F01", "F02")
    mutate.link(g, "F01", "F03")
