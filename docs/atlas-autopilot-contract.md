# Atlas Autopilot: contratto pubblico

Versione del contratto: 1.

Atlas Autopilot è un runner meccanico per eseguire il lavoro già descritto da un
grafo Atlas. Il runner coordina processi agentici, ma non ragiona al posto del
grafo e non usa un LLM come orchestratore.

La superficie CLI per un run è:

```sh
atlas run --parallelism 1
atlas run-status
atlas run-log --tail 20
```

## Confini del contratto

Il contratto riguarda una singola esecuzione di Autopilot, indicata qui come
run. Il run riceve:

- il grafo Atlas su cui lavorare;
- il parametro obbligatorio `parallelism`, intero positivo e valido solo per
  quel run.

Il valore `parallelism=1` significa esecuzione strettamente seriale: un solo
agente può essere attivo e il nodo successivo non parte prima della chiusura del
precedente. Un valore maggiore di `1` abilita parallelismo limitato: in ogni
istante il numero di agenti attivi non supera il valore ricevuto. Il grafo non
salva il parallelismo e Autopilot non introduce un default implicito. Un run che
non riceve il parametro, o lo riceve non intero o non positivo, è invalido e
deve essere rifiutato prima di avviare un agente.

## Contratto operativo

### 1. Il runner è meccanico

Autopilot non usa un LLM per scegliere i nodi, ordinare la coda, interpretare
`blockedBy`, decidere se un nodo è eleggibile o dichiarare concluso il run.
Queste decisioni derivano esclusivamente dallo stato Atlas e dalle sue
operazioni di lettura e chiusura. Un adapter può usare un LLM per eseguire il
lavoro del nodo, ma non per sostituire la macchina a stati del runner.

### 2. La frontiera Atlas è la sorgente di verità

Prima di ogni avvio Autopilot legge la frontiera Atlas del grafo attivo e lancia
solo nodi aperti i cui blocker risultano chiusi, nel rispetto del limite di
parallelismo. Dopo ogni chiusura osservata rilegge il grafo e ricostruisce la
frontiera. Una coda locale, un log del run o l'output di un agente possono
servire per riprendere e diagnosticare il lavoro, ma non possono autorizzare
un avvio che la frontiera Atlas non autorizza.

Ogni nodo avviato deve essere protetto dal claim Atlas. Un nodo già chiuso,
fuori ambito, rivendicato da un altro agente o non presente nella frontiera non
può essere avviato una seconda volta dallo stesso run.

Il claim lo prende il runner prima di lanciare il provider, e lo prende per
conto di quel provider: il lucchetto porta l'identità dell'agente che lavorerà
il nodo, non quella del processo che avvia il run. L'agente lanciato riceve
quindi un nodo già suo e non deve rivendicarlo di nuovo. Un claim preso per
conto d'altri non registra PID né sessione del runner, perché il processo che
lavorerà non è quello: la sua liveness è il lease, che scade da solo.

### 3. Ogni agente è AFK

Autopilot avvia ogni agente senza richiedere input umano durante il run. Il
processo agente esegue fuori sandbox e con bypass dei permessi, secondo il
contratto dell'adapter selezionato. Un nodo HITL non è un'eccezione implicita:
se il grafo lo contiene, il runner deve segnalarlo come incompatibile con un
run AFK invece di rispondere al posto dell'umano.

### 4. Gli adapter sono un confine estensibile

Il runner dipende da un'interfaccia di lancio, non da un provider concreto. Un
adapter deve dichiarare almeno la propria identità, accettare un contesto di
nodo e run e restituire un esito osservabile che permetta di distinguere
chiusura, errore e terminazione ambigua. Aggiungere un provider richiede di
registrare un nuovo adapter, non di cambiare la logica di frontiera,
parallelismo o terminazione del runner.

Quando il nodo non richiede un modello specifico, la selezione runtime usa
Codex Luna. Se Luna non è disponibile, il comportamento di fallback verso
Claude Sonnet deve essere esplicito e osservabile; una richiesta esplicita di
modello non può essere sostituita in silenzio da un altro provider.

### 5. Contratto del processo figlio

L'adapter concreto usa `subprocess.Popen` con una lista argv, `shell=False` e
`stdin=DEVNULL`. L'istruzione del nodo è un solo argomento del processo: valori
come titolo, domanda e path non vengono interpolati in una shell. `cwd` è la
radice del progetto, non una sandbox temporanea.

Il figlio eredita l'ambiente necessario al provider, compreso `PATH` e le
credenziali già configurate, e riceve sempre questi valori minimi:

- `ATLAS_ROOT`: cartella `.atlas` del progetto;
- `ATLAS_GRAPH`: slug del grafo attivo;
- `ATLAS_IDENTITY`: identità dell'adapter;
- `ATLAS_AUTOPILOT_NODE`: id del nodo rivendicato.

Il provider deve lavorare senza input umano, aggiornare Atlas usando il claim
ricevuto, scrivere la risposta nel ticket e chiudere il nodo. Il processo
restituisce `closed` per exit status zero, `error` per un exit status diverso da
zero e `crash` se termina per segnale. Un exit status zero non autorizza da solo
la chiusura: il runner rilegge Atlas e accetta solo uno stato terminale.

Le configurazioni concrete usano le modalità non interattive dei provider:
Codex `exec --dangerously-bypass-approvals-and-sandbox`, Claude `--print
--dangerously-skip-permissions`, Gemini `--prompt ... --sandbox=false --yolo
--skip-trust`. Un provider aggiuntivo può usare `SubprocessAdapter` con la
propria lista argv già validata, come `code_terra_adapter`, senza modificare il
runner.

## Stato e diagnosi del run

Ogni esecuzione che entra nel runner scrive atomicamente `run-state.json` nella
cartella del grafo. Lo snapshot conserva lo stato corrente (`active`, `waiting`,
`failed`, `blocked` o `completed`), il parallelismo, l'ultimo nodo, provider e
tentativo osservati, la frontiera e i blocker residui. La lista `events` conserva
la cronologia di avvio, claim, selezione provider, tentativi, fallback, attese,
backoff, errori, chiusure e aggiornamenti della frontiera.

`atlas run-status` legge lo snapshot e rende leggibile il motivo per cui il run
non avanza. `atlas run-log` stampa la cronologia, con `--tail N` per limitare gli
eventi mostrati. Questi dati sono diagnostici e non sono una seconda fonte di
verità: il runner continua a rileggere `graph.json` prima di ogni avanzamento.
Il ledger non conserva processi o handle e questa versione non implementa il
resume completo di un agente dopo un'interruzione.

### Interpretare diagnosi e retry

Lo stato `active` significa che il runner sta valutando la frontiera o ha agenti in esecuzione. `waiting` significa che un retry ha un prossimo istante utile, mentre `failed` indica un errore senza ulteriore tentativo possibile. `blocked` indica che la frontiera è vuota ma restano nodi aperti o claim che impediscono l'avanzamento. Solo `completed` è un successo, e richiede le condizioni di terminazione valide.

Il retry predefinito è bounded e usa un backoff esponenziale da 60 secondi fino a 3600 secondi. Sono ritentabili timeout, crash, rate limit, provider non disponibile e terminazione ambigua. Un agente che termina senza lasciare il nodo terminale è una terminazione ambigua di quel nodo, con un tetto di tentativi più stretto del budget generale: un rilancio identico raramente cambia esito e il costo lo paga la quota del provider. L'esaurimento del budget di un nodo non ferma il run, che continua sui rami che non dipendono da quel nodo; il verdetto finale nomina tutti i nodi esauriti. Un errore permanente esaurisce il budget senza rilancio. L'indisponibilità del provider Luna attiva prima un solo fallback a Claude Sonnet quando il modello del nodo è vuoto; non trasforma un errore del lavoro e non sostituisce una richiesta esplicita. `run-status` mostra il prossimo tentativo e il motivo, mentre `run-log` permette di seguire classificazione, attesa e rilancio. Un claim vivo blocca il duplicato; dopo un'interruzione il processo provider non viene ripreso.

## Terminazione valida

Autopilot può dichiarare un run completato con successo solo quando tutte le
condizioni seguenti sono vere nello stesso stato osservato:

1. la frontiera Atlas è vuota;
2. non ci sono agenti attivi, claim ancora protetti o retry in attesa;
3. ogni nodo è terminale, cioè `closed` oppure `out-of-scope`;
4. ogni chiusura richiesta dal lavoro è stata registrata da Atlas, con la
   risposta prevista dal contratto del nodo.

Una frontiera vuota da sola non è sufficiente. Se restano nodi aperti bloccati,
un agente attivo, un retry pianificato o una terminazione ambigua, il run è
rispettivamente bloccato o non riuscito e deve produrre una diagnosi, non un
successo. La riconciliazione dello stato dopo interruzioni deve mantenere
questa stessa regola: un run ripreso non può contare come chiuso un nodo che
Atlas non mostra come terminale.

## Criteri di successo

L'implementazione di Autopilot soddisfa questo contratto quando le verifiche
dimostrano che:

- l'avvio rifiuta un `parallelism` mancante, non intero o non positivo;
- `parallelism=1` non sovrappone agenti e valori maggiori non superano il
  limite;
- il runner avvia solo la frontiera Atlas e la rilegge dopo le chiusure;
- nessuna decisione di scheduling, dipendenza o avanzamento richiede un LLM;
- ogni processo è AFK, fuori sandbox e con bypass dei permessi;
- un adapter aggiuntivo può essere registrato senza modificare il runner;
- chiusure, errori e terminazioni ambigue sono distinguibili e osservabili;
- il run dichiara successo solo con una terminazione valida secondo le quattro
  condizioni sopra.

## Fuori ambito di questo contratto

Questo documento non decide i dettagli provider-specifici della CLI, del formato
persistente dello stato, del protocollo degli eventi di chiusura o
dell'implementazione dei singoli adapter. Questi sono contratti tecnici separati
che devono rispettare i confini qui stabiliti; i comandi pubblici, la politica di
retry predefinita e la diagnosi descritti sopra sono invece parte della consegna
di Autopilot.

Autopilot inoltre non modifica automaticamente la topologia Atlas, non inventa
blocker, non risponde a nodi HITL e non tratta una coda locale come una seconda
fonte di verità. La selezione di un ordine di lavoro può essere deterministica
e configurata, ma non può contraddire la frontiera del grafo.
