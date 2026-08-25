---
name: atlas-wayfinder
description: La dottrina che regge un grafo Atlas: nominare la destinazione, decidere invece di fare, distinguere la nebbia da un nodo, mettere fuori ambito quel che sta oltre la destinazione. Usala quando arriva un'idea troppo grande per una sessione e ancora avvolta nella nebbia, prima di sapere se un grafo serve davvero.
---

# Trovare la via

È arrivata un'idea grande, e la via che porta dall'oggi alla **destinazione** non si vede ancora. Trovare la via è il lavoro, non caricare la destinazione a testa bassa. Un grafo Atlas è la mappa di quella ricerca: nodi che sciolgono un'incertezza alla volta, finché la strada è chiara e non resta niente da decidere.

Questa skill è il metodo. La meccanica di costruzione sta in `atlas-new-graph`, quella di lavorazione in `atlas-work`.

## La destinazione si nomina per prima

La destinazione è quel che si vede quando la mappa è finita: una specifica da passare a qualcuno, una decisione da fissare prima che si possa pianificare, un cambiamento fatto sul posto come una migrazione di dati. Una o due righe, e stanno in `map.md` sotto **Destinazione**: ogni sessione ci si orienta prima di scegliere un nodo.

Nominarla è il primo atto perché **fissa l'ambito**. Tutto quel che viene dopo, quali nodi esistono e quali no, si misura su di lei.

## Si decide, non si fa

Un grafo pianifica. Ogni nodo scioglie una decisione, e la mappa è finita quando la via è chiara, cioè quando non resta niente da decidere prima che qualcuno vada a costruire. La voglia di mettersi a fare, che arriva quasi sempre, di solito è il segnale che sei arrivato al bordo della mappa ed è ora di consegnare.

Il tipo `task` è l'eccezione che conferma la regola: fa del lavoro vero, ma si giustifica perché sblocca una decisione, non perché consegna la destinazione. Un progetto che vuole portare l'esecuzione dentro la mappa lo dichiara nelle **Note** con `mutate.note_add`. Senza quella dichiarazione, produci decisioni.

## Chiamali per nome

Gli id di Atlas sono corti (`F01`, `X02`) e servono ai comandi. Quando parli con l'utente, però, un muro di id è illeggibile: nomina sempre il titolo accanto all'id. L'id non sparisce, viaggia dentro il nome invece di sostituirlo.

## La mappa è un indice, non un magazzino

`map.md` dice dove si va, cosa è già stato deciso e in quale nodo sta il dettaglio. Non ripete il contenuto delle Risposte: una decisione vive in un posto solo, il suo ticket. Per questo la sintesi che passi a `atlas close -s` è **una riga**, non un riassunto: quella riga finisce in Decisioni prese ed è l'unica cosa che una sessione futura legge prima di decidere se aprire il ticket.

## Nebbia o nodo

La mappa è deliberatamente incompleta: non si traccia quel che non si vede. Oltre i nodi vivi c'è la nebbia, cioè le decisioni che senti arrivare ma che non sai ancora enunciare, perché dipendono da domande ancora aperte. Sciogliere un nodo dirada la nebbia davanti a sé, e quel che è diventato enunciabile si promuove a nodo, uno alla volta.

**Il test è se sai enunciare la domanda adesso, non se sai rispondere.**

- **Nodo** quando la domanda è già netta, anche se è bloccata e non puoi toccarla oggi.
- **Nebbia** quando non sai ancora formularla così. Si appunta con `atlas fog "..."` (o `mutate.fog_add` in uno script) e finisce sotto **Non ancora specificato**. Non affettarla in pezzi grandi come un nodo: è più grossolana, e una singola patch può diventare tre nodi oppure nessuno.

La nebbia esclude quel che è già deciso, quel che è già un nodo vivo e quel che è fuori ambito.

## Fuori ambito non è nebbia

La nebbia si raccoglie sempre **verso** la destinazione. Quel che sta oltre non è nebbia che non si è ancora diradata, è lavoro che hai consapevolmente escluso da questo grafo. A distinguerli non è la nitidezza ma l'ambito.

Quando un nodo che esiste già si rivela oltre la destinazione, non lo si risolve e non lo si cancella:

```python
mutate.drop(g, "X03", "sta oltre la destinazione: la migrazione dei dati storici è un lavoro suo")
```

`drop` lo porta a `out-of-scope`, lo toglie dalla frontiera, lo scrive sotto **Fuori ambito** con la ragione, e continua a sbloccare chi lo aspettava. Non torna mai indietro: se la destinazione viene ridisegnata, quello è un grafo nuovo, non la ripresa di questo.

## Un nodo per sessione

Tracciare la mappa è il lavoro di una sessione, e non se ne risolve nessuno nella stessa. Lavorando, si chiude un nodo e ci si ferma: il successivo lo sceglie l'utente. Altre sessioni possono lavorare nodi sbloccati in parallelo, e la copia condivisa si allinea con `atlas-sync`.
