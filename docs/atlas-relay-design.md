# Relay universale delle notifiche — documento di lavoro

**Stato:** primo incremento costruito e chiuso (grafo `260902-atlas-relay`), mai
messo in servizio. Codice e 228 test coprono il giro intero, il deploy vero resta
da fare (§9, §11-ter): senza di esso il metro di successo di §11/12 non è ancora
misurabile.
**Aperto il:** 2026-09-02
**Ultima iterazione:** 14 (vedi §10)

Questo documento è vivo. Si lavora a cicli: si aggiunge quello che si decide, si
sposta in §8 quello che si scarta e si tiene in §7 quello che manca, con il suo
stato. Nessuna decisione va persa perché è finita in una conversazione. Quando il
disegno regge, da qui nasce un grafo di lavoro, non prima.

---

## 0. La regola che governa tutto: semplicità disarmante

Filosofia Apple, e non come slogan: **l'utente trova tutto pronto, fa pochissime
azioni e la cosa funziona come per magia, senza vedere niente della complessità
sotto.** Ogni scelta di questo documento si giudica prima di tutto qui, e una
soluzione tecnicamente elegante che aggiunge un passo all'utente perde contro una
meno elegante che lo toglie.

Tradotta in regole verificabili:

- **Zero configurazione per cominciare.** Nessuna domanda durante l'installazione,
  nessun file da editare, nessuna variabile d'ambiente da esportare a mano.
- **Un gesto, non una procedura.** Collegare il telefono è un bottone e un tap sul
  deep link. Se un giorno servono due passi, quel giorno il disegno è sbagliato.
- **Le chiavi non si vedono mai.** Nessun identificatore da copiare, nessun token
  da incollare, nessun blob da trasferire. Se compare una stringa che l'utente
  deve maneggiare, è un difetto di disegno, non una funzionalità.
- **Il vocabolario resta umano.** Nel pannello si legge «collega Telegram» e «già
  risolto da qualcun altro», mai «graphId», «bearer» o «capability».
- **Il default fa la cosa giusta.** Senza relay configurato Atlas non manda mai
  niente in rete e non arriva mai una notifica; con il relay configurato partono
  da sole, senza che nessuno le accenda. *Corretto dalla verifica del primo
  incremento (§11-ter): il bottone «collega Telegram» resta comunque visibile
  anche prima di ogni configurazione, perché è il solo modo con cui si scopre la
  funzione (grilling 27) — la promessa riguarda il traffico e le notifiche, non
  la presenza del bottone.*
- **Un errore si spiega da solo e dice il rimedio**, come già pretende il contratto
  di Atlas per i guasti del grafo.

---

## 1. Il problema

Il relay costruito dal grafo `260830-atlas-interactions` funziona per una persona
sola che si fida della propria macchina. Vogliamo che sia un servizio universale,
usabile da chiunque abbia Atlas, sconosciuti compresi. Il modello attuale non
regge quel salto per due difetti di fondo.

**L'identità di un grafo è il suo nome.** Lo slug `YYMMDD-nome` non è unico e non
è rivendicabile: chiunque può creare un grafo con lo stesso nome sulla propria
macchina e chiedere al relay le notifiche destinate a un altro. Non esiste un
controllo che renda sicuro uno spazio di nomi che tutti possono scrivere.

**Il bearer del tunnel è uno solo per istanza.** Il commento nel codice promette
«un token per progetto», l'implementazione ne conosce uno soltanto. Chi lo ha per
usare il servizio può aprire un tunnel dichiarando il grafo di chiunque altro.

---

## 2. I tre profili d'uso, e il patto sull'attrito

Il vincolo che governa ogni scelta di questo documento: **il costo di
configurazione cresce solo quando cresce l'ambizione dell'utente.** Chi non vuole
le notifiche non deve nemmeno sapere che esistono.

**Profilo A, offline.** Atlas come oggi: grafo locale, dashboard locale, nessuna
rete. Nessuna registrazione, nessun account, nessuna chiave, nessuna domanda in
fase di installazione. Se il relay non è configurato, nessuna richiesta parte mai
verso di lui e nessuna notifica può arrivare. È il profilo predefinito e resta
tale. *Corretto dalla verifica del primo incremento (§11-ter): il pannello
Notifiche mostra comunque, sempre, il bottone «collega Telegram» e la riga sul
carattere sperimentale del servizio — non c'è modo di scoprirlo altrimenti
(grilling 27) — ma restano gli unici due elementi che compaiono, e il tap è
l'unico gesto che fa uscire una richiesta dalla macchina. Chi apre la dashboard
da `file://` (`atlas render`) non vede nemmeno quello attivo: il bottone resta
a video ma disabilitato, nessuna richiesta può partire.*

**Profilo B, da solo ma con le notifiche.** Una persona, una macchina, uno o più
grafi, e il telefono che avvisa quando serve una decisione. Il gesto è uno: il
bottone di pairing nel pannello Notifiche, il deep link che apre Telegram, fatto.
Nessuna chiave da leggere, nessun invito da generare, nessun concetto nuovo da
imparare. La registrazione del grafo al relay avviene da sola alla prima notifica.

**Profilo C, condiviso.** Più persone sullo stesso grafo, ognuna col suo telefono,
il grafo che viaggia via git. *Riscritto dalla decisione 10 del grilling:* l'invito
non esiste e non esiste nessuna membership da autorizzare. Ognuno collega il proprio
telefono al proprio computer, una volta, e riceve le notifiche dei lavori che lancia
lui. Il profilo C smette di essere un terzo scalino di configurazione e diventa
semplicemente due persone che stanno entrambe nel profilo B sullo stesso repository.

Un profilo non deve pagare per il successivo. In particolare B non deve vedere
nessuna delle parole «chiave», «identificatore», «token».

---

## 3. Requisiti

1. ~~Un grafo è unico anche quando è condiviso: chi lavora un grafo riceve le
   notifiche degli eventi di quel grafo, generati da chiunque, ovunque.~~
   **Decaduto con la decisione 10**, che sposta l'identità dal grafo
   all'installazione. Il requisito vero è ora: chi lancia un lavoro riceve le
   notifiche di quel lavoro, e nessun altro.
2. Due grafi omonimi su macchine diverse restano estranei. *Soddisfatto per
   costruzione dalla 10: il nome del grafo non instrada più niente.*
3. Nessuno può ricevere le notifiche di un lavoro che non ha lanciato.
4. Chi non usa le notifiche non paga niente in configurazione, e non vede
   comparire concetti che non gli servono.
5. Il servizio regge sconosciuti: quote, limiti, dimenticanza e interruttore per
   singolo grafo.
6. Chi non si fida del relay altrui deve poter mettere in piedi il proprio in
   pochi minuti, col proprio bot.
7. Zero dipendenze di terze parti, come tutto il resto di Atlas.

---

## 4. Modello proposto (superato da §4-bis, tenuto come traccia)

### 4.1 L'identità di un grafo

Lo slug resta l'etichetta per gli umani. L'identità diventa una coppia generata
alla prima registrazione:

- **`graphId`**, 128 bit casuali, pubblico. Non lo si sceglie e non lo si indovina.
- **`graphKey`**, 256 bit segreti, la prova di appartenenza al gruppo.

Il relay impara la coppia al primo contatto (fiducia al primo uso) e da lì accetta
operazioni su quel `graphId` solo da chi prova di conoscere la chiave. La chiave
vive in `.atlas/relay.json`, fuori da git. Nel `graph.json` versionato non finisce
niente: un repository pubblico non deve rivelare nemmeno che quel grafo usa un
relay.

### 4.2 Come entra un collaboratore

Alla luce di §0 la domanda giusta non è come si trasporta una chiave, ma come si
fa a non doverne trasportare nessuna.

**Proposta rivista: la membership segue il repository.** Chi può leggere il grafo è
membro del grafo, quindi `.atlas/relay.json` viaggia con il repo come già fa
`graph.json`. Pedro clona, lancia Atlas e riceve, senza che nessuno gli mandi
niente. Il telefono lo collega con lo stesso bottone che uso io, un tap, uguale per
tutti.

Costo di questa scelta: un repository pubblico rende pubbliche anche le notifiche
del grafo. Il rimedio non è un passo in più per tutti, è un avviso per il caso
raro, cioè Atlas che riconosce un remote pubblico e lo dice una volta.

**Alternativa a maggiore attrito, tenuta come riserva:** la chiave resta fuori da
git e si consegna con un invito da incollare. Più sicura per un repo pubblico, ma
introduce il gesto che §0 vieta, quindi si adotta solo se la prima strada si
rivela insostenibile.

### 4.3 Il pairing diventa molti a molti

Oggi una chat sta su un progetto solo e un progetto ha una chat sola. Per un grafo
condiviso serve che un grafo abbia N chat e una chat segua N grafi. Una Interazione
aperta raggiunge tutte le chat del grafo; il primo che risolve vince, e agli altri
il messaggio si aggiorna in «già risolto» invece di restare un bottone che finge
di funzionare.

### 4.4 Il relay diventa un bus di eventi

Se anche gli eventi del grafo (nodo preso, chiuso, riaperto, run fallito) devono
raggiungere i membri, il relay smette di essere un ponte per le sole Interazioni.

Con una conseguenza da scrivere adesso: **il relay non è la fonte di verità e non
possiede il grafo.** Notificherà «qualcuno ha chiuso D04» anche quando il
`graph.json` locale di chi legge non sa ancora che D04 esiste. La notifica è un
fatto remoto, l'allineamento resta un gesto git. Questo tocca il grafo
`260825-sync-distribuita`: i due meccanismi devono guardarsi in faccia, altrimenti
raccontano storie diverse sullo stesso grafo.

### 4.5 Autenticazione delle richieste

Ogni richiesta al relay porta il `graphId` e una prova HMAC calcolata sulla chiave,
con marca temporale e nonce, così una richiesta intercettata non si rigioca. Il
bearer statico condiviso sparisce.

---

## 4-bis. Il modello che risulta dal grilling

**Questa sezione sostituisce §4**, che resta sotto come traccia di come si ragionava
prima. Il cambiamento maggiore viene dalla decima risposta: se una notifica raggiunge
solo chi ha lanciato quel lavoro, allora l'identita' che conta non e' quella del grafo
ma quella dell'**installazione**, e il problema da cui questo documento e' nato (due
grafi omonimi, notifiche rubate per nome) sparisce senza bisogno di difenderlo.

**Chi e' chi.** Ogni installazione di Atlas ha una sua identita' segreta, creata al
primo collegamento e mai mostrata a nessuno. Il relay conosce quella, non i grafi. Un
progetto non ha identita' presso il relay: e' solo un'etichetta dentro un messaggio.

**Cosa sa il relay.** Le installazioni collegate con la loro chat Telegram, i numeri
d'uso dell'ultimo mese e i blocchi. Non lo stato dei grafi, non le decisioni non
consegnate, non i testi passati. Il nome Telegram di chi ha collegato il telefono si
conserva, il nome dei progetti no.

**I due gesti dell'utente.** Collegare il telefono, una volta per computer, da un
bottone discreto sempre presente. Accendere le notifiche di un progetto, alla sua
creazione, con la levetta che nasce spenta.

**Il giro completo.** Un lavoro si ferma e chiede una decisione; il client, che tiene
la linea aperta verso il relay solo mentre lavora, manda il messaggio; il relay lo
consegna alla chat giusta; chi legge preme un bottone; il tap torna indietro lungo la
stessa linea e risolve la decisione nel grafo; il messaggio si aggiorna. Se la linea
non c'e' piu', il bot lo dice subito e non promette niente.

**Cosa fa il lavoro mentre aspetta.** Prosegue su tutto quello che non dipende da
quella decisione, e resta fermo solo li'. Se il relay e' irraggiungibile, aspetta e
basta.

**Il gestore.** Vede la lista e blocca dal bot stesso, con comandi riservati. Chi
viene bloccato lo sa. Nessuna quota preventiva: si guarda e si interviene.

---

## 5. Il limite che non si può togliere

Il relay vede in chiaro il testo delle notifiche, perché deve consegnarlo a
Telegram. Nessuna cifratura da un capo all'altro è possibile quando il destinatario
finale è Telegram, e senza dipendenze esterne non è disponibile nemmeno la firma
asimmetrica che eviterebbe al relay di conoscere le chiavi (la stdlib offre hash e
HMAC, non curve ellittiche).

Chi usa un relay altrui si fida di chi lo gestisce, come chi usa un server di posta.
Tre conseguenze operative:

- al relay va il minimo indispensabile: titolo del nodo e azioni ammesse, mai il
  ticket, mai i path, mai la risposta;
- il limite si dichiara nel Quick Start, non si lascia scoprire dopo;
- il self-hosting resta di prima classe.

---

## 6. Limiti operativi, prima di aprire agli sconosciuti

Il bot porta il nome di chi lo ha creato: se qualcuno lo usa per fare volume,
Telegram limita o banna il bot, non l'abusante. Servono, prima dell'apertura:

- quota di messaggi per grafo e per ora;
- tetto di chat per grafo e di grafi per chat;
- dimenticanza automatica di un grafo che non si fa vivo da mesi;
- limite di dimensione sul payload;
- interruttore per spegnere un singolo `graphId` senza toccare gli altri;
- una riga onesta su cosa succede se il servizio sparisce, perché gira su una
  macchina personale e non è un impegno contrattuale.

---

## 6-bis. Decisioni prese nel grilling del 2026-09-02

Ogni riga viene da una domanda posta e da una risposta data, in ordine. Le
domande successive sono state costruite sulle risposte precedenti.

| # | Domanda | Deciso |
|---|---------|--------|
| 1 | Natura del servizio | Un relay pubblico solo, gestito da Cristiano, con il suo bot. Non self-host per tutti, non solo locale. |
| 2 | Chi puo' entrare | Chiunque, senza chiedere permesso. In cambio il gestore vede chi c'e', quanto manda, e puo' bannare o limitare. |
| 3 | Cosa vede il gestore | Codice del grafo, numeri d'uso, nome Telegram di chi ha collegato il telefono. Non il nome del progetto: quello resta di chi lavora. |
| 4 | Quanto dice il messaggio | Tutto quel che serve per decidere, titolo del nodo compreso. Il limite (il relay legge quei testi) e' accettato come patto dichiarato di una funzione sperimentale, con il self-host documentato piu' avanti per chi vuole il bot privato. |
| 5 | Come arrivano i tap da Telegram | Il relay chiede a Telegram, non viceversa. **Corretta il 2026-09-03**: questo vale per il solo verso Telegram→relay, e con esso cadono il secret token, `setWebhook` e il vincolo sulle porte che Telegram accetta. Il verso client→relay resta pubblico, perché il tunnel e il pairing partono dalla macchina di chi usa Atlas: un hostname con certificato serve comunque, per servire il client invece che Telegram. |
| 6 | Quando suona il telefono | Solo quando serve una decisione. Il resto si chiede al bot con comandi, quando si vuole. |
| 7 | Chi risponde a quelle domande | Il Mac, se acceso. Il relay non conserva lo stato dei progetti di nessuno. |
| 8 | Tap premuto mentre il Mac dorme | Nessuna coda: il bot risponde subito che il computer non risponde. Il relay non conserva decisioni in sospeso. |
| 9 | Quanti collegamenti per più progetti | Uno solo, valido per tutti i progetti presenti e futuri di quella macchina. |
| 10 | Chi riceve su un progetto condiviso | Solo chi ha lanciato quel lavoro. **Conseguenza**: nessuno riceve per nome del progetto, quindi il furto di notifiche per slug omonimo non esiste piu' come minaccia. |
| 11 | Due computer della stessa persona | Il telefono riceve da qualunque macchina stia lavorando in quel momento. |
| 12 | Cosa risponde `/view` | Una foto della dashboard vera, scattata dal browser gia' presente sulla macchina. |
| 13 | Se quel browser non c'e' | Si prova Chrome, poi gli altri installati, e si usa il primo che risponde. |
| 14-17 | Come si collega il secondo computer | Il collegamento **non** viaggia nel progetto: sarebbe inerte per una macchina diversa (16) e regalerebbe il contatto a chi riceve il repo. Si collega con un tap, una volta per computer. |
| 16 | Collega senza collegamento che lancia un lavoro | Non suona a nessuno, e la dashboard gli propone di collegarsi. Mai notifiche di un lavoro altrui a chi non l'ha lanciato. |
| 18 | Quota contro il ban di Telegram | ~~Nessun tetto preventivo, vigilanza a posteriori.~~ **Superata da §7-ter/4**: oltre una soglia larga il servizio blocca da sé e avvisa entrambi. |
| 19 | Potere dei bottoni sul telefono | Pieno: conferma, rifiuta, riprova, ferma il lavoro. Nessuna doppia conferma, nessuna azione riservata al computer. |
| 22 | Lavoro fermo e relay irraggiungibile | Il lavoro aspetta, come già fa oggi per un nodo che chiede una decisione. Nessun ritentativo e nessuna scadenza. *Corretta da §7-ter/3*: la mancata consegna si vede sulla dashboard, non si lascia scoprire da sé. |
| 23 | Installazioni vecchie dopo un cambio di protocollo | Il relay parla solo l'ultima lingua. *Corretta da §7-ter/6*: l'avviso arriva sul telefono prima che il servizio smetta, non sulla dashboard dopo. |
| 24 | Registri del relay | Solo numeri (chi, quando, quante, esito), conservati un mese. Nessun testo di nessuno finisce su disco. |
| 25 | Dove sta il pannello del gestore | Comandi riservati dentro il bot stesso: elenco, numeri, blocco. Nessuna pagina web, nessun accesso al server necessario per intervenire. |
| 26 | Chi viene bloccato lo sa? | Si', gli si dice chiaramente che l'accesso e' sospeso. Nessun blocco silenzioso. |
| 27 | Come si scopre la funzione | Un bottone discreto e sempre presente nel pannello. Nessuna proposta non richiesta, nessuna interruzione a chi lavora offline. |
| 28 | Nessuna risposta alla notifica | Il lavoro prosegue su tutto cio' che non dipende da quella decisione, e resta fermo solo il pezzo che aspetta la persona. **Chiude il difetto noto per cui oggi un nodo che aspetta una persona ferma l'intero run.** |
| 29 | Progetti riservati | Una levetta per progetto che lo esclude dalle notifiche. |
| 30 | Default della levetta | ~~Spenta, da accendere per progetto.~~ **Ribaltata da §7-ter/1**: accesa. Collegato il telefono, ogni progetto notifica, e la levetta serve solo a zittire quelli riservati. |
| 31 | Quando si accende | ~~Alla creazione del progetto.~~ **Decaduta con la 30**: non c'è più niente da accendere. Chi ha un progetto riservato lo spegne quando vuole. |
| 32 | Quando il Mac tiene la linea aperta | Solo mentre un lavoro gira. Nessun programma residente sul computer di nessuno. **Conseguenza**: i comandi al bot rispondono solo mentre qualcosa sta girando, e fuori da quella finestra il bot lo dice invece di tacere (§7-ter/2). |
| 33 | Che promessa si fa agli utenti | Nessuna, dichiarata in una riga: servizio sperimentale, puo' finire quando il gestore vuole. |
| 34 | Lingua del messaggio | Quella del progetto, coerente con pannello e ticket. |
| 35 | Dove sta l'indirizzo del relay | Dentro Atlas come valore di partenza, sovrascrivibile da chi vuole il proprio. |
| 36 | Cosa entra nella prima versione | Tutto: notifiche, bottoni, comandi al bot e `/view`. |

**Cosa cambia rispetto al disegno di partenza**

- Il webhook esce di scena e con lui l'hostname pubblico, il certificato, la
  porta da aprire *per Telegram*, con il secret token e `setWebhook` (decisione 3
  di §7 chiusa, alternativa gia' in §8). L'hostname resta invece necessario al
  verso client→relay, che il webhook non ha mai riguardato: vedi la riga 5 di
  questa tabella, corretta il 2026-09-03.
- Nasce una funzione che il disegno non aveva: **il bot risponde a domande**, e
  la risposta viaggia dal relay al client lungo il tunnel gia' esistente, che
  finora andava in un verso solo per le notifiche.
- Nasce un pannello di amministrazione minimo per il gestore: elenco dei grafi
  attivi con i loro numeri, e i due gesti di blocco.
- Il relay resta **senza memoria del lavoro altrui**: nessuna copia dello stato
  dei grafi, solo cio' che serve a instradare e a far rispettare le quote.

**Altre conseguenze emerse fra la ottava e la diciannovesima**

- Il relay resta **senza coda e senza memoria**: non conserva stato dei grafi (7),
  non conserva decisioni non consegnate (8). Tutto quel che sa serve a instradare
  e a far rispettare i blocchi.
- Nasce `/view`: il bot chiede al client una foto della dashboard, che il client
  scatta con il browser di sistema e rimanda lungo il tunnel. Serve un ripiego per
  la macchina senza browser, e il riassunto scritto e' il candidato naturale
  (deciso a meta': la catena dei browser e' scelta, l'ultima spiaggia no).
- Il collegamento del telefono e' **per macchina**, non per persona e non per
  progetto. Una persona con due computer fa due tap in tutto la vita.
- L'identita' che conta per le notifiche e' quella dell'**installazione**, non
  quella del grafo: e' il run a essere notificato, e un run appartiene alla
  macchina che lo ha lanciato.


---

## 6-ter. La svolta proposta e ritirata: la notifica come sola notifica

**Proposta alla ventesima domanda, ritirata alla ventunesima.** Vale come **piano B
gia' ragionato**, non come decisione: se un giorno mantenere l'interazione da
Telegram costasse piu' di quanto rende, questa sezione dice esattamente cosa resta
togliendola. Il ritiro e' arrivato quando si e' visto che il codice interattivo era
gia' scritto, testato e committato dai nodi D06, D07 e D08: buttarlo per
semplificare sarebbe costato piu' della semplificazione ottenuta.

Nella versione proposta e non adottata, la prima versione non
porta nessuna interazione da Telegram verso Atlas. Il messaggio dice che serve una
decisione, offre il link alla sessione da remoto se quella sessione esiste, e
altrimenti invita ad andare al computer. Niente bottoni, niente comandi, niente
conversazione col bot. Poche cose, fatte bene.

**Cosa sarebbe caduto** (tutto questo resta invece in vigore)

| Deciso prima | Sorte |
|---|---|
| 6, 7 · comandi al bot per chiedere lo stato, con risposta dal Mac | rimandato |
| 8 · cosa succede a un tap con il Mac addormentato | non si pone: non ci sono tap |
| 12, 13 · `/view` con la foto della dashboard | rimandato, l'idea resta buona |
| 19 · potere pieno dei bottoni dal telefono | non si pone |

**Cosa non sarebbe cambiato in ogni caso**

| Deciso prima | Perche' regge |
|---|---|
| 1, 2, 3 · relay pubblico aperto, con vigilanza a posteriori | invariato |
| 4 · il messaggio dice titolo del nodo e cosa serve | invariato, anzi ora e' l'unica cosa che il messaggio fa |
| 9, 10, 11, 14-17 · collegamento per macchina, notifica a chi lancia il lavoro | invariato |
| 18 · nessuna quota preventiva | invariato |

**Cosa sarebbe diventato il relay**

Un servizio che riceve dal client un messaggio gia' scritto e lo consegna alla chat
giusta. In ingresso da Telegram gli serve una cosa sola: il `/start <codice>` con cui
qualcuno collega il telefono. Cadono le capability nei bottoni, il loro store, il
ritorno del tap e l'aggiornamento del messaggio, cioe' quasi tutto il lavoro dei nodi
D06, D07 e D08. Il polling verso Telegram resta, ma solo per vedere arrivare i
collegamenti.

---

## 7. Decisioni aperte

| # | Domanda | Stato |
|---|---------|-------|
| 1 | Registrazione aperta a chiunque, oppure su invito del gestore del relay? | **chiusa**: aperta, con vigilanza a posteriori (grilling 2) |
| 2 | Solo Interazioni, oppure anche gli eventi del grafo (§4.4)? | **chiusa**: solo le decisioni in push, il resto a richiesta (grilling 6) |
| 3 | Webhook con ingresso pubblico, oppure long polling in uscita? | **chiusa**: polling (grilling 5) |
| 4 | Come si revoca una `graphKey` compromessa, e che fine fanno le chat già appaiate? | **decaduta**: non esistono più le `graphKey`, l'identità è dell'installazione (grilling 10). Il gesto equivalente è staccare un computer dall'elenco (§7-ter/5). |
| 5 | Chi risolve una Interazione da Telegram: si registra quale membro è stato? | **decaduta**: riceve e risolve solo chi ha lanciato il run (grilling 10) |
| 6 | Il relay pubblico ha un nome e un'identità propria, oppure resta un servizio privato che qualcuno condivide? | **rimandata**: per il primo incremento è privato e a invito (§11/1), quindi la domanda si pone all'apertura. |
| 7 | Rapporto con `260825-sync-distribuita`: un grafo solo o due grafi che si parlano? | **chiusa**: due meccanismi distinti che si parlano da un lato solo. Quando un altro chiude un pezzo, il bot avvisa che conviene aggiornare senza dire cosa è cambiato (§11/9). |
| 8 | La chiave viaggia nel repo (nessun gesto) oppure fuori (nessun rischio da repo pubblico)? | **chiusa**: fuori dal repo, il collegamento e la chiave restano sulla macchina (grilling 14-17) |
| 9 | Che cosa manda `/view` quando nessun browser risponde? | **chiusa**: la dashboard come allegato (§7-bis) |
| 13 | Come si accorge il relay che una linea aperta e' morta, e per quanto la tiene? | **chiusa**: al momento del tap, nessun battito (§7-bis) |
| 14 | Quale etichetta di progetto mostra il messaggio? | **chiusa**: il titolo umano del grafo (§7-bis) |
| 10 | Cosa fa un lavoro in corso quando il relay non risponde? | **chiusa**: aspetta (grilling 22) |
| 11 | Che fine fa il codice dei tap gia' scritto (D06, D07, D08)? | **chiusa**: resta in servizio, l'interazione da Telegram si fa (grilling 21) |
| 12 | Il link alla sessione remota: quando esiste, e chi lo genera? | **chiusa**: c'e' quando la sessione e' governabile da remoto (§7-bis) |

---

## 7-bis. I quattro punti aperti, chiusi il 2026-09-02

| # | Punto | Deciso |
|---|-------|--------|
| 9 | `/view` quando nessun browser risponde | Il bot manda **la dashboard stessa come allegato**: Atlas la sa gia' costruire, quindi non serve nessun browser sulla macchina, e chi la apre sul telefono vede la pagina vera invece di una fotografia. La foto resta la scorciatoia che si legge senza toccare niente, il file la strada che funziona sempre. |
| 12 | Il link alla sessione remota | Compare **quando quel lavoro gira in una sessione governabile da remoto**, come riga in fondo al messaggio. Serve per le decisioni che non sono un si' o un no, dove i bottoni non bastano. Il costo accettato: una riga che a volte c'e' e a volte no. |
| 13 | Come si scopre che una linea e' morta | **Non si scopre prima, si scopre al momento**: nessun battito periodico, nessun traffico a vuoto, nessuno buttato fuori per una rete lenta. Il relay prova a consegnare il tap e, se il computer non risponde in pochi secondi, lo dice a chi ha premuto. Coerente con la scelta di non tenere code (8) e di non avere processi residenti (32). |
| 14 | Come il messaggio nomina il progetto | Con **il titolo umano** scritto da chi ha creato il grafo, non con lo slug. Il relay continua a non conservare nomi di progetti: quel titolo e' dentro un messaggio di passaggio, non in un archivio. |

**Conseguenze da tenere a mente quando si costruira'**

- `/view` ha due uscite (foto e allegato) che condividono la stessa domanda al client:
  vanno progettate insieme, non come due funzioni diverse.
- Senza battito, il relay non sa quante linee vive ha davvero. Per i numeri
  dell'ultimo mese (24) contano le consegne riuscite e fallite, non le connessioni.
- Il titolo del grafo diventa un dato che l'utente vede sul telefono: chi lascia il
  titolo generato di default se ne accorgera' li', ed e' un buon posto per accorgersene.

## 7-ter. La critica del 2026-09-02 e le sei correzioni

Riletto il documento con la sola lente di §0, il relay è risultato ben disegnato e
l'esperienza no. Esisteva un percorso realistico in cui una persona onesta collega il
telefono, lancia un lavoro, non riceve niente, chiede al bot e non ottiene risposta,
senza che in nessun punto qualcuno le dica cosa è successo. Le sei correzioni qui
sotto lo chiudono senza toccare l'architettura.

| # | Difetto trovato | Correzione decisa |
|---|-----------------|-------------------|
| 1 | La levetta spenta di default (30) contraddiceva §0 parola per parola, che promette notifiche «senza che nessuno le accenda», e imponeva un gesto per progetto. | **Accesa di default.** Collegato il telefono, ogni progetto notifica. La levetta resta, però serve a zittire un progetto riservato, non ad abilitare gli altri. Sparisce anche il buco della migrazione, perché i progetti già esistenti non hanno più niente da accendere. |
| 2 | I comandi al bot rispondevano solo mentre un lavoro girava (32), cioè tacevano proprio la sera a lavoro finito, quando uno prende il telefono per sapere com'è andata. | **Il bot risponde sempre, e quando il computer non è in linea lo dice.** Nessun riassunto lasciato al relay, che resta senza memoria. L'utente non resta mai in attesa di una risposta che non arriverà. |
| 3 | Nessuna coda (8), nessun ritentativo (22) e nessun battito (13) rendevano la notifica silenziosamente inaffidabile, con «se ne accorge da sé» al posto della diagnosi. | **La mancata consegna si vede sulla dashboard**, accanto al nodo in attesa. Nessun ritentativo e nessuna coda in più, quindi il costo è una riga di stato e il silenzio smette di essere inspiegabile. |
| 4 | Nessuna quota (18) contro un rischio dichiarato in §6: un abusante fa limitare il bot da Telegram e restano senza notifiche tutti gli altri, in silenzio. | **Soglia larga che blocca da sé**, con avviso sia al gestore sia a chi è stato fermato. Il bot resta protetto anche mentre il gestore dorme. Costo accettato: un lavoro grosso e legittimo può essere fermato per eccesso di prudenza, e per quello serve una via di contatto. |
| 5 | Il collegamento era per macchina ma non esisteva il gesto inverso, e senza battito (13) il relay non poteva nemmeno dimenticare le macchine morte come prevedeva §6. | **Un comando al bot elenca i computer collegati con l'ultima volta che si sono fatti vivi, e ne stacca uno con un tap.** Chi tace per mesi sparisce da solo. |
| 6 | Il protocollo unico (23) spegneva ogni Atlas non aggiornato del mondo nello stesso istante, con l'avviso sulla dashboard, cioè dove la persona non sta guardando. | **Il bot avvisa sul telefono prima** che il servizio smetta di servire quella versione, e dice come aggiornare. |

**Contraddizioni interne sanate nello stesso passaggio**

- §3 requisito 1 prometteva le notifiche a chi lavora il grafo, la decisione 10
  stabilisce l'opposto. Il requisito è ora marcato decaduto e riscritto.
- §2 profilo C descriveva inviti e membership che nel modello finale non esistono
  più. Riscritto: il profilo C è due persone nel profilo B sullo stesso repository.
- La decisione 3 promette che il nome del progetto resta di chi lavora, mentre
  §7-bis/14 manda al relay il titolo umano, che rivela più dello slug. È una
  **deroga consapevole**, non una svista: il titolo passa dentro un messaggio e non
  entra in nessun archivio, e senza di esso il messaggio sul telefono non sarebbe
  leggibile. Va detto nel Quick Start insieme al limite di §5.
- §4 resta prima di §4-bis pur essendo superata. Chi deriva il grafo di lavoro legge
  **§4-bis, §6-bis, §7-bis e §7-ter**, mai §4 e §6-ter.

**Cosa regge, e va detto**

Il relay senza memoria e senza coda toglie a chi lo gestisce la responsabilità di
custodire lavoro altrui. Il passaggio dell'identità dal grafo all'installazione fa
sparire per costruzione la minaccia che ha aperto questo documento, invece di
difendersene. Il polling al posto del webhook cancella hostname, certificato e porta
aperta. La 28, il lavoro che prosegue sui rami liberi, chiude un difetto vero di
Atlas che esisteva già prima del relay.

**Resta scoperto, e va deciso quando si costruisce**

- La promessa nulla (33) va detta sul bottone che attiva il collegamento, non in una
  riga di documentazione che nessuno legge.
- Chi viene bloccato sa di esserlo (26), però non ha una via per rispondere. Con il
  blocco automatico di §7-ter/4 la via di contatto diventa necessaria.

## 11. Il primo incremento, deciso il 2026-09-02

Nato dalla domanda «inizieresti così, ti senti confidente?». La risposta era no,
perché il disegno era chiuso e il piano di attuazione non esisteva. Dodici domande
dopo esiste.

| # | Domanda | Deciso |
|---|---------|--------|
| 1 | Chi lo usa fra due settimane | Tu e chi inviti tu. Nessuno sconosciuto per ora, però il modello a più installazioni serve dal primo giorno. **Supera la decisione 2 del primo grilling**, che apriva a chiunque. |
| 2 | Che ne facciamo del codice di D01-D08 | Riscrittura chirurgica del solo layer che decide chi è chi (collegamento, riconoscimento, instradamento). Restano la linea aperta, i bottoni, il ritorno del tap e l'aggiornamento del messaggio. |
| 3 | Come entra un invitato | Preme il bottone come tutti, il bot gli dice che serve il via libera, al gestore arriva il nome Telegram e approva con un tap. Nessuna stringa da maneggiare, coerente con §0. |
| 4 | `/view` e i ticket | Per il telefono si costruisce una pagina **senza i testi dentro**: grafo, titoli e stati. §5 resta in piedi e il server non vede mai il contenuto del lavoro. |
| 5 | Le soglie, adesso | Freno automatico oltre un tetto largo per ora, con avviso a entrambi. Il rischio di questa fase non è l'abuso umano, è un Atlas che va in loop e fa limitare il bot. |
| 6 | Cosa entra nel primo giro | La decisione (notifica, bottoni, tap che risolve) **e lo sguardo** (comandi di stato, `/view`). Il resto aspetta l'uso vero. **Supera la decisione 36**, che voleva tutto insieme. |
| 7 | Come si costruisce | Un grafo Atlas nuovo, portato avanti da **Autopilot**. Atlas su Atlas, con i difetti del pilota che vengono a galla mentre serve. |
| 8 | Se il pilota si pianta | Si ripara il pilota e si riparte da lì. Il relay slitta di quanto serve. Ogni intoppo migliora Atlas per sempre, che è la regola Kaizen applicata al prodotto invece che alla sessione. |
| 9 | Lavoro condiviso | Il bot avvisa che qualcosa è cambiato e che conviene aggiornare, **senza dire cosa**. L'allineamento resta git. **Chiude la decisione 7 di §7.** *Rivisto in §11-bis*: serve un codice opaco che viaggia col repository, perché altrimenti il relay non saprebbe chi avvisare. |
| 10 | Chi si invita per primo | Anche colleghi, anche per lavoro, con i progetti sensibili spenti a mano. |
| 11 | Il nome del cliente che parte da solo | **Rischio accettato consapevolmente**: le notifiche restano accese di default (§7-ter/1) e spegnere un progetto riservato è responsabilità di chi lo apre. Sollevata la contraddizione con la 10, la scelta è stata confermata. |
| 12 | Come sappiamo che ha funzionato | Il metro è **quante decisioni hai risolto dal telefono** invece di rimandarle al computer. Se la maggioranza le hai chiuse senza tornare al Mac, il servizio serve e si può aprire. Se sei tornato al Mac lo stesso, il disegno va rifatto prima di aprirlo a chiunque. |

**Ordine di costruzione**

1. Il layer di identità: collegamento per installazione, richiesta di ingresso,
   approvazione del gestore, riconoscimento e instradamento. È la riscrittura
   chirurgica della decisione 2, e tocca `relay/pairing.py` e `relay/tunnel.py`.
2. La notifica con i bottoni e il ritorno del tap, portati sul modello nuovo.
3. Il freno automatico e l'elenco dei computer collegati.
4. I comandi di stato e `/view` con la pagina alleggerita.
5. L'avviso «sei indietro» del lavoro condiviso.
6. Deploy sull'host OCI e due settimane d'uso vero.

**Rischi accettati, scritti perché non si scoprano dopo**

- I progetti di lavoro notificano di default, e la levetta va spenta a mano (11).
- La soglia del freno si sceglie senza dati d'uso, quindi va tenuta molto alta e
  ritarata sui numeri veri alla fine delle due settimane.
- Il codice che sopravvive alla riscrittura chirurgica resta nato per un'idea
  diversa. Va riletto alla fine del primo incremento, non prima.

## 11-bis. Cosa ha cambiato la revisione del grafo

Il grafo di lavoro è stato riletto tre volte prima di essere avviato, su richiesta
esplicita, per equilibrare la granularità. La rilettura ha prodotto cinque
correzioni e ha trovato una contraddizione che il disegno non aveva visto.

**Granularità.** Un nodo faceva due lavori in uno, cioè il formato del messaggio e
la levetta per progetto, che tocca configurazione, dashboard e cataloghi: sono
diventati due nodi. I comandi al bot erano descritti come «il bot risponde a domande
sullo stato», che per un nodo lavorato senza supervisione è abbastanza vago da
produrre codice inventato: ora il nodo pretende un elenco chiuso di comandi.

**Un nodo mancante.** L'identità e il lato relay dell'approvazione avevano il loro
nodo, il lato client del collegamento no. Il bottone discreto, l'attesa del via
libera e l'esito non erano di nessuno. Ora sono un nodo, ed è lì che si dichiara la
promessa nulla di grilling 33, sul bottone che attiva il servizio invece che in una
riga di documentazione.

**I punti scoperti erano finiti nel posto sbagliato.** La promessa nulla e la via di
contatto per chi viene bloccato stavano dentro il nodo finale, che è di verifica:
nessuno le avrebbe costruite. Sono passate nei nodi che le riguardano, cioè il
collegamento e il freno automatico.

**La contraddizione trovata.** L'avviso «un collega ha chiuso un pezzo» richiede che
il relay sappia che due installazioni condividono un progetto, mentre il modello dice
che il relay conosce le installazioni e non i progetti, e la decisione 8 vieta che un
segreto viaggi nel repository. Deciso il 2026-09-02: **il progetto porta con sé un
codice opaco**, uguale su tutte le copie e muto per chi lo legge, con un vincolo
stretto. Quel codice instrada soltanto l'avviso di aggiornamento, e non autorizza a
ricevere una decisione né a risolverla, che restano legate all'installazione. Il
relay continua a non sapere come si chiama un progetto né cosa contiene. Costo
accettato: chi ottiene il repository può mettersi in ascolto di quegli avvisi, che
però non dicono nulla oltre al fatto che qualcosa è cambiato.

**Nota di esecuzione.** I diciassette nodi girano su Claude e non sul default Codex
Luna, perché la quota di quest'ultimo è esaurita fino al 30 settembre 2026. Il nodo
di messa in servizio è AFK come gli altri, e il suo esito atteso è la diagnosi
dell'ambiente, non un deploy inventato.

## 11-ter. Verifica di chiusura del primo incremento (2026-09-03)

Il nodo finale del grafo (`END`) doveva controllare il metro di successo di §11/12
contro il codice davvero scritto, non contro l'intenzione. Quattro controlli,
fatti leggendo il codice riga per riga, non i ticket dei nodi che lo dichiarano
già fatto.

**Il metro di §11/12 non è misurabile, perché non c'è stato uso reale.** Il
metro dice «quante decisioni hai risolto dal telefono invece di rimandarle al
computer». `F01`, il nodo di messa in servizio, non ha effettuato nessun deploy:
mancano tutte le variabili d'ambiente che `deploy.py` pretende, e la sessione non
aveva credenziali ssh verso l'host OCI (porta 22 viva, chiave rifiutata). Non
esiste un bot Telegram vero collegato a questo relay, quindi non esiste una sola
decisione risolta dal telefono da contare. Il criterio non è né superato né
fallito: è un lavoro non ancora cominciato. Il grafo produce codice e 228 test
verdi che coprono l'intero giro a livello di unità e integrazione locale, non la
prova che chiede §11/12. Chi riprende questo lavoro parte da qui: deploy vero,
poi due settimane d'uso, poi si guarda quante volte il telefono è bastato.

**Chi lavora offline vede comunque due cose, per scelta dichiarata del disegno
stesso.** La domanda del nodo chiedeva di controllare che chi lavora offline non
veda comparire niente. Letto `render_notif_telegram.py:39-57` (il blocco è
incluso incondizionatamente da `render_notifiche.panel`, senza nessun gate su
`relay_client.da_ambiente`) e `dashboard.js:49-55` (l'unico gate è
`location.protocol`, cioè `file://` contro un server vero): il bottone «collega
Telegram» e la riga sul carattere sperimentale del servizio sono sempre nel
markup del pannello Notifiche, anche su un'installazione che non ha mai visto
una variabile d'ambiente del relay. Non è un difetto emerso ora: è la decisione
27 di §6-bis, «un bottone discreto e sempre presente», che il documento non
aveva mai riconciliato con la promessa opposta di §0 e del vecchio §2 («non
stampa nulla»). Verificato anche il lato server (`serve_pairing.py:34-42`): un
tap senza relay configurato torna 503 senza che parta nessuna richiesta esterna,
quindi il bottone è visibile ma inerte, non una porta aperta per sbaglio. §0 e §2
sono stati corretti sopra per dire questo con precisione, invece di ripetere una
promessa che il codice non mantiene alla lettera.

**Un progetto spento resta muto: confermato.** `B02` fa dipendere il canale
Telegram da `serve_notify.telegram_abilitato(ref)` dentro
`_canali_attivi`, letto da `config.json` del progetto (`notify.telegram_enabled`,
default `true`); test dedicati coprono l'esclusione del canale a levetta spenta
anche con relay e capability presenti. Un progetto riservato smette di
notificare non appena qualcuno lo spegne dal pannello.

**Il contenuto dei ticket non passa mai dal server: confermato su tre punti
diversi.** `autopilot._card` (che genera il testo di ogni Interazione) usa solo
`node["id"]`/`node["title"]`, mai il file `tickets/<ID>.md`: cercato
`tickets/`, `question` e ogni lettura di ticket in `autopilot.py` e
`notify_telegram.py`, nessuna occorrenza. `render_lite.py` (D02, la pagina che
`/view` manda al telefono) esclude esplicitamente la domanda del nodo e i
riassunti delle Interazioni aperte, non solo il testo del ticket. `B01` compone
il messaggio Telegram come titolo del progetto più titolo del nodo più
etichetta dell'evento, mai un path, mai il corpo del ticket.

**I due punti scoperti di §7-ter sono stati affrontati, non solo citati.** La
promessa nulla di grilling 33 è in `render_notif_telegram.py` come riga fissa
sotto il bottone (`pairing-nota`), a video sempre e non solo dopo il tap, come
chiedeva la correzione. La via di risposta per chi viene bloccato dal freno
automatico è in `C01`: il messaggio di blocco porta un bottone «Chiedi
sblocco» che avvisa il gestore, il quale riceve comunque un «Sblocca» già al
primo blocco senza dover aspettare l'appello.

## 11-ter. Esito del primo run e difetti emersi

Il grafo `260902-atlas-relay` è stato portato a termine da Autopilot il 3 settembre
2026: **diciassette nodi su diciassette**, in sequenziale, con un solo provider
(Claude, perché la quota di Codex era esaurita).

**Il buco che il grafo non copriva.** Il nodo di messa in servizio ha diagnosticato
che il codice riceve gli aggiornamenti Telegram via webhook, mentre il grilling
aveva deciso il polling (decisione 5, che cancellava hostname, certificato e porte
aperte). Nessuno dei diciassette nodi copriva quella conversione: è un errore di
costruzione del grafo, non degli agenti, sfuggito anche alle tre riletture. Va
scritto prima della messa in servizio, perché senza polling il servizio pretende
esattamente l'infrastruttura che il disegno voleva evitare.

**Due difetti di Autopilot, trovati e corretti mentre girava.**

Il primo lo ha visto l'utente guardando la dashboard: il nodo in lavorazione non
appariva mai come tale. Autopilot non rigenerava la dashboard, che si aggiornava
solo quando un agente chiudeva un nodo, cioè nell'istante in cui il successivo non
era ancora rivendicato. Ora la rigenera anche al claim, con un test che verifica
quel che serve davvero, cioè che l'agente al momento di partire trovi già il proprio
nodo marcato come in corso.

Il secondo è emerso a grafo completo: il run restava vivo a ciclare su un risveglio
programmato per un nodo che nel frattempo era stato chiuso a mano. Il ledger dei
tentativi conserva il nodo fallito e non sa che qualcun altro lo ha chiuso, e il
controllo di completamento arrivava dopo l'attesa del backoff invece che prima. Ora
un backoff pendente non tiene in vita un run su un grafo finito.

**Un difetto che resta, e non è nostro da correggere.** Un hook di fine sessione
(`atlas render --all` in `.claude/settings.json`) fa fallire l'agente quando fallisce
lui, quindi il nodo risulta in crash anche a lavoro concluso e scritto sul ticket.
È successo su un nodo che aveva finito il lavoro e lo ha rifatto cinque volte senza
potersi chiudere. Legare l'esito del lavoro a un'operazione accessoria che gira dopo
è fragile per costruzione.

**Una lezione sul monitoraggio.** Un rigeneratore periodico della dashboard, avviato
durante il run per aggirare il primo difetto, prendeva il lock del grafo ogni
quarantacinque secondi e faceva scadere proprio quell'hook. Il rimedio improvvisato
è diventato la causa: durante un run non si prende il lock del grafo per comodità di
visualizzazione.

**Fog aperta.** Il link alla sessione governabile da remoto (§7-bis/12) non ha
ancora una sorgente nel codice: non esiste né una variabile né un concetto di
sessione remota da cui derivarlo. Il messaggio per ora lo omette.

## 8. Alternative scartate

| Scelta | Perché no |
|--------|-----------|
| Slug del grafo come identificatore | Non unico e rivendicabile da chiunque: è il difetto che apre questo documento. |
| Bearer unico per istanza di relay | Chi lo possiede può leggere i grafi di tutti gli altri. |
| Cifratura da un capo all'altro dei testi | Il destinatario finale è Telegram, che deve leggere il messaggio. |
| Firma asimmetrica per non dare le chiavi al relay | Fuori portata senza dipendenze di terze parti. |
| Webhook su IP nudo con certificato autofirmato | Costa l'apertura di una porta come il webhook con dominio, senza il rinnovo automatico del certificato. |

## 9. Prossimi passi

Il grafo di lavoro `260902-atlas-relay` è chiuso: codice e 228 test coprono
l'intero giro chiesto da §11, i due punti scoperti di §7-ter sono costruiti
(§11-ter). Resta da fare, nell'ordine:

1. Il deploy vero sull'host OCI (`F01`, diagnosi soltanto in questo giro): servono
   segreti e credenziali ssh che non stanno in questo repo. Lo scarto che F01
   aveva trovato fra polling promesso (§7/3, grilling 5) e webhook ereditato
   da D04 è chiuso: `G01` ha scritto il long polling verso `getUpdates`, `G02`
   ha smontato l'endpoint `POST /telegram/webhook`, il suo segreto, l'hostname
   HTTPS dedicato e il blocco Caddy che lo esponeva. Nessuna porta nuova serve
   più a ricevere da Telegram. Correzione di `G03`: un hostname pubblico e un
   reverse proxy davanti al servizio restano comunque necessari, non per
   Telegram ma per il tunnel client→relay e il pairing (D03/D05, chiamate in
   ingresso da un client remoto verso `RELAY_PUBLIC_URL`); il blocco Caddy che
   G02 ha tolto esponeva anche quelli, non solo il webhook. Dettaglio in
   `relay/README.md`, "La parte pubblica che resta".
2. Due settimane d'uso vero, poi la lettura del metro di §11/12: quante decisioni
   si sono risolte dal telefono. Prima del deploy quel numero è sempre zero, e non
   è un giudizio sul disegno (§11-ter).
3. Rileggere il codice sopravvissuto alla riscrittura chirurgica e decidere cosa
   resta e cosa si rifà (§11, ordine di costruzione punto 6 mai raggiunto).

## 10. Registro delle iterazioni

- **16 · 2026-09-03** — `G03` rivede la diagnosi di F01 alla luce di G01/G02:
  cosa serve davvero per la messa in servizio non è cambiato quanto la voce
  15 lasciava credere. Confermato: nessun segreto o porta serve più a
  *ricevere* da Telegram (`TELEGRAM_WEBHOOK_SECRET_REF`, hostname dedicato al
  webhook). Corretto: il blocco Caddy che G02 ha tolto (`Caddyfile.atlas-relay`)
  non era dedicato al webhook, faceva `reverse_proxy 127.0.0.1:8765` su ogni
  path, quindi esponeva anche il tunnel client→relay e il pairing (D03/D05).
  Un hostname pubblico, un certificato e un reverse proxy restano necessari
  per quelle due vie, che partono dal client verso `RELAY_PUBLIC_URL`, non da
  Telegram verso il relay. Nessun segreto inventato o stampato, nessun nuovo
  accesso alla macchina richiesto rispetto a quanto F01 aveva già trovato
  (ssh verso l'host OCI, non disponibile in questa sessione). Dettaglio in
  `relay/README.md`, "La parte pubblica che resta".
- **15 · 2026-09-03** — Chiuso il buco trovato da F01 (§11-ter): `G01` ha
  scritto il long polling verso `getUpdates` che alimenta lo stesso
  traduttore di D04 (`telegram_webhook.processa_update`), `G02` ha smontato
  l'endpoint `POST /telegram/webhook`, il segreto del suo header, l'hostname
  HTTPS dedicato e il blocco Caddy che lo esponeva, insieme ai prerequisiti
  che li pretendevano (`TELEGRAM_WEBHOOK_SECRET_REF`, `RELAY_HTTPS_HOSTNAME`
  nei prerequisiti di deploy). L'health check di `deploy.py` passa dalla
  stessa sessione ssh del rollout invece che da un opener HTTPS pubblico. Il
  servizio non ha più nessuna porta pensata per *ricevere* da Telegram,
  verificato bind-side (`127.0.0.1:8765` di default) e non solo dichiarato —
  il tunnel client→relay resta un secondo lato pubblico, corretto dalla voce
  16.
- **17 · 2026-09-03** — Riparato invece che annotato il gap trovato da G03. Il
  reverse proxy esiste di nuovo, ridotto ai sette path che un client deve poter
  chiamare, con 404 su tutto il resto, e un test confronta quell'elenco con i path
  che il servizio serve davvero. Nello stesso controllo e' emerso che il rollout
  copiava una lista di moduli scritta a mano, che ne aveva gia' dimenticati quattro
  in passato e ne dimenticava altri tre: ora la lista viene dalla cartella, e un
  test la verifica. Corretta la decisione 5, che dichiarava la macchina invisibile
  da Internet mentre vale solo per il verso Telegram.
- **14 · 2026-09-03** — Chiusura del primo giro (`END` del grafo
  `260902-atlas-relay`). Il metro di successo di §11/12 non è misurabile perché
  `F01` non ha effettuato nessun deploy: corretto §9 per dirlo. Trovata e sanata
  una contraddizione fra §0/§2 (nessun relay configurato → «non stampa nulla») e
  la decisione 27 di §6-bis (bottone sempre presente, già costruita così da
  `A04`): §0 e §2 riscritti per promettere il silenzio della rete e delle
  notifiche, non l'assenza del bottone di scoperta. Confermati sul codice, non
  solo sui ticket: la levetta per progetto zittisce davvero il canale (`B02`),
  il contenuto dei ticket non raggiunge mai il server su tre percorsi diversi
  (`autopilot._card`, `render_lite.py`, `B01`), ed entrambi i punti scoperti di
  §7-ter sono costruiti (`A04`, `C01`). Dettaglio in §11-ter.
- **14 · 2026-09-03** — Primo run completato, 17 nodi su 17 (§11-ter). Corretti due
  difetti di Autopilot emersi durante la corsa, trovato un buco di copertura del
  grafo (il polling deciso e mai scritto) e registrata la fog sul link alla
  sessione remota.
- **13 · 2026-09-02** — Il grafo di lavoro `260902-atlas-relay` è stato scritto,
  riletto tre volte e avviato con Autopilot. Diciassette nodi. La rilettura ha
  spezzato un nodo che ne conteneva due, precisato un nodo vago, aggiunto il nodo
  mancante del collegamento lato client, spostato i due punti scoperti dove
  qualcuno li costruisce, e trovato la contraddizione dell'avviso condiviso, chiusa
  con il codice opaco di progetto (§11-bis).
- **12 · 2026-09-02** — Secondo grilling, dodici domande su cosa serve per partire
  con confidenza (§11). Il servizio parte chiuso e a invito invece che aperto, il
  primo giro porta la decisione e lo sguardo invece di tutto, il codice esistente si
  corregge nel solo layer di identità, e il criterio di successo è quante decisioni
  si risolvono dal telefono. Chiuse anche le ultime tre righe di §7. Nella stessa
  sessione la funzione «Automata» è stata rinominata **Autopilot** in tutto il
  motore, nei test, nei due README e nei documenti.
- **11 · 2026-09-02** — Critica del documento contro la sola §0. Sei difetti di
  esperienza trovati e corretti (§7-ter), fra cui due contraddizioni letterali con
  §0: la levetta spenta di default e il bot che taceva a lavoro finito. Sanate anche
  tre incoerenze interne rimaste dai passaggi precedenti (§3 requisito 1, §2 profilo
  C, la deroga sul titolo umano). L'architettura non è stata toccata.
- **10 · 2026-09-02** — Chiusi i quattro punti rimasti (§7-bis). Nessuna decisione
  aperta resta sul disegno portante: si puo' passare alla stesura del grafo di lavoro.
- **9 · 2026-09-02** — Grilling concluso, domande 32-36. Nessun processo residente,
  nessuna promessa di continuita', lingua del progetto, indirizzo predefinito ma
  sovrascrivibile, e prima versione completa di bottoni e comandi. Scritta §4-bis, il
  modello che risulta da tutte le risposte: l'identita' passa dal grafo
  all'installazione, e il furto di notifiche per nome omonimo smette di essere un
  problema da difendere.
- **8 · 2026-09-02** — Grilling, domande 26-31. Blocco dichiarato, scoperta senza
  interruzioni, il lavoro che prosegue sui rami liberi, e la levetta per progetto
  spenta di default che si accende alla creazione. Emerge che i gesti sono due e
  non uno: collegare il telefono (una volta per computer) e abilitare un progetto.
- **7 · 2026-09-02** — Grilling, domande 22-25: attesa senza ritentativi, un solo
  protocollo vivo, registri di soli numeri per un mese, console dentro il bot.
- **6 · 2026-09-02** — Ritiro della svolta alla ventunesima: si prosegue con
  Telegram interattivo, perche' il codice esiste gia' e funziona. La sezione 6-ter
  resta come piano B scritto invece di essere cancellata: e' l'uscita d'emergenza
  se un giorno l'interazione costasse piu' di quanto rende.
- **5 · 2026-09-02** — Svolta alla ventesima: la notifica torna a essere solo una
  notifica, con al massimo il link alla sessione remota. Cade tutto il ritorno da
  Telegram verso Atlas, e con esso buona parte del lavoro di D06, D07 e D08, che
  resta in git per l'evolutiva. Il principio invocato: poche cose, fatte bene.
- **4 · 2026-09-02** — Grilling, domande 8-19. Il relay si conferma senza memoria e
  senza coda. Il collegamento del telefono diventa per macchina, dopo che la
  quattordicesima risposta e la sedicesima si sono contraddette e la seconda ha
  vinto. Nasce `/view` con foto della dashboard vera. Nessuna quota preventiva.
- **3 · 2026-09-02** — Grilling a domande singole, ognuna costruita sulla risposta
  precedente. Chiuse le decisioni 1, 2 e 3, aggiunta §6-bis con le prime sette
  risposte. Emergono due funzioni nuove: il bot che risponde a domande e il
  pannello di amministrazione del gestore.
- **2 · 2026-09-02** — Entra la regola di §0, la semplicità disarmante, che diventa
  il primo criterio di giudizio di ogni scelta. Da lì l'invito con blob da
  incollare retrocede ad alternativa di riserva e avanza l'ipotesi che la
  membership segua il repository (§4.2, decisione 8).
- **1 · 2026-09-02** — Primo disegno. Nasce dalla domanda se il bot sia privato e
  se due persone con grafi diversi restino separate. Emergono i due difetti di
  fondo (§1), i tre profili d'uso e il patto sull'attrito (§2), il modello a
  `graphId` più `graphKey` (§4) e il limite di fiducia nel relay (§5).
