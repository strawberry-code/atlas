"""Accenti veri nelle question e nella fog.

Si esegue con:  atlas exec .atlas/scripts/002-accenti-nel-contenuto.py

Il disegno era stato scritto con la forma ASCII (perche', verita', puo') che in questo
progetto vale per i commenti del motore. Ma question, title e fog sono contenuto: li
legge una persona nel ticket e nella dashboard, e li' un apostrofo al posto
dell'accento e' un difetto, non una convenzione.
"""
from core import mutate


def run(g):
    mutate.edit_node(g, "A01", question=(
        "Quando due macchine chiudono nodi diversi, quali conflitti produce graph.json, "
        "quali sono ambigui per davvero e quali lo sono solo perché il file è uno?"))
    mutate.edit_node(g, "L02", question=(
        "Il claim oggi vale finché vive un PID locale. Cosa cambia nel modello quando quel "
        "PID sta su un'altra macchina, e quale scadenza rende un lucchetto ancora un lucchetto?"))
    mutate.edit_node(g, "L05", question=(
        "Come convivono lucchetto locale e lucchetto remoto senza due verità sullo stesso nodo?"))
    mutate.edit_node(g, "V02", question=(
        "Con che passo si leggono i lucchetti remoti perché la vista sia viva senza "
        "martellare il remote a ogni secondo?"))
    mutate.edit_node(g, "C01", question=(
        "Cosa cambia nei due README, nel contratto e in how-to, adesso che un claim può "
        "venire da un'altra macchina?"))
    mutate.edit_node(g, "C02", question=(
        "Due cloni, due identità, due agenti che prendono e chiudono insieme: cosa deve "
        "succedere perché la prova valga qualcosa e non sia compiacente?"))
    mutate.fog_drop(g, "rinominare o togliere un ramo")
    mutate.fog_add(g, "manca una mutazione per rinominare o togliere un ramo: il ramo di "
                      "default creato da create_graph si può solo riscrivere a mano")
