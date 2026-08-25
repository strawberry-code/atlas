# Sincronizzazione fra macchine

> Grafo `260825-sync-distribuita` · la verità sta in `graph.json`, questa mappa è la sua faccia leggibile.

## Destinazione

<!-- atlas:auto -->
Due agenti su due macchine lavorano lo stesso grafo senza pestarsi: le chiusure si fondono da sole, un nodo preso su una macchina risulta preso sull'altra, e la dashboard mostra chi tiene cosa mentre lo tiene.

## Note

Preferenze permanenti e skill da consultare a ogni sessione.

<!-- atlas:auto -->
_niente, per ora._

## Come si lavora un nodo

Si guarda la frontiera con `atlas status`, si rivendica un nodo con `atlas claim <ID>` prima di toccare qualsiasi cosa, si lavora, si scrive la sezione Risposta del suo ticket e si chiude con `atlas close <ID> -s "sintesi"`, che aggiunge da sé la riga qui sotto. Il contratto completo sta in `.atlas/CONTRACT.md`.

## Decisioni prese

Una riga per nodo chiuso, in ordine di chiusura: quanto basta per giudicarne la rilevanza, poi si apre il ticket.

<!-- atlas:auto -->
_niente, per ora._

## Non ancora specificato

Quel che è emerso e non ha ancora un nodo. Si appunta con `atlas fog "una riga"`.

<!-- atlas:auto -->
- sotto --dry-run due messaggi dell'install sono al passato ('contratto appeso', 'aggiunte N righe') accanto a 'scriverebbe'
- manca una mutazione per rinominare o togliere un ramo: il ramo di default creato da create_graph si può solo riscrivere a mano

## Fuori scopo

Quel che sta oltre la destinazione, e il perché.

<!-- atlas:auto -->
_niente, per ora._
