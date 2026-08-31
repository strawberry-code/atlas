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

`atlas serve` tiene la dashboard viva su `http://127.0.0.1`, la rigenera quando `graph.json` cambia e spinge il reload al browser già aperto; con `lock.remote` attivo mostra anche i lucchetti delle altre macchine.

Automata conserva l'ultima esecuzione in `run-state.json` accanto a `graph.json`. `atlas run-status` mostra se il run è attivo, in attesa, fallito, bloccato o completato, insieme a nodo, provider, tentativo, retry, frontiera e blocker residui. `atlas run-log` stampa la cronologia persistente di claim, provider, fallback, attese, backoff, chiusure e aggiornamenti della frontiera; `--tail N` limita l'uscita. Il ledger descrive ciò che è accaduto, ma non conserva processi e non autorizza il resume di un agente dopo un'interruzione.

### Run Automata

Ogni run parte con `atlas run --parallelism N`. Il valore è obbligatorio per quel run, `1` significa esecuzione strettamente seriale e un valore maggiore significa parallelismo limitato. È una configurazione runtime e non viene mai scritta nel grafo. Il comando configura e valida il run; le decisioni di scheduling e terminazione restano del runner guidato da Atlas.

Il campo `model` del nodo è opzionale e resta assente o vuoto salvo indicazione dell'autore del grafo. Vuoto seleziona Codex Luna (`codex-luna`). Un valore esplicito deve corrispondere esattamente a un'identità di adapter registrata. Se il provider Luna di default non è disponibile, Automata registra un solo fallback a Claude Sonnet (`claude`); un modello esplicito non viene mai sostituito in silenzio. Gemini e Code Terra sono identità aggiuntive supportate.

Il runner rivendica il nodo per conto del provider che sta per lanciare: il lucchetto porta l'identità di quell'agente, quindi l'agente lanciato riceve un nodo già suo, non deve fare `atlas take` e chiude con `atlas close`. Un agente che termina senza chiudere il nodo vale come terminazione ambigua di quel nodo: viene ritentato con un tetto stretto e, se non chiude, il run prosegue sui rami che non dipendono da lui invece di fermarsi.

Ogni provider lanciato da Automata è AFK, viene eseguito fuori sandbox e usa il bypass dei permessi. Per aggiungere un provider, implementa `AgentAdapter` oppure configura `SubprocessAdapter`, registralo in `AdapterRegistry` e passa il registry a `launcher_from_registry`. Il runner non cambia. Un adapter di processo deve usare una argv validata, stdin chiuso e i flag non interattivi del provider.

Usa `atlas run-status` per leggere lo stato corrente e il motivo. Usa `atlas run-log` oppure `atlas run-log --tail N` per esaminare selezione del modello, fallback, claim, guasti, backoff, chiusure e aggiornamenti della frontiera. Timeout, crash, rate limit, provider non disponibile e terminazione ambigua sono ritentabili; gli errori permanenti no. La policy di retry predefinita cresce da un minuto fino a un'ora ed è bounded. Un claim vivo impedisce un lancio duplicato; questa versione non riprende il processo provider dopo un'interruzione.

Se arrivi qui senza sapere niente di Atlas, `atlas how-to` è il punto di ingresso: stampa questo contratto, l'elenco dei comandi, le mutazioni chiamabili da uno script, le skill installate e i path di questo progetto. È la stessa dottrina che stai leggendo, raggiungibile da un comando invece che da un file.

### Se Atlas ti ostacola, dillo

Atlas è un progetto aperto e chi lo usa di più sono gli agenti come te. Quando qualcosa qui dentro ti rallenta, un comando che non fa quel che promette, un messaggio che non si capisce, un gesto che manca, apri una issue su [github.com/strawberry-code/atlas/issues](https://github.com/strawberry-code/atlas/issues) invece di aggirare il problema in silenzio.

Tre momenti in cui vale la pena fermarsi a chiederselo. Appena incontri il problema, finché hai in mano il comando che l'ha prodotto. Quando chiudi un nodo e guardi indietro al giro appena fatto. A fine sessione, prima di lasciare il grafo. Conta anche l'attrito che non arriva a essere un difetto. Una proposta di miglioramento serve quanto la segnalazione di un guasto. Nella issue metti la versione (`atlas how-to` la stampa in testa), il comando esatto e cosa ti aspettavi.

### Un nodo per sessione

Il claim è un lucchetto, non un promemoria: porta l'identità di chi rivendica (il PID di processo, o `ATLAS_IDENTITY` se impostata) e un battito che si rinnova ri-rivendicando lo stesso nodo. `claim`/`take` rifiutano se questa identità ne tiene già uno. Per lavorare su più nodi in parallelo con subagent che condividono lo stesso processo padre, ognuno imposta un'identità diversa tramite il flag `--identity` sui comandi che prendono il lucchetto (`claim`, `take`, `release`, `close`), oppure la variabile d'ambiente `ATLAS_IDENTITY`: altrimenti il tetto per sessione li conta come un solo attore. Il flag ha la precedenza sulla variabile, ed è quello che serve a un agente che lancia ogni comando da una shell nuova, perché lì un `export` non arriva alla chiamata dopo e il lucchetto tornerebbe a registrarsi sotto il PID del padre, cioè sotto la stessa identità dei suoi fratelli. Il rifiuto si scavalca con `--force`, che esiste per i casi imprevisti e non per la fretta.

Un lucchetto è orfano quando il processo che l'ha preso non esiste più, o fermo quando il battito non si aggiorna da troppo tempo. `atlas doctor` segnala entrambi i casi, insieme ai terminali che non confluiscono nel nodo finale e alle dashboard non aggiornate: eseguilo prima di dichiarare un grafo finito. Con `lock.remote` attivo riferisce anche lo stato del lucchetto remoto, attivo e raggiungibile, irraggiungibile o dichiarato ma non iniettato, senza mai morire.

**Un claim può venire da un'altra macchina.** Quando due macchine lavorano sullo stesso grafo, la liveness di un claim remoto non si può verificare col PID locale: un claim è vivo finché il suo `lease_until` non scade, e porta `host` e `lease_until`. Il TTL di default è 3600 secondi, `lease_ttl_seconds` in `config.json`. Il battito dei claim nostri si rinnova da solo: a ogni comando che carica il grafo, se manca meno di metà del TTL alla scadenza, il lease si allunga. Un comando per TTL tiene viva la presa, e una raffica non riscrive il file. Il lucchetto remoto è un'opzione: con `lock.remote` in `config.json` (un remote git, per esempio `origin`) Atlas coordina la presa su ref git condivise prima di toccare un nodo, e un nodo che stai lavorando resta intoccabile dalle altre macchine finché il lease è fresco. Senza `lock.remote` il comportamento è identico a prima, tutto locale. Senza rete il lucchetto degrada in lettura e chiude in mutazione: `status`, `next`, `show` e `brief` mostrano lo stato locale con l'avviso "remote non raggiungibile", mentre `take` su un nodo libero, `close` e `release` rifiutano di scrivere, perché senza la ref non si può escludere che un'altra macchina tenga il nodo. `take` sul proprio nodo degrada: avvisa e non allunga il lease. `close --force` salta la consulta remota, e la deduzione degli artefatti salta con l'avviso dedicato. Quando il lucchetto remoto è attivo, la finestra condivisa della deduzione degli artefatti vede anche le ref remote prese da altre macchine durante la lavorazione.

Con `lock.remote` il nome del remote viene risolto nella copia Git del progetto prima di creare il trasporto nel repository di servizio; un URL configurato viene usato direttamente. Un nome inesistente è una configurazione non risolvibile e lascia il lucchetto spento, mentre un URL non raggiungibile è un errore di rete del trasporto.

### HITL e AFK

Ogni nodo dichiara chi scrive la sua risposta.

| Gesto | Autonomia |
|---|---|
| claim, release, close | sì, è contabilità |
| lavorazione e risposta di un nodo **AFK** | sì, è il lavoro stesso del nodo |
| risposta di un nodo **HITL** | no, si scrive insieme all'umano: è il senso della sigla |
| creare nodi, cambiare `blockedBy`, mettere fuori scopo | mai in autonomia, e comunque solo con uno script |

`atlas ask` registra nel ledger una domanda non bloccante e l'assunzione con cui un nodo AFK può proseguire. Non è una decisione HITL e non la sostituisce: su un nodo HITL `ask` viene rifiutato e la decisione resta da scrivere insieme all'umano. `atlas render` mostra le domande aperte nella dashboard; dopo 24 ore dall'istante `askedAt` le marca come invecchiate. `atlas doctor` segnala le domande aperte invecchiate, che vanno risposte o riesaminate con `atlas answer`.

`atlas drift` propone diagnosi leggibili per archi mancanti plausibili, mostrando i nodi e gli artefatti condivisi. È una diagnosi in sola lettura: non modifica il grafo e non aggiunge archi automaticamente. Se il segnale è corretto, un umano lo trasforma in un arco dichiarato in uno script con `mutate.link(g, "NODO_SUCCESSIVO", blocked_by="NODO_PRECEDENTE")`, poi esegue `atlas exec`.

Un agente che risponde da solo a un nodo HITL ha rotto la regola più importante di questo contratto.

### La forma del grafo si cambia solo con codice

`graph.json` non si edita a mano, e la CLI non ha comandi che creano nodi o archi. Ogni modifica strutturale è uno script Python in `.atlas/scripts/` che passa da `core/mutate.py`:

```sh
atlas new-script aggiunge-ramo-deploy
atlas exec .atlas/scripts/003-aggiunge-ramo-deploy.py
```

Lo script gira in una sola transazione e il grafo viene validato prima di essere scritto, quindi un ciclo o un arco verso un nodo inesistente lo fanno fallire senza toccare il file. Gli script restano versionati: sono la storia delle modifiche alla mappa.

Quando il grafo è condiviso e le storie divergono, la base è quella già pubblicata: il proprio lavoro si riapplica sopra con script rinumerati in coda, mai fondendo `graph.json` a mano, perché un merge manuale staccherebbe la mappa dalla sequenza di script che l'ha prodotta. Il merge di git è un'altra cosa e lo fa il driver, come descritto poco più sotto. `atlas renumber` rimette gli script in ordine, compattando la numerazione senza argomenti o spostando in coda i file che gli passi, nell'ordine indicato; `--dry-run` mostra le rinomine senza farle. Le chiusure già avvenute su un'altra copia si riportano con `mutate.restore_closure`, che le ricrea coi metadati originali. Non è un modo per chiudere un nodo: quello resta `atlas close`, che verifica il lucchetto e la Risposta scritta nel ticket. Serve invece a riapplicare il proprio lavoro sopra un grafo arrivato da altri. Il ciclo completo, pull, merge lasciato al driver, risoluzione degli eventuali conflitti, rinumerazione e push, è descritto per esteso nella skill `atlas-sync`.

Quando un merge di git tocca davvero `graph.json`, se ne occupa il driver di merge che Atlas registra all'installazione (una riga in `.gitattributes` e una sezione nel config git locale): fonde per id di nodo invece che per riga, scrive sempre JSON valido e non lascia mai marker di git nel file. Se i due rami hanno cambiato lo stesso nodo in modi inconciliabili, esce in conflitto, annota quel che non ha saputo fondere in un campo `conflicts` dentro il grafo e lascia la decisione a te: `atlas conflicts` elenca le voci, `atlas conflicts --resolve` le dichiara risolte una volta che hai corretto `graph.json` a mano. Il driver arriva da solo ai progetti già installati al primo `atlas update`; per disattivarlo, togli la riga da `.gitattributes` e la sezione dal config git.

Il ticket di un nodo non è una seconda copia del grafo. La sua testa (titolo, ramo, tipo, modo, bloccanti, domanda) discende da `graph.json` e viene riscritta a ogni rigenerazione, mentre Lavorazione e Risposta restano di chi le scrive. Il confine fra le due parti è il commento `<!-- /atlas:auto -->`. Uno script che cambia titolo, domanda o dipendenze non lascia quindi dietro di sé un markdown stantio, e non c'è niente da correggere a mano; se quel commento sparisce, il ticket smette di riallinearsi e `atlas doctor` lo segnala.

Quel che scopri lavorando un nodo e che meriterebbe un nodo suo va **proposto**, non creato: intanto si appunta con `atlas fog`. Per farne un nodo c'è un esempio pronto in `.atlas/scripts/000-promote-fog.py`: si compila con l'indice della voce e i campi del nodo, e si lancia con `atlas exec`.

### Quando un nodo è fatto

| Tipo | Fatto quando |
|---|---|
| `grilling` | la decisione è scritta e l'artefatto che produce esiste |
| `research` | la risposta cita fonti lette adesso, con link e data, non ricordate |
| `prototype` | l'artefatto si può guardare, e il ticket dice cosa si è imparato e cosa si è scartato |
| `task` | il lavoro è fatto e verificato, con la prova descritta nel ticket |

Quella tabella dice quando un nodo è finito, non come lo si lavora. Il *come* sta nelle skill installate nel progetto, una per tipo. Un nodo `grilling` ne ha due, perché due sono i modi di grigliare: `atlas-strategic-grilling` quando la decisione è strutturale o irreversibile, senza budget, finché l'albero del disegno non è percorso; `atlas-tactical-grilling` quando l'ambito è ristretto, in tre fasi, prima la ricognizione dell'agente sul codice, poi un numero dichiarato di domande all'utente, infine la sintesi da confermare. Un nodo `research` passa da `atlas-research`, un `prototype` da `atlas-prototype`, e il linguaggio del dominio da `atlas-domain-modeling`. Il metodo che regge il grafo intero, destinazione, nebbia e ambito, sta in `atlas-wayfinder`. `atlas how-to` elenca le skill presenti qui.

`close` verifica una cosa sola, che la sezione **Risposta** del ticket sia compilata. Il resto lo dichiara chi chiude. Che la risposta sia anche vera non lo può verificare nessuna macchina, e l'unica difesa è che la scriva chi ha fatto il lavoro mentre ce l'ha fresco.

C'è però un caso in cui `close` rifiuta e non dipende da cosa hai scritto: il nodo è cambiato da quando l'hai preso. Alla presa Atlas registra un'impronta del contenuto e alla chiusura la riverifica, perché fra i due momenti passa tutto il tempo del lavoro, e in quel tempo un altro agente o uno script di mutazione può aver cambiato la domanda, le dipendenze o l'ambito del nodo su cui stavi ragionando. La tua risposta entrerebbe pulita e poggerebbe su una premessa che non c'è più, senza che nessuno se ne accorga. Quando succede, rileggi il nodo con `atlas show <ID>` e decidi: richiudi se la tua risposta regge lo stesso, oppure aggiornala. `--force` chiude comunque, e va usato quando il cambiamento non tocca quello che hai scritto.

Sotto Risposta ci sono tre sotto-sezioni leggere e facoltative: **scelte non canoniche** (cosa hai deciso a tavolino, non dettato dal documento di design), **debito dichiarato** (cosa lasci volutamente incompleto, e perché) e **autorizzazioni ricevute** (se hai agito oltre l'ambito del nodo su indicazione esplicita dell'utente, cosa e quando). Un cancello di verifica le legge senza dover ricostruire la stessa archeologia da una prosa libera, e la terza rende verificabile un "come da tua richiesta" invece che solo asserito.

`close` accetta anche `-c/--costo` (un ordine di grandezza di quanto è costato, testo libero, niente di preciso) e `--artefatti` (i file prodotti, popolano il campo che il grafo già prevede). Senza `--artefatti`, in una repo git il campo si popola da solo con i file toccati da quando il nodo è stato rivendicato, esclusi quelli di `.atlas/`. La deduzione salta, e `close` rifiuta: non lascia chiudere un nodo con il campo vuoto per errore. Succede se al momento della chiusura c'è più di un nodo rivendicato, oppure se un altro nodo del grafo è stato chiuso o rilasciato mentre questo era in lavorazione, perché in quella finestra il lavoro dei due si sovrappone e git non sa dire di chi è ciascun file. Il messaggio indica il motivo e chiede di dichiarare gli artefatti. Quando invece deduce, `close` stampa l'elenco dei file dedotti: guardalo, perché è l'unico momento in cui te ne accorgi senza andarlo a cercare. È quel campo che permette a `doctor` di accorgersi di una scrittura dentro l'ambito di un nodo già chiuso; per dichiarare intenzionalmente nessun artefatto usa `--artefatti` senza argomenti.
Il flag esplicito prende un solo path e va ripetuto. Token con spazi o virgole sono rifiutati per evitare che una variabile zsh venga spezzata in più artefatti; i path dichiarati ma mancanti vengono segnalati alla chiusura.

Se in quell'elenco c'è roba che non è tua, o se il costo e la sintesi sono usciti sbagliati, la correzione è `atlas amend <ID> [--artefatti ...] [--costo ...] [--sintesi ...]`. Riscrive i soli campi che passi e lascia stare tutto il resto: il nodo resta chiuso, e l'istante della chiusura non si sposta, perché è da lì che `doctor` misura le scritture postume. La correzione resta scritta nel nodo con chi l'ha fatta e quando, così chi rilegge sa che quel campo è stato messo a mano e non dedotto. Un nodo ancora aperto non si corregge: lì la contabilità la scrive `close`. Se un cancello rilascia un nodo invece di chiuderlo, `-r/--ragione` su `release` registra il perché come evento in mappa, non solo come un ritorno silenzioso alla frontiera.

### Chi fa cosa, se serve

Un nodo può essere assegnato a una o più persone con `atlas assign <nomi> <ID...>`, dove la virgola separa i nomi; `atlas assign cristiano,pedro F01` lo affida a entrambi. Senza `--add` e senza `--remove` il comando sostituisce l'intero elenco del nodo, che è il comportamento di sempre esteso a più nomi; `atlas assign lucia F02` lo lascia a lei sola, qualunque fosse l'assegnazione precedente. La virgola separa le persone e un nome non può contenerla, come non può contenere il `+`: il comando lo rifiuta indicando la virgola come rimedio. Un grafo scritto con la forma vecchia, anche con nomi congiunti come `cristiano+pedro`, continua a leggersi, e la prima mutazione lo rimette in pari da sola.

`--branch <ramo>` prende i nodi che quel ramo ha in quel momento, e uno aggiunto dopo nasce senza assegnatario. Assegnare un ramo sovrascrive anche i nodi che erano già di qualcun altro, e il comando stampa gli id che ha cambiato. `--add <nome>` aggiunge una persona a quelle che il nodo ha già, `--remove <nome>` ne toglie una sola lasciando le altre, e `--me` assegna a te senza riscrivere il nome, perché chi lavora da questa copia lo ricorda `atlas whoami <nome>`. Il file `.atlas/whoami` non è versionato. `atlas unassign <ID...>` riporta il nodo a nessuno.

L'assegnazione non è il lucchetto e non lo sostituisce: dice di chi è quel pezzo di lavoro, mentre il `claim` dice chi ci ha le mani sopra adesso. Un nodo assegnato resta prendibile da chiunque, e assegnarlo mentre qualcuno lo sta lavorando non gli impedisce di chiuderlo. Se non le usi, il grafo si comporta esattamente come prima: nessun nodo nasce assegnato e la dashboard non mostra niente in più.

### Più grafi

Un grafo per epic, ciascuno isolato in `.atlas/graphs/<slug>/` con la sua mappa e la sua dashboard. `atlas new <nome>` antepone da solo la data di creazione al nome tecnico che dai (`<nome>` diventa `YYMMDD-<nome>`): lo slug vero è quello, non quello passato sulla riga di comando. Lo switch è a carico di chi lavora: `atlas use <slug>`, oppure `-g/--graph <slug>` sul singolo comando, che vale sia prima sia dopo il comando stesso. Lo slug non si scrive al posto del comando: `atlas <slug> render` non esiste.
