"""Toglie dalla nebbia la domanda su dove viaggino le posizioni delle card
trascinate (C10): restano locali alla macchina per sempre, mai in graph.json
ne' altrove. positions.js le tiene in localStorage, una chiave per grafo
(data-slug su <body>, render.py); nessun canale le porta fuori da li'.

Si esegue con:  atlas exec .atlas/scripts/022-fog-posizioni-locali.py
"""
from core import mutate

NEEDLE = "le posizioni delle card debbano viaggiare fra macchine come il grafo"


def run(g):
    mutate.fog_drop(g, NEEDLE)
