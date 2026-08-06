"""Promuove una voce di nebbia a nodo del grafo.

E' un esempio da modificare, e la seconda meta' del gesto 'atlas fog': la nebbia
raccoglie quel che emerge lavorando e non ha ancora un nodo, questo script e' la
via ovvia per farlo diventare uno.

Prima si guarda cosa c'e' in nebbia:  atlas fog --list
poi si compilano INDICE e NUOVO qui sotto, e si esegue con:
                                      atlas exec .atlas/scripts/000-promote-fog.py
"""
from core import mutate

INDICE = None              # il numero fra parentesi quadre stampato da 'atlas fog --list'
NUOVO = {
    "id": "X01",           # deve essere libero: 'atlas show X01' non deve trovare niente
    "branch": "A",         # un ramo che esiste gia' nel grafo
    "title": "Titolo del nodo nato dalla nebbia",
    "question": "La domanda a cui questo nodo risponde.",
    "type": "task",
    "mode": "AFK",
    "blockedBy": [],       # gli id che devono chiudere prima che questo sia prendibile
}


def run(g):
    if INDICE is None:
        raise NotImplementedError("scegli INDICE e compila NUOVO, poi rilancia")
    voce = g.data["fog"][INDICE]
    mutate.add_node(g, **NUOVO)
    mutate.fog_drop(g, voce)   # fog_drop lavora per sottostringa: le passiamo la voce intera
    mutate.note_add(g, f"{NUOVO['id']} nasce da una voce di nebbia: {voce}")
