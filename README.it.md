# Atlas

*[English version](README.md)*

Harness di task a grafo. I task sono nodi, le dipendenze sono archi, la **frontiera** è quel che si può prendere adesso. Ogni nodo dichiara se la sua risposta si scrive con l'umano (**HITL**) o la scrive l'agente da solo (**AFK**).

## Cos'è, e quando ha senso usarlo

Atlas prende il lavoro di un progetto, lo scompone in nodi collegati da dipendenze e lo fa vivere in un grafo invece che in una lista. Ogni nodo è un ticket dimensionato su una sessione: una feature da costruire, una domanda da sciogliere, un'esplorazione da fare prima di poter decidere. La frontiera è l'insieme dei nodi prendibili adesso, quelli i cui blocker sono già chiusi: non si sceglie leggendo dall'alto in basso, si guarda cosa è davvero prendibile.

Ogni nodo dichiara anche chi scrive la sua risposta. Un nodo **AFK** (away from keyboard) lo lavora l'agente da solo, e l'output finisce sempre in un file: il ticket stesso o l'artefatto che produce. Un nodo **HITL** (human in the loop) si scioglie parlando: la domanda arriva all'utente una alla volta, e la risposta si scrive insieme.

Ha senso installarlo quando un pezzo di lavoro dura più sessioni e ha dipendenze vere fra le sue parti. Un'epic con una decina di task collegati è il caso tipico, un grafo per epic. Se il lavoro sta in una sessione sola, o è una lista senza dipendenze reali, il grafo aggiunge cerimonia invece di struttura.

## Come si lavora, in pratica

Si installa il CLI, si installa in un progetto (crea `.atlas/`, registra il progetto, aggiunge le due skill), poi il ciclo è sempre lo stesso:

1. **Si crea o importa un grafo**, da un testo che già esiste oppure tracciandolo da zero col wayfinder se l'idea è ancora nebbia. Se ne occupa la skill `atlas-new-graph`.
2. **Si guarda la frontiera** con `atlas status`, o `atlas next` per ordinarla per impatto quando i nodi prendibili sono più d'uno.
3. **Si prende un nodo** con `atlas take <ID>`, prima di toccarlo: rivendica e stampa il suo contesto (domanda, Risposte dei bloccanti, nebbia che lo nomina) nello stesso passo.
4. **Si lavora**: se il nodo è AFK lo fa l'agente da solo, se è HITL la skill `atlas-work` porta le domande una alla volta e aspetta.
5. **Si chiude** con `atlas close <ID> -s "sintesi"`, dopo aver scritto la Risposta nel ticket. Mappa e dashboard si rigenerano da sole.

Un modo di orchestrare più nodi insieme, se il progetto ne ha molti prendibili: una sessione "principale" che guarda la frontiera e coordina, i nodi AFK delegati a sotto-agenti che lavorano in parallelo e scrivono i risultati nei rispettivi ticket, i nodi HITL riservati a una sessione dedicata. Non è una funzione del motore, è un modo di usarlo: Atlas resta la fonte di verità su cosa è fatto, chi coordina sopra è libero di organizzarsi come preferisce.

## Installare il CLI

```bash
curl -fsSL https://raw.githubusercontent.com/strawberry-code/atlas/main/install.sh | sh
```

Su Windows nativo (nessun WSL richiesto):

```powershell
irm https://raw.githubusercontent.com/strawberry-code/atlas/main/install.ps1 | iex
```

Finisce in `~/.local/bin/atlas` (`%USERPROFILE%\.local\bin\atlas` su Windows, override con `ATLAS_INSTALL_DIR`). Serve Python 3.10+: niente venv, nessuna dipendenza oltre la stdlib.

## Installare in un progetto

```bash
atlas install .                      # oppure atlas install /path/al/progetto
atlas install . --graph mio-epic     # crea subito il primo grafo
atlas install . --lang en            # contenuti e skill in inglese invece che italiano
```

In `.atlas/` finiscono solo i dati del progetto: `config.json`, i grafi, gli script di mutazione, le skill, il contratto e un `README.md` che spiega a chi trova quella cartella come procurarsi `atlas`. Il motore non ci finisce: vive nell'eseguibile, uno per macchina. Fuori da `.atlas/` restano due symlink in `.claude/skills/`, l'hook di fine sessione in `.claude/settings.json` e il contratto in `CLAUDE.md`. Il progetto viene anche registrato in `~/.config/atlas.json` con uno slug (default: nome della cartella; `--slug` per un nome diverso).

```bash
atlas list                           # progetti registrati e il loro stato
atlas list mio-progetto              # la scheda di uno solo
atlas update                         # aggiorna atlas stesso all'ultima versione
atlas lang en                        # lingua dei contenuti di questo progetto
atlas lang --global en               # default per i progetti futuri
```

Non esiste un comando per aggiornare il motore di un progetto, perché il motore in un progetto non c'è: aggiorni `atlas` e ogni progetto usa la versione nuova. Reinstallare (`atlas install .`) serve solo a rigenerare skill e contratto, oppure a ripulire un progetto che veniva da una versione precedente.

Cambiare lingua a un progetto esistente rigenera `SKILL.md`, `CONTRACT.md` e ogni dashboard: un `map.md` già scritto nella vecchia lingua non viene toccato (le sue intestazioni non combaciano più), quel grafo resta com'era finché non lo si aggiorna a mano, mentre i ticket nuovi seguono la lingua corrente.

## Lavorare

I comandi del grafo valgono da dentro il progetto, che `atlas` trova da solo risalendo le cartelle:

```bash
atlas status                         # frontiera, lucchetti, avanzamento
atlas next                           # frontiera ordinata per impatto, come suggerimento
atlas take F01                       # rivendica e stampa il contesto in un solo passo
# lavori, poi scrivi la sezione Risposta in .atlas/graphs/<slug>/tickets/F01.md
atlas close F01 -s "sintesi in una riga"
atlas render --open                  # dashboard
atlas doctor                         # controllo di salute: nodi dimenticati, lucchetti fermi, dashboard stantia
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

Altre funzioni: `edit_node`, `link`, `unlink`, `drop` (fuori scopo), `remove_node`, `reopen`, `fog_add`, `fog_drop`, `note_add`, `set_meta`.

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

`payload/` è il motore che finisce nel progetto ospite, e deve restare stdlib pura, multipiattaforma (POSIX e Windows), senza rete. `atlascli/` è il CLI globale (install/update/uninstall/list, registro, self-update): stdlib pura anche lì, ma la rete verso GitHub è consentita perché è un prodotto diverso. Dopo ogni modifica va rigenerato `dist/atlas` con `build.py`. Per tagliare una release: `python3 release.py X.Y.Z` (bump versione, build, test, sha256 — i comandi git/GitHub restano manuali).
