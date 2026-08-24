## Atlas: il grafo comanda il lavoro

Il lavoro di questo progetto è un grafo di task in `.atlas/`. Un nodo è un pezzo di lavoro dimensionato su una sessione, gli archi `blockedBy` sono le dipendenze, e la **frontiera** è l'insieme dei nodi aperti i cui blocker sono tutti chiusi. Non si sceglie cosa fare leggendo una lista: si guarda la frontiera.

```sh
atlas how-to                     # questo contratto, i comandi, le mutazioni, le skill e i path
atlas status                     # frontiera, lucchetti, avanzamento
atlas next                       # la frontiera ordinata per impatto: un suggerimento
atlas take <ID>                  # rivendica e stampa il contesto insieme, prima di toccare qualsiasi cosa
atlas close <ID> -s "..."        # chiude, dopo aver scritto la Risposta nel ticket
atlas fog "una riga" --for <ID>  # appunta ciò che è emerso, indirizzato a un nodo se lo riguarda
```

`atlas brief <ID>` stampa lo stesso pacchetto di contesto di `take` (domanda, Risposte dei bloccanti, nebbia che lo nomina) senza rivendicare: utile per rileggerlo senza toccare il lucchetto.

Se arrivi qui senza sapere niente di Atlas, `atlas how-to` è il punto di ingresso: stampa questo contratto, l'elenco dei comandi, le mutazioni chiamabili da uno script, le skill installate e i path di questo progetto. È la stessa dottrina che stai leggendo, raggiungibile da un comando invece che da un file.

### Un nodo per sessione

Il claim è un lucchetto, non un promemoria: porta l'identità di chi rivendica (il PID di processo, o `ATLAS_IDENTITY` se impostata) e un battito che si rinnova ri-rivendicando lo stesso nodo. `claim`/`take` rifiutano se questa identità ne tiene già uno. Per lavorare su più nodi in parallelo con subagent che condividono lo stesso processo padre, ognuno imposta un'identità diversa tramite il flag `--identity` sui comandi che prendono il lucchetto (`claim`, `take`, `release`, `close`), oppure la variabile d'ambiente `ATLAS_IDENTITY`: altrimenti il tetto per sessione li conta come un solo attore. Il flag ha la precedenza sulla variabile, ed è quello che serve a un agente che lancia ogni comando da una shell nuova, perché lì un `export` non arriva alla chiamata dopo e il lucchetto tornerebbe a registrarsi sotto il PID del padre, cioè sotto la stessa identità dei suoi fratelli. Il rifiuto si scavalca con `--force`, che esiste per i casi imprevisti e non per la fretta.

Un lucchetto è orfano quando il processo che l'ha preso non esiste più, o fermo quando il battito non si aggiorna da troppo tempo. `atlas doctor` segnala entrambi i casi, insieme ai terminali che non confluiscono nel nodo finale e alle dashboard non aggiornate: eseguilo prima di dichiarare un grafo finito.

### HITL e AFK

Ogni nodo dichiara chi scrive la sua risposta.

| Gesto | Autonomia |
|---|---|
| claim, release, close | sì, è contabilità |
| lavorazione e risposta di un nodo **AFK** | sì, è il lavoro stesso del nodo |
| risposta di un nodo **HITL** | no, si scrive insieme all'umano: è il senso della sigla |
| creare nodi, cambiare `blockedBy`, mettere fuori scopo | mai in autonomia, e comunque solo con uno script |

Un agente che risponde da solo a un nodo HITL ha rotto la regola più importante di questo contratto.

### La forma del grafo si cambia solo con codice

`graph.json` non si edita a mano, e la CLI non ha comandi che creano nodi o archi. Ogni modifica strutturale è uno script Python in `.atlas/scripts/` che passa da `core/mutate.py`:

```sh
atlas new-script aggiunge-ramo-deploy
atlas exec .atlas/scripts/003-aggiunge-ramo-deploy.py
```

Lo script gira in una sola transazione e il grafo viene validato prima di essere scritto, quindi un ciclo o un arco verso un nodo inesistente lo fanno fallire senza toccare il file. Gli script restano versionati: sono la storia delle modifiche alla mappa.

Il ticket di un nodo non è una seconda copia del grafo. La sua testa (titolo, ramo, tipo, modo, bloccanti, domanda) discende da `graph.json` e viene riscritta a ogni rigenerazione, mentre Lavorazione e Risposta restano di chi le scrive. Il confine fra le due parti è il commento `<!-- /atlas:auto -->`. Uno script che cambia titolo, domanda o dipendenze non lascia quindi dietro di sé un markdown stantio, e non c'è niente da correggere a mano; se quel commento sparisce, il ticket smette di riallinearsi e `atlas doctor` lo segnala.

Quel che scopri lavorando un nodo e che meriterebbe un nodo suo va **proposto**, non creato: intanto si appunta con `atlas fog`. Per farne un nodo c'è un esempio pronto in `.atlas/scripts/000-promote-fog.py`: si compila con l'indice della voce e i campi del nodo, e si lancia con `atlas exec`.

### Quando un nodo è fatto

| Tipo | Fatto quando |
|---|---|
| `grilling` | la decisione è scritta e l'artefatto che produce esiste |
| `research` | la risposta cita fonti lette adesso, con link e data, non ricordate |
| `prototype` | l'artefatto si può guardare, e il ticket dice cosa si è imparato e cosa si è scartato |
| `task` | il lavoro è fatto e verificato, con la prova descritta nel ticket |

`close` verifica una cosa sola, che la sezione **Risposta** del ticket sia compilata. Il resto lo dichiara chi chiude. Che la risposta sia anche vera non lo può verificare nessuna macchina, e l'unica difesa è che la scriva chi ha fatto il lavoro mentre ce l'ha fresco.

C'è però un caso in cui `close` rifiuta e non dipende da cosa hai scritto: il nodo è cambiato da quando l'hai preso. Alla presa Atlas registra un'impronta del contenuto e alla chiusura la riverifica, perché fra i due momenti passa tutto il tempo del lavoro, e in quel tempo un altro agente o uno script di mutazione può aver cambiato la domanda, le dipendenze o l'ambito del nodo su cui stavi ragionando. La tua risposta entrerebbe pulita e poggerebbe su una premessa che non c'è più, senza che nessuno se ne accorga. Quando succede, rileggi il nodo con `atlas show <ID>` e decidi: richiudi se la tua risposta regge lo stesso, oppure aggiornala. `--force` chiude comunque, e va usato quando il cambiamento non tocca quello che hai scritto.

Sotto Risposta ci sono tre sotto-sezioni leggere e facoltative: **scelte non canoniche** (cosa hai deciso a tavolino, non dettato dal documento di design), **debito dichiarato** (cosa lasci volutamente incompleto, e perché) e **autorizzazioni ricevute** (se hai agito oltre l'ambito del nodo su indicazione esplicita dell'utente, cosa e quando). Un cancello di verifica le legge senza dover ricostruire la stessa archeologia da una prosa libera, e la terza rende verificabile un "come da tua richiesta" invece che solo asserito.

`close` accetta anche `-c/--costo` (un ordine di grandezza di quanto è costato, testo libero, niente di preciso) e `--artefatti` (i file prodotti, popolano il campo che il grafo già prevede). Senza `--artefatti`, in una repo git il campo si popola da solo con i file toccati da quando il nodo è stato rivendicato, esclusi quelli di `.atlas/`. La deduzione salta, e il campo rimane vuoto da dichiarare con `--artefatti` esplicito, in due casi: se al momento della chiusura c'è più di un nodo rivendicato, e se un altro nodo del grafo è stato chiuso o rilasciato mentre questo era in lavorazione, perché in quella finestra il lavoro dei due si sovrappone e git non sa dire di chi è ciascun file. Quando invece deduce, `close` stampa l'elenco dei file dedotti: guardalo, perché è l'unico momento in cui te ne accorgi senza andarlo a cercare. È quel campo che permette a `doctor` di accorgersi di una scrittura dentro l'ambito di un nodo già chiuso; per lasciarlo vuoto di proposito basta `--artefatti` senza argomenti.

Se in quell'elenco c'è roba che non è tua, o se il costo e la sintesi sono usciti sbagliati, la correzione è `atlas amend <ID> [--artefatti ...] [--costo ...] [--sintesi ...]`. Riscrive i soli campi che passi e lascia stare tutto il resto: il nodo resta chiuso, e l'istante della chiusura non si sposta, perché è da lì che `doctor` misura le scritture postume. La correzione resta scritta nel nodo con chi l'ha fatta e quando, così chi rilegge sa che quel campo è stato messo a mano e non dedotto. Un nodo ancora aperto non si corregge: lì la contabilità la scrive `close`. Se un cancello rilascia un nodo invece di chiuderlo, `-r/--ragione` su `release` registra il perché come evento in mappa, non solo come un ritorno silenzioso alla frontiera.

### Chi fa cosa, se serve

Un nodo può essere assegnato a una persona con `atlas assign <nome> <ID...>`, o a tutto un ramo con `--branch <ramo>`, che prende i nodi che quel ramo ha in quel momento: uno aggiunto dopo nasce senza assegnatario. Assegnare un ramo sovrascrive anche i nodi che erano già di qualcun altro, e il comando stampa gli id che ha cambiato. `atlas unassign <ID...>` toglie l'assegnazione, e `atlas whoami <nome>` ricorda chi lavora da questa copia del progetto, così `atlas assign --me <ID>` non richiede di riscrivere il nome. Il file `.atlas/whoami` non è versionato.

L'assegnazione non è il lucchetto e non lo sostituisce: dice di chi è quel pezzo di lavoro, mentre il `claim` dice chi ci ha le mani sopra adesso. Un nodo assegnato resta prendibile da chiunque, e assegnarlo mentre qualcuno lo sta lavorando non gli impedisce di chiuderlo. Se non le usi, il grafo si comporta esattamente come prima: nessun nodo nasce assegnato e la dashboard non mostra niente in più.

### Più grafi

Un grafo per epic, ciascuno isolato in `.atlas/graphs/<slug>/` con la sua mappa e la sua dashboard. `atlas new <nome>` antepone da solo la data di creazione al nome tecnico che dai (`<nome>` diventa `YYMMDD-<nome>`): lo slug vero è quello, non quello passato sulla riga di comando. Lo switch è a carico di chi lavora: `atlas use <slug>`, oppure `-g/--graph <slug>` sul singolo comando, che vale sia prima sia dopo il comando stesso. Lo slug non si scrive al posto del comando: `atlas <slug> render` non esiste.
