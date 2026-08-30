# Atlas Interactions

> Grafo `260830-atlas-interactions` · la verità sta in `graph.json`, questa mappa è la sua faccia leggibile.

## Destinazione

<!-- atlas:auto -->
Interazioni Atlas a basso attrito: pannello Notifiche, avvisi locali, email Himalaya e Telegram con relay OCI, risposta valida e ripresa Automata senza polling.

## Note

Preferenze permanenti e skill da consultare a ogni sessione.

<!-- atlas:auto -->
- Issue #30. Tutti i nodi sono AFK e non specificano model: Automata usa Codex Luna di default.
- Il deploy Telegram richiede un bot, hostname e segreti OCI già approvati nel suo ambiente; il grafo li verifica ma non li crea né li espone.

## Come si lavora un nodo

Si guarda la frontiera con `atlas status`, si rivendica un nodo con `atlas claim <ID>` prima di toccare qualsiasi cosa, si lavora, si scrive la sezione Risposta del suo ticket e si chiude con `atlas close <ID> -s "sintesi"`, che aggiunge da sé la riga qui sotto. Il contratto completo sta in `.atlas/CONTRACT.md`.

## Decisioni prese

Una riga per nodo chiuso, in ordine di chiusura: quanto basta per giudicarne la rilevanza, poi si apre il ticket.

<!-- atlas:auto -->
_niente, per ora._

## Non ancora specificato

Quel che è emerso e non ha ancora un nodo. Si appunta con `atlas fog "una riga"`.

<!-- atlas:auto -->
_niente, per ora._

## Fuori scopo

Quel che sta oltre la destinazione, e il perché.

<!-- atlas:auto -->
_niente, per ora._
