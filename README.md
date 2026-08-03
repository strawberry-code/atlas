# Atlas

Harness di task a grafo. I task sono nodi, le dipendenze sono archi, la **frontiera** è quel che si può prendere adesso. Ogni nodo dichiara se la sua risposta si scrive con l'umano (**HITL**) o la scrive l'agente da solo (**AFK**).

## Installare in un progetto

```bash
cp ~/cristiano/10-projects/15-ai-claude-tooling/atlas/dist/atlas-install.py .
python3 atlas-install.py --yes --graph mio-epic
```

Serve Python 3.10+ su POSIX. Niente rete, niente venv, niente dipendenze.

Finisce tutto in `.atlas/`, più due symlink in `.claude/skills/`, l'hook di fine sessione in `.claude/settings.json` e il contratto in `CLAUDE.md`. Rilanciarlo aggiorna il motore e lascia intatti config, grafi e script.

## Lavorare

```bash
.atlas/bin/atlas status              # frontiera, lucchetti, avanzamento
.atlas/bin/atlas claim F01           # rivendica, prima di toccare qualsiasi cosa
.atlas/bin/atlas show F01            # domanda, dipendenze, path del ticket
# lavori, poi scrivi la sezione Risposta in .atlas/graphs/<slug>/tickets/F01.md
.atlas/bin/atlas close F01 -s "sintesi in una riga"
.atlas/bin/atlas render --open       # dashboard
```

Un nodo per sessione. `close` rifiuta se la Risposta è vuota.

## Cambiare il grafo

Mai a mano, sempre con uno script:

```bash
.atlas/bin/atlas new-script aggiunge-ramo-deploy
# scrivi le mutazioni in .atlas/scripts/002-aggiunge-ramo-deploy.py
.atlas/bin/atlas exec .atlas/scripts/002-aggiunge-ramo-deploy.py
```

```python
from core import mutate

def run(g):
    mutate.add_branch(g, "X", "Consegna", "#0f766e")
    mutate.add_node(g, id="X01", branch="X", type="task", mode="AFK",
                    title="Pipeline di build",
                    question="Che cosa produce, e come si verifica che sia buono?",
                    blockedBy=["F03"])
```

Tutto gira in una transazione sola e viene validato prima di scrivere: cicli, archi verso il nulla e id duplicati fanno fallire lo script senza toccare il file.

Altre funzioni: `edit_node`, `link`, `unlink`, `drop` (fuori scopo), `remove_node`, `reopen`, `fog_add`, `note_add`, `set_meta`.

## Più grafi

Uno per epic, isolati.

```bash
.atlas/bin/atlas new altro-epic -t "Titolo" -d "Dove si arriva."
.atlas/bin/atlas graphs
.atlas/bin/atlas use altro-epic       # oppure -g <slug>, oppure ATLAS_GRAPH=<slug>
```

## Le due skill

`atlas-new-graph` costruisce un grafo nuovo, da un testo che hai già o tracciandolo col wayfinder. `atlas-work` lavora un nodo dalla frontiera alla chiusura. Si invocano da sole quando serve.

## Sviluppare Atlas

```bash
python3 -m unittest discover -s tests   # motore
python3 build.py && python3 tests/e2e.py  # installer, provato davvero
```

`payload/` è ciò che finisce nel progetto ospite, e deve restare stdlib pura. Dopo ogni modifica va rigenerato `dist/atlas-install.py` con `build.py`.
