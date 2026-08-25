"""La nota che tiene vivo il trial mentre il grafo si usa.

Si esegue con:  atlas exec .atlas/scripts/003-nota-del-collaudo.py

Le Note della mappa si leggono a ogni sessione: e' l'unico posto che vede chi
lavora il grafo senza aprire il ticket di C03. Non e' una skill di proposito,
perche' 'atlas update' riscrive .atlas/skills/ dal payload e una regola messa
li' sparirebbe al primo aggiornamento.
"""
from core import mutate


def run(g):
    mutate.note_add(g, "Trial sul campo fino al 2026-09-09: due macchine, due identità, "
                       "lavoro vero. Dopo OGNI merge lancia `atlas doctor` e annota i "
                       "`concurrent close` / `divergent state` che riporta. La regola di "
                       "decisione e l'alternativa stanno in C03 e in "
                       "docs/adr/0001-centralized-graph-service.md.")
