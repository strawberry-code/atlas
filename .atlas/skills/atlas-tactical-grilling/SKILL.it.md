---
name: atlas-tactical-grilling
description: Griglia operativa in tre fasi su un task circoscritto, di solito di codice: prima l'agente accerta da solo quel che il codice già dice, poi porta all'utente un numero dichiarato di domande strutturate (default dodici), infine sintetizza le due cose in un piano da confermare. Usala sui nodi `grilling` di ambito ristretto e quando l'utente chiede di essere grigliato prima di una modifica.
---

# Grigliare un task circoscritto

Serve quando le scelte da chiudere sono poche, stanno dentro un codice che puoi leggere adesso, e la sessione deve finire con un piano eseguibile. Se invece la decisione è strutturale e ne vincola molte altre, la skill giusta è `atlas-strategic-grilling`, che non ha né fasi né budget e va avanti finché l'albero non è percorso.

Le fasi vanno in quest'ordine, e la seconda non comincia prima che la prima sia finita.

## Prima di cominciare: dichiara il budget

Le domande all'utente sono **dodici** di default. Prima di aprire la fase 2 annuncia quante ne farai, e aspetta: è lì che l'utente le cambia, dicendo "facciamone cinque" o "vai fino a venti". Su un task minuscolo proponi tu un numero più basso invece di riempire il conto.

Il budget è un tetto, non una quota. Se le domande vere finiscono a sei, si smette a sei: inventarne altre sei per arrivare a dodici è il modo più efficace di far perdere fiducia nel metodo. Se invece si esauriscono e restano scelte aperte, dillo e chiedi di allargarlo.

## Fase 1 — Ricognizione in autonomia

Prima di chiedere qualsiasi cosa, vai a vedere. Leggi il codice che il task tocca, i test che lo presidiano, le convenzioni già in vigore nei file vicini, i vincoli scritti (il `CLAUDE.md` del progetto, il contratto Atlas, le Risposte dei nodi bloccanti, le Note della mappa).

**Un fatto che sta nel codice non si chiede.** Chiedere all'utente come si chiama una funzione, se un test esiste o quale libreria è già in uso brucia una domanda del budget e dice che non hai guardato.

La fase finisce con due elenchi, che porti all'utente prima di aprire la successiva:

- **Accertato**: quel che hai trovato, in righe brevi, con il file e la riga. È la base su cui poggeranno le domande, e l'utente deve poterla correggere subito se hai letto male.
- **Aperto**: le decisioni che restano, ordinate mettendo per prime quelle che ne vincolano altre. Una risposta data presto taglia interi rami e ti restituisce budget.

## Fase 2 — Le domande

**Una domanda per chiamata.** `AskUserQuestion` ne accetta fino a quattro insieme, e qui non si usa così: la risposta a una cambia la successiva, e quattro risposte date in blocco sono quattro risposte non pensate.

Ogni domanda ha quattro pezzi, in quest'ordine:

1. **Contesto**: cosa hai visto che genera la domanda. Una o due righe, concrete, col file se serve.
2. **Ragionamento**: perché la scelta non è ovvia e cosa cambia a valle a seconda di come va.
3. **La domanda**, esplicita.
4. **La raccomandazione**: cosa faresti tu e perché. Non è una gentilezza ma la parte che rende veloce la risposta, perché correggere una proposta costa molto meno che riempire un foglio bianco.

Come atterrano nei campi:

- `question` porta tutti e quattro i pezzi. Non lasciare il contesto nel testo di chat prima della chiamata: nello storico resta la domanda nuda, e l'utente rilegge una cosa che non si capisce più.
- `header` è l'oggetto della scelta in dodici caratteri, non la domanda accorciata.
- Le opzioni portano nella `description` la conseguenza di sceglierle, non la parafrasi della label. La raccomandata sta per prima, con `(consigliato)` in fondo alla label.

**La forma normale è sì o no**, due opzioni, perché con la raccomandazione già scritta all'utente resta da confermarla o rifiutarla. La risposta multipla si usa solo quando la scelta è davvero fra alternative diverse, e allora vale una regola che non si negozia: **ogni opzione dev'essere praticabile.** Nessuna opzione messa lì per far numero, nessuna scritta male apposta perché vinca quella che consigli. Se non riesci a scrivere la terza opzione in modo da poterla difendere, vuol dire che le opzioni sono due.

Mentre vai:

- Se una risposta rende inutili domande che avevi in coda, cancellale e dillo, invece di farle lo stesso.
- Se una risposta ne apre una che non avevi previsto, mettila in coda e di' che il conto è cambiato.
- Se ti accorgi che una domanda avresti potuto risolverla leggendo il codice, non farla: torna un attimo alla fase 1.
- Non rispondere al posto dell'utente. Il silenzio non è un assenso, e "procedo con la raccomandata se non dici niente" non è una risposta ricevuta.

## Fase 3 — La sintesi

Rimetti insieme le due metà, quel che hai accertato da solo nella fase 1 e quel che l'utente ha deciso nella fase 2, in un piano solo: cosa si fa, in che ordine, e cosa si è scelto di non fare. Ogni decisione presa dall'utente si cita insieme alla domanda a cui rispondeva, così chi legge distingue quel che è stato deciso da quel che hai dedotto tu dal codice.

**Non eseguire prima che l'utente confermi la sintesi.** Le risposte alle singole domande non sono l'accordo sul piano: l'accordo lo dichiara l'utente, sul piano intero, una volta sola.

In un nodo Atlas: gli elenchi della fase 1 e le alternative scartate nella fase 2 vanno in **Lavorazione**, il piano confermato in **Risposta**, e quel che hai deciso a tavolino senza chiederlo va sotto **Scelte non canoniche**. Se durante la griglia emerge qualcosa che meriterebbe un nodo suo, non crearlo: appuntalo con `atlas fog "..." --for <ID>` e proponilo a fine nodo.
