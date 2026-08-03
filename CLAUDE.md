# CLAUDE.md — Atlas

Harness di task a grafo, distribuito come singolo installer. Qui si sviluppa Atlas; il modo di lavorare che Atlas impone ai progetti ospiti sta in `payload/templates/contract.md`.

## Struttura

- `payload/` è l'unica cosa che finisce dentro un progetto ospite. Tutto ciò che sta qui deve funzionare con la sola stdlib di Python 3.10, su POSIX, senza rete.
- `build.py` impacchetta `payload/` dentro `dist/atlas-install.py`. L'installer è un artefatto generato ma **tracciato in git**, perché è il deliverable.
- `tests/` usa `unittest` della stdlib. Nessun runner esterno.

## Regole

- **Zero dipendenze in `payload/`.** Un import di terze parti qui rompe la promessa dell'installer. Nei test e in `build.py` vale la stessa regola, per non dover installare niente prima di poter costruire.
- **Dopo ogni modifica a `payload/` va rigenerato l'installer** con `python3 build.py`, altrimenti `dist/` mente.
- I file di `payload/core/` stanno sotto le 200 righe. Il rimedio al superamento è spezzare, non comprimere.
- La prosa dei documenti generati (ticket, `map.md`, dashboard) è in italiano, con gli accenti scritti alla fonte. Il codice e i nomi dei simboli in inglese.

## Verifica

```bash
python3 -m unittest discover -s tests
python3 build.py && python3 tests/e2e.py    # installa in una sandbox e ne verifica il ciclo
```
