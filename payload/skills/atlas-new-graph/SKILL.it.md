---
name: atlas-new-graph
description: Costruisce un grafo di task Atlas nuovo, partendo da un testo che l'utente ha già oppure tracciandolo da zero con il wayfinder. Usala quando l'utente vuole pianificare un epic, trasformare un documento in task, o dice di voler creare un grafo.
---

# Costruire un grafo

Il risultato non è mai un JSON scritto a mano: è uno **script di mutazione** in `.atlas/scripts/`, che si legge in diff e si riesegue. Questa skill porta dal nulla a quello script.

## Passo 0 — da dove si parte

Chiedi all'utente, con AskUserQuestion, una cosa sola:

- **Ha già un testo?** Un documento, una lista di task, note di una riunione, un issue, una roadmap. In quel caso il lavoro è tradurre, e passi al ramo A.
- **Oppure c'è solo un'idea?** Allora la mappa va tracciata, e passi al ramo B.

Chiedi anche lo **slug** del grafo (kebab-case, es. `epic-auth`) e il **titolo**, se non li ha già detti. Se il progetto ha già dei grafi, mostraglieli con `atlas graphs`: forse il lavoro appartiene a uno di quelli.

## Ramo A — c'è un testo

1. Leggilo tutto prima di proporre qualsiasi cosa.
2. **Nomina la destinazione**: una o due righe che dicono dove si arriva quando il grafo è finito. Se dal testo non si ricava, chiedila. Senza destinazione non si può decidere cosa sta fuori scopo.
3. Individua i **rami**: 3-6 filoni di lavoro, ognuno con una lettera e un colore. I rami servono a leggere il grafo, non a organizzare l'esecuzione.
4. Ricava i **nodi**. Ognuno è dimensionato su una sessione di lavoro sola. Un nodo che contiene tre decisioni indipendenti va spezzato; tre nodi che si chiudono con la stessa frase vanno fusi.
5. Cabla le **dipendenze**: un arco `blockedBy` esiste quando il secondo nodo non è nemmeno formulabile finché il primo non ha risposto. Un semplice "viene prima nel tempo" non è una dipendenza. Fai **convergere il grafo in un nodo finale unico**, di solito un cancello che verifica la destinazione: un terminale che non vi confluisce è un ramo il cui esito nessuno raccoglierà, e `atlas doctor` lo segnala.
6. **Mostra la struttura all'utente prima di scrivere** — id, titolo, tipo, modo, blocker — e chiedi conferma. È qui che si correggono le cose, non dopo.

## Ramo B — c'è solo un'idea

Usa la skill `wayfinder`, se installata, con l'obiettivo dichiarato di produrre un grafo Atlas invece di ticket su un tracker. In breve, il metodo:

1. **Nomina la destinazione** con `grilling` e `domain-modeling`, una domanda alla volta.
2. **Mappa la frontiera** grigliando ancora, ma in ampiezza: ventaglia su tutto lo spazio del problema invece di scendere a fondo su un filo solo. Serve a far emergere la nebbia, cioè quello che non sai ancora.
3. Se dal grilling non emerge nebbia, **fermati e dillo all'utente**: se il lavoro è già chiaro, un grafo è una cerimonia inutile.
4. Trasforma in nodi solo quello che sai già formulare con precisione. Il test è se riesci a enunciare la domanda adesso, non se sai già rispondere. Il resto va nella nebbia con `mutate.fog_add`, e diventerà un nodo quando qualche risposta l'avrà reso specificabile.
5. Tracciare la mappa è il lavoro di una sessione. **Non risolvere anche dei nodi** nella stessa sessione.

## Tipo e modo di ogni nodo

| Tipo | Quando | Modo tipico |
|---|---|---|
| `grilling` | sciogliere una decisione parlando | HITL |
| `research` | leggere documentazione, API, fonti | AFK |
| `prototype` | costruire un artefatto rozzo a cui reagire | HITL |
| `task` | lavoro manuale che deve accadere perché una decisione diventi possibile | HITL o AFK |

Il **modo** è la domanda più importante che fai a ogni nodo: la risposta la può scrivere l'agente da solo (AFK) oppure va costruita con l'umano (HITL)? Nel dubbio è HITL. Un nodo che decide qualcosa di irreversibile è sempre HITL.

## Scrivere lo script

```sh
atlas new <slug> -t "Titolo del grafo" -d "La destinazione, in una o due righe."
atlas new-script primo-disegno
```

Poi riempi lo script generato in `.atlas/scripts/`:

```python
from core import mutate

def run(g):
    mutate.add_branch(g, "F", "Fondamenta", "#4f46e5")
    mutate.add_branch(g, "X", "Distribuzione", "#0f766e")

    mutate.add_node(g, id="F01", branch="F", type="grilling", mode="HITL",
                    title="Contratto operativo",
                    question="Con quale contratto lavora l'agente su questo repo? Il testo lungo del ticket va qui.")
    mutate.add_node(g, id="X01", branch="X", type="task", mode="AFK",
                    title="Pipeline di build",
                    question="Che cosa produce la pipeline, e come si verifica che l'artefatto sia buono?",
                    blockedBy=["F01"])

    mutate.note_add(g, "Le decisioni di interfaccia passano dalla skill design-an-interface.")
    mutate.fog_add(g, "come si distribuiscono gli aggiornamenti fuori dallo store")
```

L'ordine di creazione non conta: la validazione avviene alla fine della transazione, quindi puoi nominare in `blockedBy` un nodo che crei più sotto. Quello che conta è che alla fine ogni arco risolva e che non ci siano cicli.

Una voce di nebbia (`atlas fog --list` per rileggerle tutte) che matura in un nodo si promuove nello stesso tipo di script, aggiungendo il nodo e togliendo la voce con `fog_drop`, che cerca una sottostringa:

```python
def run(g):
    mutate.add_node(g, id="F04", branch="F", type="task", mode="AFK",
                    title="Come si distribuiscono gli aggiornamenti",
                    question="...", blockedBy=["F01"])
    mutate.fog_drop(g, "distribuiscono gli aggiornamenti")
```

Poi:

```sh
atlas exec .atlas/scripts/001-primo-disegno.py
atlas render --open
```

`exec` scrive i ticket mancanti, rigenera la mappa e la dashboard, e stampa la frontiera. Guardala insieme all'utente: un grafo con venti nodi tutti prendibili non ha dipendenze vere, uno con un nodo solo prendibile è una lista travestita da grafo, e più nodi terminali sono rami che non confluiscono nel finale.

## La domanda di ogni nodo

Il campo `question` diventa il corpo del ticket, quindi scrivilo per intero: un paragrafo che dice cosa va deciso o fatto, e che cosa si considera una risposta. Un titolo breve più una domanda lunga si leggono bene; una domanda che ripete il titolo non aiuta nessuno.
