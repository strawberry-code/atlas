# Atlas Automata

> Grafo `260830-atlas-automata` · la verità sta in `graph.json`, questa mappa è la sua faccia leggibile.

## Destinazione

<!-- atlas:auto -->
Atlas Automata sostituisce l'orchestratore LLM con un runner meccanico, configurabile per esecuzione, robusto al fallimento e pronto a usare Codex Luna, Claude, Gemini, Terra e futuri adapter.

## Note

Preferenze permanenti e skill da consultare a ogni sessione.

<!-- atlas:auto -->
- Issue GitHub unica: #29. Tutti i nodi sono AFK e destinati a un solo agente Luna per sessione. Il parallelismo non è una proprietà del grafo: Automata lo richiede esplicitamente a ogni avvio. Il campo modello dei nodi resta vuoto salvo richiesta dell'autore; il runner usa Codex Luna e ricade su Claude Sonnet se Luna non è disponibile. Ogni adapter deve eseguire fuori sandbox con bypass dei permessi. Il grafo è seriale per questa orchestrazione: non avviare più nodi contemporaneamente durante la sua esecuzione.

## Come si lavora un nodo

Si guarda la frontiera con `atlas status`, si rivendica un nodo con `atlas claim <ID>` prima di toccare qualsiasi cosa, si lavora, si scrive la sezione Risposta del suo ticket e si chiude con `atlas close <ID> -s "sintesi"`, che aggiunge da sé la riga qui sotto. Il contratto completo sta in `.atlas/CONTRACT.md`.

## Decisioni prese

Una riga per nodo chiuso, in ordine di chiusura: quanto basta per giudicarne la rilevanza, poi si apre il ticket.

<!-- atlas:auto -->
- **A01** Contratto di Atlas Automata: Contratto pubblico definito e presidiato: Automata meccanico, AFK, guidato dalla frontiera Atlas, con parallelism obbligatorio per run, adapter estensibili e terminazione valida. · [ticket](tickets/A01.md)
- **A02** Campo modello opzionale nei nodi rilasciato: lucchetto orfano rilevato prima della sessione Luna · [ticket](tickets/A02.md)
- **A02** Campo modello opzionale nei nodi rilasciato: riallineamento esplicito dell’identità della sessione · [ticket](tickets/A02.md)
- **A02** Campo modello opzionale nei nodi: Campo model opzionale implementato con serializzazione condizionale, validazione, compatibilità dei grafi esistenti e rendering nella scheda dashboard. · [ticket](tickets/A02.md)
- **B01** Avvio con parallelismo esplicito: Entry point Automata con parallelism obbligatorio per run, validazione positiva e modalità 1 seriale · [ticket](tickets/B01.md)
- **B02** Runner guidato dalla frontiera Atlas rilasciato: claim orfano rilevato prima della sessione Luna · [ticket](tickets/B02.md)
- **B02** Runner guidato dalla frontiera Atlas: Runner seriale guidato dalla frontiera Atlas implementato e verificato; parallelismo effettivo, adapter, retry e resume restano ai nodi successivi. · [ticket](tickets/B02.md)
- **B03** Serialità e parallelismo limitato: Controllo bounded del runner completato: parallelism=1 seriale, valori maggiori entro il limite, claim Atlas protetti e rilettura della frontiera dopo ogni chiusura. · [ticket](tickets/B03.md)
- **B04** Eventi di chiusura e aggiornamento della frontiera: Eventi di chiusura event-driven con riconciliazione atomica Atlas, deduplica, resume idempotente nello stesso Run e nessun doppio avvio. · [ticket](tickets/B04.md)
- **C01** Registry degli adapter modello: Registry provider-agnostic e interfaccia AFK implementati e verificati; selezione modello, default, fallback e retry restano fuori ambito. · [ticket](tickets/C01.md)
- **C02** Selezione del modello e default Luna: Selezione modello collegata al registry con default Codex Luna, rifiuto diagnostico e log deterministico. · [ticket](tickets/C02.md)
- **C03** Fallback a Claude Sonnet: Fallback singolo a Claude Sonnet per default Luna indisponibile, con distinzione degli esiti e log delle transizioni · [ticket](tickets/C03.md)
- **C04** Retry progressivo e classificazione dei guasti: Retry bounded con classificazione dei guasti, backoff persistente e riconciliazione dei claim implementato e verificato · [ticket](tickets/C04.md)
- **D01** Lancio AFK fuori sandbox: Lancio provider AFK fuori sandbox con argv sicura, ambiente Atlas minimo e contratto del processo figlio documentato · [ticket](tickets/D01.md)
- **D02** Stato, log e diagnostica del run: Ledger persistente, eventi osservabili e diagnostica CLI del run implementati e verificati; resume completo escluso. · [ticket](tickets/D02.md)
- **D03** Resume e idempotenza dopo interruzione: Resume persistente e idempotente dopo interruzione: riconcilia claim, retry e chiusure Atlas senza rilanci duplicati · [ticket](tickets/D03.md)
- **E01** Suite di test del runner meccanico: Suite Automata deterministica completata: coperti contratto, scheduling bounded, eventi, modelli, fallback, guasti, retry, resume, idempotenza e terminazione ambigua. · [ticket](tickets/E01.md)
- **E02** CLI, contratto e documentazione future-proof rilasciato: lock orfano di sessione terminata, rilevato prima della sessione Luna · [ticket](tickets/E02.md)
- **E02** CLI, contratto e documentazione future-proof: CLI, contratto, template e README Automata allineati e verificati · [ticket](tickets/E02.md)
- **END** Collaudo finale e chiusura dell'enhancement: Collaudo finale Automata completato e issue #29 verificata · [ticket](tickets/END.md)

## Non ancora specificato

Quel che è emerso e non ha ancora un nodo. Si appunta con `atlas fog "una riga"`.

<!-- atlas:auto -->
_niente, per ora._

## Fuori scopo

Quel che sta oltre la destinazione, e il perché.

<!-- atlas:auto -->
_niente, per ora._
