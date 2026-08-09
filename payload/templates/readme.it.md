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

Se `atlas` non si trova dopo l'installazione, aggiungi `~/.local/bin` al tuo `PATH`.

Il progetto sta su [github.com/strawberry-code/atlas](https://github.com/strawberry-code/atlas).
