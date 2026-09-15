# Aree di memoria del grafo

> Grafo `260915-atlas-memory` · la verità sta in `graph.json`, questa mappa è la sua faccia leggibile.

## Destinazione

<!-- atlas:auto -->
Ogni grafo Atlas dichiara aree di memoria: documenti con una regola di scrittura (locked, append, edit) e un sigillo nel grafo, che take e brief stampano a ogni nodo e che close verifica. Le note di mappa sono un'area append. Contratto, README, skill e how-to in pari, suite, build ed e2e verdi, feature provata su questo stesso grafo.

## Note

Preferenze permanenti e skill da consultare a ogni sessione.

<!-- atlas:auto -->
- La fonte del disegno e' .atlas/graphs/260915-atlas-memory/notes/design.md: ogni nodo lo legge per intero prima di toccare il codice.
- Chi lavora un nodo non rigenera mai dist/atlas: lo fa solo Q01. Per provare l'e2e prima, copia la repo in una cartella temporanea e costruisci li'.
- Due nodi prendibili insieme non condividono un sorgente: gli archi della catena C e di S sono disegnati anche per questo. Prima di prendere un nodo guarda cosa dichiarano in artifacts quelli gia' rivendicati.
- I nodi vanno lavorati con Sonnet o piu': su un grafo precedente cinque nodi Haiku su sette hanno richiesto un secondo giro.

## Come si lavora un nodo

Si guarda la frontiera con `atlas status`, si rivendica un nodo con `atlas claim <ID>` prima di toccare qualsiasi cosa, si lavora, si scrive la sezione Risposta del suo ticket e si chiude con `atlas close <ID> -s "sintesi"`, che aggiunge da sé la riga qui sotto. Il contratto completo sta in `.atlas/CONTRACT.md`.

## Decisioni prese

Una riga per nodo chiuso, in ordine di chiusura: quanto basta per giudicarne la rilevanza, poi si apre il ticket.

<!-- atlas:auto -->
_niente, per ora._

## Non ancora specificato

Quel che è emerso e non ha ancora un nodo. Si appunta con `atlas fog "una riga"`.

<!-- atlas:auto -->
- una terza vista 'Memoria' nel pannello di destra della dashboard, con le aree e il loro sigillo
- filtro delle aree per tipo di nodo oltre che per ramo, se un grafo reale lo chiede
- un lucchetto sull'area edit durante la modifica, se due AFK finiscono davvero per pestarsi i piedi sul glossario
- atlas memory add da Telegram, per appuntare una decisione dal telefono

## Fuori scopo

Quel che sta oltre la destinazione, e il perché.

<!-- atlas:auto -->
_niente, per ora._
