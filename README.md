# Atlas

Harness di task a grafo. I task sono nodi, le dipendenze sono archi, la **frontiera** è quel che si può prendere adesso. Ogni nodo dichiara se la sua risposta si scrive con l'umano (**HITL**) o la scrive l'agente da solo (**AFK**).

## Installare il CLI

```bash
curl -fsSL https://raw.githubusercontent.com/strawberry-code/atlas/main/install.sh | sh
```

Finisce in `~/.local/bin/atlas` (override con `ATLAS_INSTALL_DIR`). Serve Python 3.10+ su POSIX: niente venv, nessuna dipendenza oltre la stdlib.

## Installare in un progetto

```bash
atlas install .                      # oppure atlas install /path/al/progetto
atlas install . --graph mio-epic     # crea subito il primo grafo
```

Finisce tutto in `.atlas/`, più due symlink in `.claude/skills/`, l'hook di fine sessione in `.claude/settings.json` e il contratto in `CLAUDE.md`. Il progetto viene anche registrato in `~/.atlas/registry.json` con uno slug (default: nome della cartella; `--slug` per un nome diverso).

```bash
atlas list                           # progetti registrati e il loro stato
atlas mio-progetto update            # aggiorna SOLO l'harness di quel progetto
atlas update                         # aggiorna SOLO il CLI globale, mai i progetti
```

## Lavorare

Da dentro il progetto, `atlas <comando>` fa da passthrough al motore locale — stesso effetto di `.atlas/bin/atlas <comando>`, forma consigliata perché non richiede il path:

```bash
atlas status                         # frontiera, lucchetti, avanzamento
atlas claim F01                      # rivendica, prima di toccare qualsiasi cosa
atlas show F01                       # domanda, dipendenze, path del ticket
# lavori, poi scrivi la sezione Risposta in .atlas/graphs/<slug>/tickets/F01.md
atlas close F01 -s "sintesi in una riga"
atlas render --open                  # dashboard
```

Un nodo per sessione. `close` rifiuta se la Risposta è vuota.

## Cambiare il grafo

Mai a mano, sempre con uno script:

```bash
atlas new-script aggiunge-ramo-deploy
# scrivi le mutazioni in .atlas/scripts/002-aggiunge-ramo-deploy.py
atlas exec .atlas/scripts/002-aggiunge-ramo-deploy.py
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
atlas new altro-epic -t "Titolo" -d "Dove si arriva."
atlas graphs
atlas use altro-epic       # oppure -g <slug>, oppure ATLAS_GRAPH=<slug>
```

## Le due skill

`atlas-new-graph` costruisce un grafo nuovo, da un testo che hai già o tracciandolo col wayfinder. `atlas-work` lavora un nodo dalla frontiera alla chiusura. Si invocano da sole quando serve.

## Licenza

AGPL-3.0. Vedi `LICENSE`.

## Sviluppare Atlas

```bash
python3 -m unittest discover -s tests   # motore + CLI globale (registry, self-update, install.sh)
python3 build.py && python3 tests/e2e.py  # dist/atlas, provato davvero
```

`payload/` è il motore che finisce nel progetto ospite, e deve restare stdlib pura, POSIX, senza rete. `atlascli/` è il CLI globale (install/update/uninstall/list, registro, self-update): stdlib pura anche lì, ma la rete verso GitHub è consentita perché è un prodotto diverso. Dopo ogni modifica va rigenerato `dist/atlas` con `build.py`. Per tagliare una release: `python3 release.py X.Y.Z` (bump versione, build, test, sha256 — i comandi git/GitHub restano manuali).
