# Relay notifiche, primo giro

> Grafo `260902-atlas-relay` · la verità sta in `graph.json`, questa mappa è la sua faccia leggibile.

## Destinazione

<!-- atlas:auto -->
Notifiche Telegram con decisione e sguardo. Servizio chiuso a invito, identita' per installazione e non per grafo, relay senza memoria del lavoro altrui. Perimetro e ordine in docs/atlas-relay-design.md §11.

## Note

Preferenze permanenti e skill da consultare a ogni sessione.

<!-- atlas:auto -->
- Fonte di verita' del disegno: docs/atlas-relay-design.md. Si leggono §4-bis (modello), §6-bis, §7-bis, §7-ter (decisioni) e §11 (primo incremento). NON si legge §4 ne' §6-ter: sono superate e tenute solo come traccia.
- Il codice di partenza esiste gia' in relay/ e payload/core/ (nodi D01-D08 del grafo 260830-atlas-interactions). §11/2 impone la riscrittura chirurgica del solo layer di identita': si tengono linea aperta, bottoni, ritorno del tap e aggiornamento del messaggio.
- Vincoli invariati di Atlas: sola stdlib, nessuna dipendenza di terze parti, file di payload/core sotto le 200 righe, ogni stringa a video da catalogo t() in italiano e inglese, accenti veri nei cataloghi e ASCII nei commenti del motore. Dopo ogni modifica a payload/ o atlascli/ si rigenera dist/atlas con python3 build.py.
- Vietato 'git stash' in qualunque forma: un lavoro e' gia' andato perso cosi'. Vietato fermarsi ad aspettare la notifica di un comando lanciato in background mentre si tiene un nodo rivendicato: o resta in foreground fino all'esito, o si lavora ad altro sullo stesso nodo.
- Tutti i nodi girano su Claude e non sul default Codex Luna: la quota Codex e' esaurita fino al 30 settembre 2026. F01 e' AFK come gli altri, ma il suo esito atteso e' una diagnosi dell'ambiente, non un deploy inventato.
- Il deploy reale (F01) richiede segreti che non stanno in questo repo. Si verifica l'ambiente, non si inventano risorse ne' si stampano segreti.

## Come si lavora un nodo

Si guarda la frontiera con `atlas status`, si rivendica un nodo con `atlas claim <ID>` prima di toccare qualsiasi cosa, si lavora, si scrive la sezione Risposta del suo ticket e si chiude con `atlas close <ID> -s "sintesi"`, che aggiunge da sé la riga qui sotto. Il contratto completo sta in `.atlas/CONTRACT.md`.

## Decisioni prese

Una riga per nodo chiuso, in ordine di chiusura: quanto basta per giudicarne la rilevanza, poi si apre il ticket.

<!-- atlas:auto -->
- **A01** Definisci l'identita' di installazione: Contratto e modulo client dell'identita' d'installazione verso il relay: nascita del secret, path fuori repo, firma HMAC per-richiesta, versione di protocollo · [ticket](tickets/A01.md)
- **A02** Riscrivi lo store del relay sulle installazioni: Store del relay riscritto su 'chat -> installazione' (SS4-bis): un'installazione ha una chat sola, una chat segue piu' installazioni, nessun nome di progetto o stato di grafo persistito · [ticket](tickets/A02.md)
- **A03** Richiesta d'ingresso e approvazione, lato relay: Cancello d'ingresso lato relay: il gestore nasce da un tap di bootstrap monouso, mai un segreto nel codice, e ogni richiesta resta 'in attesa di via libera' finche' non la approva o la rifiuta con un tap; chi e' rifiutato lo sa · [ticket](tickets/A03.md)
- **A05** Instrada per installazione, non per progetto: Il tunnel instrada per installazione, non per progetto: RegistroTunnel tiene le linee per installation_id, un push mirato e senza coda arriva alla sola linea giusta · [ticket](tickets/A05.md)
- **A04** Il collegamento visto da chi lo usa: Bottone discreto sempre presente nel pannello Notifiche: promessa nulla di grilling 33 sotto il bottone, esiti in parole umane (mai bearer/capability/graphId), gesto spostato da per-progetto a per-installazione · [ticket](tickets/A04.md)
- **B01** Manda la notifica col titolo umano: Il canale Telegram nomina il progetto col titolo umano (mai lo slug), usa la vera identita' d'installazione al posto dello slug come debito lasciato da A05, e la lingua del progetto per testo e bottoni; il link alla sessione remota resta debito dichiarato, in fog. · [ticket](tickets/B01.md)
- **B02** La levetta che zittisce un progetto: Levetta muto Telegram per progetto: accesa di default (SS7-ter/1), un clic dal pannello Notifiche la spegne, invisibile a chi non ha Telegram collegato su questa installazione · [ticket](tickets/B02.md)
- **B03** Porta il ritorno del tap sul modello nuovo: Nessuna modifica di codice: instradamento per installazione, aggiornamento messaggio senza bottoni, potere pieno dei bottoni e limite 64 byte erano gia' tutti verificati e coperti da test, incluso un end-to-end capability-token-reale gia' esistente. · [ticket](tickets/B03.md)
- **B04** Rendi visibile la notifica non consegnata: La mancata consegna di una notifica si legge ora sulla dashboard, accanto al nodo in attesa: rilegge il ledger notify-state.json gia' esistente (nessun ritentativo o coda in piu', grilling 22), non serviva un canale nuovo · [ticket](tickets/B04.md)
- **C01** Freno automatico oltre soglia: Freno automatico per installazione sopra soglia oraria su /tunnel/deliver: 429 e avviso a gestore e macchina fermata al primo sforamento, bottone di appello per chi e' stato fermato · [ticket](tickets/C01.md)
- **C02** Elenco dei computer collegati e distacco: Comando /computer elenca le installazioni della chat con l'ultima volta viste (dal segnale di connessione al tunnel, nessun battito dedicato) e un tap 'Stacca' le dimentica · [ticket](tickets/C02.md)
- **D01** Comandi di stato, con la risposta a Mac spento: Tre comandi di stato al bot (/stato, /aspetta, /storto): il relay li riconosce e instrada senza conservare stato (grilling 7), il client compone la risposta dal ledger locale sulla stessa linea gia' aperta, e se la linea non c'e' il relay dice subito 'non in linea' invece di tacere (S7-ter/2) · [ticket](tickets/D01.md)
- **D02** Vedere il progetto senza spedire i ticket: Comando /view completo su entrambe le uscite: relay/view_command.py instrada la richiesta sulla linea aperta, il client risponde con l'immagine del grafo o con la pagina alleggerita senza i testi dei ticket. Lavoro svolto dall'agente e recuperato a mano: la sessione falliva sull'hook SessionEnd dopo che il lavoro era gia' concluso. · [ticket](tickets/D02.md)
- **E02** Avvisa sul telefono prima di smettere di servire: Avviso Telegram di deprecazione protocollo: header X-Atlas-Protocol (A01) sulla connessione del tunnel, soglia di modulo lato relay (protocol_watch.py, stile throttle.py), un avviso per installazione prima che il relay smetta di servire una versione vecchia · [ticket](tickets/E02.md)
- **E01** Codice muto del progetto e avviso di aggiornare: Codice opaco di progetto (projectCode in config.json, versionato) e /peers/notify sul relay: avviso muto 'qualcosa e' cambiato' fra installazioni che condividono un progetto, senza mai autorizzare a ricevere o risolvere una decisione · [ticket](tickets/E01.md)
- **F01** Metti in servizio il relay e provalo davvero: Diagnosi dell'ambiente per la messa in servizio: codice e 228 test verdi coprono l'intero giro, ma mancano segreti/riferimenti di deploy e credenziali ssh verso l'host OCI, e il codice ereditato e' webhook mentre il disegno aveva deciso polling (fog aperta) · [ticket](tickets/F01.md)
- **END** Chiudi il primo giro del relay: Metro di §11/12 non misurabile (F01 non ha fatto deploy); trovata e sanata in docs/atlas-relay-design.md la contraddizione fra §0/§2 e il bottone sempre visibile (grilling 27); confermati su codice progetto muto, ticket mai al server, e i due punti scoperti di §7-ter affrontati in A04/C01 · [ticket](tickets/END.md)
- **G01** Interroga Telegram invece di aspettarlo: Long polling getUpdates in relay/telegram_polling.py (sola stdlib): stesso traduttore di telegram_webhook.py (processa_update estratto da gestisci), offset persistito su disco, thread demone dentro il servizio · [ticket](tickets/G01.md)
- **G02** Smonta l'ingresso pubblico che non serve piu': Smontato il webhook Telegram (endpoint, secret token, hostname HTTPS, Caddyfile dedicato) e i suoi prerequisiti; il polling di G01 e la verifica di chi puo' entrare restano intatti. Verificato che il servizio non ha nessuna porta raggiungibile da Internet (bind 127.0.0.1, health check ora via ssh). · [ticket](tickets/G02.md)
- **G03** Rimetti in pari la messa in servizio: Corretta la diagnosi di F01/G02: il polling toglie hostname e segreto solo lato Telegram, ma tunnel client-relay e pairing restano un secondo lato pubblico che il Caddy smontato da G02 esponeva anch'esso, e va ricreato · [ticket](tickets/G03.md)
- **H01** Fissa il protocollo, prima di implementarlo: Contratto d'esito chiuso: due strati (graph.json sotto lock per la decisione, run-state.json/log per la diagnostica umana), quattro valori chiusi (done via close esistente, give-up con motivo enum su nuovo data.surrenders, human-needed sopra le Interazioni esistenti con nuovo evento, progress dentro il claim esistente con nuovo campo progress), mutua esclusione per costruzione via store.transaction, verità sempre in graph.json mai nell'exit del processo. · [ticket](tickets/H01.md)
- **H02** L'agente segna dove e' arrivato: Comando 'atlas progress <ID> <PASSO> ["<nota>"]' (H01/4): scrive step+nota dentro il claim gia' esistente, rinfresca solo il battito senza toccare lease_until, non rigenera gli artefatti derivati, e non fa mai fallire il chiamante anche quando il segnale stesso fallisce · [ticket](tickets/H02.md)
- **H03** Il pilota si accorge di un agente fermo: L'attesa del runner e' a fette: ogni fetta guarda claims.silent_for, e uccide per silenzio (status timeout) solo un nodo che ha gia' dichiarato un passo (H01/4) e poi si ferma oltre un'ora; senza alcun passo dichiarato resta solo il tetto assoluto invariato (crash a 90 min). · [ticket](tickets/H03.md)
- **H04** L'agente puo' arrendersi, e il pilota lo ascolta: atlas give-up (claims.give_up): resa terminale con motivo chiuso, intercettata prima di ambiguous-termination, distinguibile in run-log e run-status · [ticket](tickets/H04.md)
- **H05** L'agente puo' chiedere una persona senza sprecare tentativi: Esito 'serve una persona' (H01/3) sopra le Interazioni esistenti: claims.ask_human apre la card e rilascia il claim in una transazione, claim()/frontier() rifiutano di riprendere il nodo finche' resta aperta, il runner non la conta come fallimento e si ferma con una diagnosi dedicata invece del generico invalid_termination · [ticket](tickets/H05.md)
- **H06** Scrivi il protocollo dove l'agente lo legge: Il protocollo di esito di H01 (close/give-up/ask-human/progress) e' scritto nel briefing del figlio, nel contratto it/en, e ereditato da atlas how-to e dalla skill atlas-work in entrambe le lingue, con dist/atlas e il contratto di questo progetto rigenerati · [ticket](tickets/H06.md)
- **H07** Prova il protocollo su un guasto vero: Prova end-to-end sui tre guasti del 2026-09-03: silenzio (H03) e resa (H04) reggono come progettato; il crash dopo lavoro scritto no, e viene corretto con un nuovo esito 'orphaned-answer' (non ritentabile, un tentativo solo). · [ticket](tickets/H07.md)

## Non ancora specificato

Quel che è emerso e non ha ancora un nodo. Si appunta con `atlas fog "una riga"`.

<!-- atlas:auto -->
- SS7-bis/12 chiede in fondo al messaggio Telegram il link alla sessione governabile da remoto, quando esiste: nel codice non c'e' ancora nessuna sorgente per quel link (nessun env var, nessun concetto di 'sessione governabile da remoto'). B01 lascia il messaggio senza quella riga; va deciso da dove viene il link prima di aggiungerla, e a quale nodo appartiene (forse B03, il ritorno del tap sul modello nuovo).
- 33 test preesistenti falliscono nel working tree (test_conflicts/test_drift/test_due_cloni/test_edges/test_heartbeat/test_motore, lock/lease/identity/fog): non toccati da B02, cli.py/identity.py/claims.py risultano gia' modificati da altro lavoro in corso
- per G03: relay/deploy.py:rilascia() 'sorgenti' non porta sul remote peers.py, protocol_watch.py e view_command.py, importati da atlas_relay.py (E01/E02/D02): stesso buco gia' successo tre volte prima (vedi commento del modulo), stavolta non trovato da un deploy fallito ma leggendo il codice mentre G01 aggiungeva telegram_polling.py alla stessa lista.
- per F01: G03: il tunnel client-relay e il pairing (D03/D05) restano raggiungibili solo con un reverse proxy pubblico davanti a 127.0.0.1:8765, che G02 ha tolto insieme al webhook (Caddyfile.atlas-relay esponeva tutto il servizio, non solo il webhook). Va ricreato un blocco Caddy (o equivalente) e scelto un hostname prima del deploy vero, o deciso di lasciarlo fuori dal repo come passo manuale: decisione non presa qui.
- report.show_brief non mostra le rese passate (data["surrenders"]) su un nodo, solo le releases: chi riprende un nodo gia' abbandonato una volta non lo scopre finche' non rilegge run-log

## Fuori scopo

Quel che sta oltre la destinazione, e il perché.

<!-- atlas:auto -->
_niente, per ora._
