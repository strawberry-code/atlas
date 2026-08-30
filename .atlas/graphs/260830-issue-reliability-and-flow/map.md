# Affidabilita e coordinamento di Atlas

> Grafo `260830-issue-reliability-and-flow` · la verità sta in `graph.json`, questa mappa è la sua faccia leggibile.

## Destinazione

<!-- atlas:auto -->
Tutte le issue GitHub da #22 a #28 sono implementate, verificate e documentate; gli artefatti, i lock e il coordinamento multi-agente sono affidabili.

## Note

Preferenze permanenti e skill da consultare a ogni sessione.

<!-- atlas:auto -->
- Tutti i nodi sono AFK e dimensionati per un solo agente Luna 5.6. I rami possono procedere in parallelo quando la frontiera lo consente; ogni ramo confluisce in END.

## Come si lavora un nodo

Si guarda la frontiera con `atlas status`, si rivendica un nodo con `atlas claim <ID>` prima di toccare qualsiasi cosa, si lavora, si scrive la sezione Risposta del suo ticket e si chiude con `atlas close <ID> -s "sintesi"`, che aggiunge da sé la riga qui sotto. Il contratto completo sta in `.atlas/CONTRACT.md`.

## Decisioni prese

Una riga per nodo chiuso, in ordine di chiusura: quanto basta per giudicarne la rilevanza, poi si apre il ticket.

<!-- atlas:auto -->
- **A01** Doctor verifica presenza e tracciamento degli artefatti rilasciato: ripristino del claim orfano lasciato dall’esecuzione interrotta · [ticket](tickets/A01.md)
- **A01** Doctor verifica presenza e tracciamento degli artefatti: Doctor segnala artefatti mancanti e non tracciati, con regressioni dedicate e controlli sulle scritture postume preservati. · [ticket](tickets/A01.md)
- **A02** Close avvisa sugli artefatti non tracciati: Close avvisa sugli artefatti presenti ma non tracciati da Git e prosegue la chiusura · [ticket](tickets/A02.md)
- **B01** Close richiede una scelta quando la deduzione salta: close ora richiede artefatti espliciti quando la deduzione non è attendibile; deduzione sicura e test aggiornati · [ticket](tickets/B01.md)
- **C01** Definisci una raccolta non ambigua per --artefatti: Raccolta CLI ripetibile per tutti i path --artefatti in close e amend, con lista vuota intenzionale · [ticket](tickets/C01.md)
- **C02** Rifiuta artefatti malformati prima di salvarli: Artefatti ambigui rifiutati, path mancanti segnalati alla chiusura e quattro regressioni coperte. · [ticket](tickets/C02.md)
- **B02** Contratto e messaggi rendono visibile la mancata deduzione: Contratto, how-to e messaggi rendono esplicito il rifiuto della chiusura quando la deduzione salta; test di output verificati · [ticket](tickets/B02.md)
- **D01** Doctor degrada gli OSError a diagnosi: Doctor tratta ogni OSError durante l'ispezione di un artifact, incluso ENAMETOOLONG, come avviso diagnostico con nodo, path ed errore; continua l'ispezione degli altri artifact e i controlli successivi. Aggiunta regressione che verifica entrambe le proprietà. · [ticket](tickets/D01.md)
- **E01** Lock remoto risolve il nome del remote nel repository del progetto: Risolto lock.remote dal nome del remote all'URL Git nel checkout del progetto prima di creare il trasporto; gli URL passano direttamente. Configurazione non risolvibile ed errore di rete restano distinti, con contratto e test aggiornati. · [ticket](tickets/E01.md)
- **F01** Registra le domande con assunzione nel grafo: Ledger questions validato, mutazioni ask/answer e rifiuto dei nodi HITL implementati e verificati. · [ticket](tickets/F01.md)
- **F02** Espone ask, asks e answer nella CLI: CLI ask, asks e answer completata e verificata · [ticket](tickets/F02.md)
- **F03** Calcola l'impatto di una risposta divergente: Calcolo dell'impatto delle risposte divergenti implementato e verificato · [ticket](tickets/F03.md)
- **F04** Rende le domande visibili e governate rilasciato: claim orfano della sessione precedente · [ticket](tickets/F04.md)
- **F04** Rende le domande visibili e governate: Domande aperte visibili in dashboard e doctor, con marcatura dopo 24 ore e distinzione AFK/HITL · [ticket](tickets/F04.md)
- **G01** Configura i segnali osservati per drift rilasciato: claim orfano preesistente · [ticket](tickets/G01.md)
- **G01** Configura i segnali osservati per drift: Configurazione dei collettori e raccolta temporale degli artefatti condivisi implementate e verificate · [ticket](tickets/G01.md)
- **G02** Drift deduce soltanto archi mancanti plausibili: Implementata la diagnosi transitiva degli archi mancanti: segnala solo nodi chiusi successivamente che condividono artefatti senza una dipendenza diretta o transitiva; conserva gli artefatti come evidenza e non diagnostica archi spurii. · [ticket](tickets/G02.md)
- **G03** Espone atlas drift come diagnosi leggibile: Esposta diagnosi drift in sola lettura con rimedio umano · [ticket](tickets/G03.md)
- **END** Verifica finale e chiusura delle issue: Verifica finale completata: suite, doctor, validate, verifiche manuali e confronto requisiti #22-#28 registrati nella Risposta di END.md. Issue #22-#28 chiuse con evidenza. Limiti preesistenti e claim orfano documentati; nessun commit, push o agente aggiuntivo. · [ticket](tickets/END.md)

## Non ancora specificato

Quel che è emerso e non ha ancora un nodo. Si appunta con `atlas fog "una riga"`.

<!-- atlas:auto -->
_niente, per ora._

## Fuori scopo

Quel che sta oltre la destinazione, e il perché.

<!-- atlas:auto -->
_niente, per ora._
