"""Corregge il titolo del grafo appena creato.

Si esegue con:  atlas exec .atlas/scripts/005-titolo-con-accento.py

Lo script gira dentro una sola transazione: se qualcosa non torna, il grafo resta
com'era. Alla chiusura la forma viene validata (id unici, archi risolti, niente cicli).
"""
from core import mutate


def run(g):
    mutate.set_meta(g, title="Affidabilità e coordinamento di Atlas")
