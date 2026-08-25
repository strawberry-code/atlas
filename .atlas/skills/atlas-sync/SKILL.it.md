---
name: atlas-sync
description: Riporta la copia del grafo Atlas di questo progetto in pari con quella degli altri agenti e pubblica il proprio lavoro, anche quando `graph.json` è andato in conflitto. Usala prima di un push su un grafo condiviso, o quando un merge tocca il grafo.
---

# Allineare un grafo condiviso

Il grafo condiviso si cambia solo con script di mutazione. Quando due agenti lavorano lo stesso grafo su copie diverse, prima o poi `graph.json` va in conflitto. Fonderlo a mano è il rimedio peggiore, perché il file smette di essere il prodotto di una sequenza di script e nessuno sa più ricostruire come ci si è arrivati. Questa skill allinea la tua copia a quella di chi ha pubblicato per primo e riapplica il tuo lavoro sopra con script, così la storia resta lineare.

## 1. Prima di pubblicare, chiudi la sessione

```sh
atlas status
```

`status` mostra i lucchetti: se ce n'è uno tuo ancora aperto, chiudi il nodo con `atlas close <ID> -s "..."` oppure molla con `atlas release <ID>`. Il lavoro va committato prima di passare oltre.

## 2. Guarda se il grafo si è mosso

```sh
git fetch
git log --oneline HEAD..origin/<ramo> -- .atlas/
```

Se non è uscito niente, nessun altro ha toccato il grafo. Il push è ordinario e la procedura finisce qui.

## 3. Annota cosa hai fatto tu

```sh
BASE=$(git merge-base HEAD origin/<ramo>)
git diff $BASE..HEAD -- .atlas/graphs/<slug>/graph.json
```

Da quel diff escono tre categorie, e servono tutte e tre dopo: gli script tuoi non ancora pubblicati, le chiusure che hai fatto, le assegnazioni e la nebbia che hai aggiunto.

## 4. Fondi prendendo il loro grafo

```sh
git merge origin/<ramo>
git checkout origin/<ramo> -- .atlas/graphs/<slug>/graph.json
```

Il checkout del file loro si scrive per esteso, col nome del ramo, mai con `--ours` o `--theirs`, perché fra merge e rebase le due parole si invertono ed è l'errore che si fa. Chi ha pubblicato per primo fa da base, e il proprio lavoro si riapplica sopra. Solo in questo verso la storia degli script resta lineare e rieseguibile.

Per gli altri file vale lo stesso criterio. `map.md` si prende dal remoto senza pensarci, perché le sezioni che il grafo possiede, fra cui Decisioni prese, si rigenerano da sole al primo comando che tocca il grafo. Restano da fondere a mano soltanto Destinazione e Note, se le avete scritte entrambi. I ticket sono un file per nodo e raramente confliggono.

## 5. Rinumera i tuoi script in coda ai loro

```sh
atlas renumber <i tuoi file>
```

Li sposta dopo il massimo degli altri, nell'ordine che indichi, con `git mv` dove serve.

## 6. Scrivi lo script di allineamento

Quello che non era uno script si riapplica con uno script nuovo, mai a mano.

```sh
atlas new-script riallinea-<qualcosa>
```

Poi riempi lo script generato:

```python
from core import mutate

def run(g):
    mutate.restore_closure(g, "F02", answer="...", closedBy="...", closedAt="...")
    mutate.assign(g, "anna,marco", ["F05"])
    mutate.fog_add(g, "...")
```

Aggiungi una `restore_closure` per ogni nodo che avevi chiuso tu. I metadati li leggi dal diff del passo 3: sono quelli veri, della chiusura avvenuta sulla tua copia, e vanno ricopiati, non inventati. Poi aggiungi le assegnazioni con `mutate.assign` e la nebbia con `mutate.fog_add`.

## 7. Riesegui in ordine

```sh
atlas exec <i tuoi script, in ordine>
```

`exec` accetta più script in una volta e li applica dal primo all'ultimo, fermandosi al primo che fallisce.

## 8. Verifica e pubblica

```sh
atlas doctor
atlas status
```

Prima del commit, `doctor` e `status` devono passare puliti. Il push è un gesto che l'utente ha chiesto, non l'ultimo passo automatico della procedura. Chiedilo, se non è già stato detto.

## Cosa non fare

- **Non aprire `graph.json` in un editor** per fondere due versioni. Il file smette di essere il prodotto di una sequenza di script, e nessuno sa più ricostruire come ci si è arrivati.
- **Non rieseguire uno script già applicato** sul grafo che hai preso come base: i suoi nodi ci sono già, e l'esecuzione muore dicendo che l'id esiste.
- **Non usare `restore_closure` per chiudere un nodo vero.** Un nodo si chiude con `atlas close`.
