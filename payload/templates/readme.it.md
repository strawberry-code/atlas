# Questa cartella è un grafo di lavoro Atlas

Qui dentro non c'è codice: ci sono i dati del lavoro di questo progetto, scomposto in nodi collegati da dipendenze. I ticket, la mappa e le dashboard si rigenerano da `graphs/*/graph.json`.

```
graphs/     i grafi: nodi, ticket, mappa, dashboard
scripts/    gli script che cambiano la forma del grafo
skills/     le skill per l'agente
config.json come si chiama il progetto e in che lingua scrive
CONTRACT.md come si lavora qui: leggilo prima di toccare qualcosa
```

## Per aprirlo serve il programma

Il motore non sta in questa cartella, sta in un eseguibile unico che si installa una volta per macchina.

```sh
curl -fsSL https://raw.githubusercontent.com/strawberry-code/atlas/main/install.sh | sh
```

Su Windows, in PowerShell:

```powershell
irm https://raw.githubusercontent.com/strawberry-code/atlas/main/install.ps1 | iex
```

Serve Python 3.10 o superiore, e nient'altro: niente venv, nessuna dipendenza.

## Poi

```sh
atlas how-to     # il briefing completo: contratto, comandi, mutazioni, path
atlas status     # a che punto è il lavoro, e cosa si può prendere adesso
```

## Run Automata

`atlas run --parallelism N` configura un run Automata; `N` è obbligatorio per ogni run, `1` è l'esecuzione strettamente seriale e i valori maggiori sono parallelismo limitato. Il campo `model` del nodo è opzionale: vuoto significa Codex Luna, con un solo fallback a Claude Sonnet quando Luna non è disponibile. I provider vengono eseguiti AFK, fuori sandbox e con bypass dei permessi.

Usa `atlas run-status` per lo stato persistente e il motivo, e `atlas run-log --tail N` per gli ultimi claim, provider, fallback, guasti, backoff, chiusure e aggiornamenti della frontiera. Timeout, crash, rate limit, provider non disponibile e terminazione ambigua sono ritentabili; gli errori permanenti no. Aggiungi un provider registrando un `AgentAdapter` o `SubprocessAdapter` in `AdapterRegistry`; il runner non cambia.

Se `atlas` non si trova dopo l'installazione, aggiungi `~/.local/bin` al tuo `PATH`.

Il progetto sta su [github.com/strawberry-code/atlas](https://github.com/strawberry-code/atlas).
