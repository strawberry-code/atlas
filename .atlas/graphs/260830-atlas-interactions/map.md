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
- **A01** Verifica i prerequisiti del relay: Prerequisiti Telegram e HTTPS mancanti; credenziali OCI locali presenti senza esposizione di segreti. · [ticket](tickets/A01.md)
- **A02** Definisci il contratto UX e delle Interazioni: Contratto Interaction definito: tre eventi, quattro stati, capability dichiarate e card senza dettagli di trasporto. · [ticket](tickets/A02.md)
- **A03** Implementa ledger e schema Interaction: Ledger Interaction atomico e idempotente nel graph.json, con audit, contesto e scadenza. · [ticket](tickets/A03.md)
- **A04** Implementa lifecycle e risposta validata rilasciato: run Automata del 2026-08-30 interrotto: il nodo non fu mai lavorato · [ticket](tickets/A04.md)
- **A04** Implementa lifecycle e risposta validata: Lifecycle Interaction transazionale, risposta validata e audit completo implementati · [ticket](tickets/A04.md)
- **A05** Collega Automata alle Interazioni: Interazioni Automata e risveglio event-driven · [ticket](tickets/A05.md)

## Non ancora specificato

Quel che è emerso e non ha ancora un nodo. Si appunta con `atlas fog "una riga"`.

<!-- atlas:auto -->
_niente, per ora._

## Fuori scopo

Quel che sta oltre la destinazione, e il perché.

<!-- atlas:auto -->
_niente, per ora._
