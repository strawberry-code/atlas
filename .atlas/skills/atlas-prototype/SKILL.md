---
name: atlas-prototype
description: Costruisce un prototipo usa e getta per rispondere alla domanda di un nodo `prototype`: una TUI minima per sentire se un modello di stato regge, oppure varianti di interfaccia da guardare una accanto all'altra. Usala sui nodi `prototype` del grafo e quando l'utente vuole reagire a qualcosa di concreto invece che a una descrizione.
---

# Prototipare per rispondere a un nodo

Un prototipo è **codice usa e getta che risponde a una domanda**. La domanda decide la forma, e in un nodo Atlas è già scritta: è quella che `atlas take <ID>` ti ha stampato. Se il prototipo risponde a un'altra domanda è sprecato, per quanto sia bello.

Il nodo `prototype` è HITL. L'artefatto serve ad alzare la risoluzione della conversazione, non a sostituirla: si costruisce, si mette davanti all'utente, si ascolta la reazione.

## Scegli il ramo

- **"Questa logica, questo modello di stato, regge?"** → il ramo *logica*: una TUI minuscola che spinge la macchina a stati dentro i casi difficili da ragionare sulla carta.
- **"Che aspetto deve avere?"** → il ramo *interfaccia*: più varianti radicalmente diverse sulla stessa rotta, commutabili al volo.

Sbagliare ramo butta via l'intero prototipo. Se la domanda del nodo è ambigua e l'utente non è raggiungibile, scegli in base al codice attorno (un modulo di backend porta alla logica, una pagina o un componente all'interfaccia) e dichiara l'assunzione in **Lavorazione**.

### Ramo logica

Isola quel che risponde alla domanda dietro un'interfaccia piccola e pura, che si possa sollevare e lasciar cadere nel codice vero: un riduttore `(stato, azione) -> stato`, una macchina a stati esplicita, un pugno di funzioni pure. Niente I/O e niente terminale lì dentro. La TUI attorno è usa e getta, il modulo no, e questo è quel che rende il prototipo utile oltre la propria vita.

La TUI ridisegna il fotogramma intero a ogni azione invece di accodare righe: prima lo stato corrente, un campo per riga, poi i tasti disponibili in fondo. L'utente deve vedere una schermata sola e stabile, non uno scrollback che cresce.

### Ramo interfaccia

Tre varianti di default, cinque al massimo: oltre smettono di essere diverse e diventano rumore. Montale **dentro una pagina che esiste già**, commutandole con un parametro nell'URL, e tieni i dati, i permessi e la densità veri. Una rotta nuova e vuota è un vuoto pneumatico dove ogni variante sembra accettabile, e nasconde proprio i problemi che una pagina popolata farebbe saltare fuori. Solo se davvero non c'è una pagina che la possa ospitare, crea una rotta usa e getta seguendo le convenzioni di routing già in uso, col nome che dice a chiunque che è un prototipo.

## Le regole che valgono per entrambi

1. **Usa e getta dal primo giorno, e marcato come tale.** Mettilo vicino a dove il codice vero andrà, così il contesto è ovvio, ma chiamalo in modo che nessuno lo scambi per produzione.
2. **Un comando per lanciarlo**, quello che il progetto già usa. L'utente deve poterlo avviare senza pensarci.
3. **Niente persistenza.** Lo stato vive in memoria: la persistenza è quel che il prototipo sta verificando, non qualcosa su cui deve appoggiarsi.
4. **Niente rifiniture.** Nessun test, nessuna astrazione, nessuna gestione degli errori oltre a quella che serve per farlo partire.
5. **Mostra lo stato.** Dopo ogni azione, o a ogni cambio di variante, rendi visibile tutto quel che è cambiato.

## Come si chiude il nodo

Il contratto dice che un nodo `prototype` è fatto quando **l'artefatto si può guardare** e il ticket dice **cosa si è imparato e cosa si è scartato**. Le due cose devono valere insieme, perché un prototipo consegnato senza verdetto lascia al prossimo lo stesso dubbio di prima.

In **Lavorazione** annota le varianti scartate e il perché. In **Risposta** scrivi la decisione che il prototipo ha permesso di prendere, non la cronaca di come l'hai costruito. Alla chiusura dichiara i file:

```sh
atlas close <ID> -s "la variante B regge, le altre due no" --artefatti prototipi/settings-varianti.tsx
```

La decisione validata entra nel codice vero con un lavoro suo, che non è questo nodo. Il prototipo resta dov'è, dichiarato fra gli artefatti; se sporca il ramo principale, spostalo su un ramo usa e getta e cita quello nella Risposta.
