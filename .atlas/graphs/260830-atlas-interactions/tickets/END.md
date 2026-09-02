<!-- atlas:auto -->
# END · Chiudi Atlas Interactions

> Ramo: Verifica e consegna · Tipo: task · Modo: AFK
> Bloccato da: E03, D07, D08
> Stato e dipendenze vivono in `../graph.json`, e si cambiano solo con uno script di mutazione.

## Domanda

Verifica che il pannello funzioni senza configurazione, Telegram si colleghi con un solo gesto, il relay OCI non sia fonte di verità e Automata arrivi a END dopo una risposta remota valida. Chiudi la issue #30 solo con evidenza riproducibile.
<!-- /atlas:auto -->

## Lavorazione

Letti tutti i ticket A01-A05, B01-B03, C01-C03, D01-D08, E01-E03 e l'intera nebbia (7 voci) via `atlas fog --list`. Nessuna voce di nebbia orfana: ognuna e' o gia' indirizzata a un nodo chiuso (B01, C01, C02, A05, D01) o riferita al fallback modello (Codex esaurito) o al gap D01/D07 su `callback_data`, gia' risolto da D08 salvo il debito residuo su un deploy mai fatto.

`atlas doctor` sull'intero registro (4 grafi) segnala molte righe "nodo chiuso ma artifact modificato dopo": atteso in un repo dove nodi successivi toccano gli stessi file (es. `dashboard.js`, `serve.py`) senza che questo costituisca scope creep, i ticket dei nodi coinvolti lo motivano gia' uno per uno. Specifico per questo grafo: `END, rivendicato da 33493, verifica nodi che 33493 stessa ha chiuso: E03, D07, D08` (self-check, atteso: stessa sessione ha lavorato la coda del grafo in serie) e artifact non tracciati da git per D07 (`notify_telegram.py`, `test_notify_telegram.py`) e D08 (`capability_store.py`, `test_capability_store.py`, ticket D08.md): nessun commit e' stato fatto durante questo lavoro per mandato esplicito, quindi lo stato uncommitted e' l'esito atteso, non un difetto di questo nodo.

Suite rilanciate con `env -u ATLAS_ROOT -u ATLAS_GRAPH -u ATLAS_IDENTITY -u ATLAS_AUTOMATA_NODE`: `python3 -m unittest discover -s tests` e, dopo `python3 build.py`, `python3 tests/e2e.py` (97/97). Numeri della suite unitaria in Risposta.

## Risposta

### Cosa esiste adesso

La feature Interazioni collega in una sola catena il grafo Atlas e un tap su Telegram. Quando un nodo Automata entra in HITL, un gate si blocca, un run resta fermo o il grafo arriva a END, `automata.py` apre un record nel ledger `interactions` dentro `graph.json` (A03): un'Interaction con contesto, al massimo due azioni consentite, scadenza e idempotency key, scritta nella stessa transazione atomica di ogni altra mutazione Atlas. Da qui la stessa Interaction alimenta due strade indipendenti che non si scavalcano mai a vicenda.

La prima strada è la dashboard locale. `interactions_view.project()` (B01) proietta il ledger senza mai rileggere gli eventi di audit, il pannello Notifiche (B02) la mostra in tre sezioni con card a una frase e bottoni presi 1:1 dalle azioni dichiarate, e un clic parte come `POST /interactions/<id>/<action>` in `atlas serve` (B03), verificato lato server e non solo lato client. Il commit di quella transazione pubblica un `ResolutionEvent` in-process che risveglia Automata senza polling (A05), lo stesso canale che B03 riusa per il bottone quanto A05 lo usa per il tap Telegram.

La seconda strada sono gli avvisi. Un coordinatore comune (`notify.py`, C01) pianifica una consegna per canale registrato con dedup permanente su disco (`NotifyState`) e retry bounded condiviso con Automata. Tre canali senza alcuna configurazione aggiuntiva agganciati alla ronda di `atlas serve`, sistema operativo e browser (C02), più Himalaya per l'email quando `ATLAS_HIMALAYA_TO` è impostato (C03).

Telegram è il quarto canale, e passa dal relay OCI perché un laptop dietro NAT non può ricevere webhook in ingresso. Il pairing one-tap (D05) associa una chat a un progetto con un solo bottone e nessun campo per token o hostname. In uscita, `notify_telegram.TelegramChannel` (D07) costruisce il messaggio con un bottone per azione, emette per ciascuno una capability firmata e monouso (`capability.emetti`, D01/D06) e la spedisce tramite il tunnel client-relay (D03) verso `POST /tunnel/deliver`; il relay risolve il chat_id dal pairing e non vede mai il grafo né la chiave HMAC che firma le capability. In entrata, il tap sul bottone attraversa il webhook Telegram (D04), il relay traduce la capability in un identificativo corto da meno di 64 byte per il campo `callback_data` (D08) e la risolve per intero al momento del tap, il tunnel la consegna al client e `telegram_actions.gestore` la verifica (firma, scadenza, jti monouso) prima di applicarla dentro `mutate.editing`/`resolve_interaction`. Solo a transazione riuscita il messaggio Telegram viene aggiornato con l'esito e Automata riprende. Il relay resta un instradatore puro in ogni punto della catena: non apre, non firma e non risolve mai un'Interaction da solo.

### Cosa è verificato e come

`env -u ATLAS_ROOT -u ATLAS_GRAPH -u ATLAS_IDENTITY -u ATLAS_AUTOMATA_NODE python3 -m unittest discover -s tests` chiude a **772/772 test verdi** in 196 secondi, rilanciata da questo nodo dopo la chiusura di E03/D07/D08. `python3 build.py && python3 tests/e2e.py`, rieseguita nello stesso giro dopo aver rigenerato `dist/atlas`, chiude a **97/97 verifiche passate**.

I test end-to-end di E01 (`tests/test_verifica_e2e_interazioni.py`) usano thread e server HTTP reali, non stub sul lifecycle: provano che un `automata.execute()` bloccato su HITL si sblocca da un vero POST di `atlas serve`, che un secondo POST sulla stessa card torna 409 col run ancora vivo, e la differenza tra un crash a metà attesa (resumable, stesso run_id) e uno stop pulito su HITL (non resumable, run_id nuovo). Il ciclo Telegram inbound (webhook, capability, risoluzione, aggiornamento del messaggio) è provato allo stesso modo con server relay veri-in-locale e fixture (D04, D06, D07, D08), incluso un test end-to-end che assembla deliver, webhook e tunnel condividendo un solo `StoreCapability` come farebbe `atlas_relay.main()` in produzione.

Quello che nessun test tocca è un bot Telegram o un hostname HTTPS reali: ogni scambio con l'API Telegram è mockato o passa da un server locale, e il deploy su OCI è provato solo in isolamento (systemd/Caddy, health check, rollback automatico, D02/E03), mai su una macchina raggiungibile da internet.

### Cosa manca per usarla sul campo

Nessun deploy reale è mai stato fatto, e il gate di A01 resta chiuso in questo ambiente: mancano un bot Telegram approvato con il suo token, un hostname HTTPS pubblico che punti al relay, il deploy vero sulla macchina OCI e la registrazione del webhook presso Telegram. Finché questi quattro pezzi non esistono, la catena descritta sopra ha ogni singolo tratto provato ma nessuno di loro è mai stato messo in comunicazione con un servizio esterno vero.

### Il debito che resta

L'idempotenza del ledger è per run, non per nodo: se un run si ferma su un nodo HITL già notificato e qualcuno rilancia `atlas run` prima di chiudere quel nodo a mano, il run successivo apre un run_id nuovo e con esso una seconda card indipendente per lo stesso nodo, invece di riprendere la prima (scoperto e verificato con codice vero da A05/E01, mai affrontato perché richiederebbe una chiave di idempotenza diversa da quella già scelta in A03).

Il set di azioni resta quello ristretto deciso da A02 (`confirm`/`decline`, `retry`/`cancel`, `acknowledge`), più piccolo del set della issue #30: una scelta di contratto fatta a monte di tutta l'implementazione, non un taglio successivo.

Nove file di `payload/core/` superano le 200 righe senza un'eccezione dichiarata in CLAUDE.md: `automata.py`, `claims.py`, `serve.py`, `strings_cli.py`, `strings_engine.py`, `interactions.py`, `report.py`, `retry.py`, `adapters.py`. Un refactoring di questa portata è una decisione di design che va grigliata a parte, non qualcosa che un nodo di verifica o di chiusura può decidere da solo.

### Le due correzioni di rotta

D07 ha costruito il canale Telegram in uscita che D04 aveva lasciato a metà: D04 aveva già l'adapter lato relay per ricevere un tap, ma nessun nodo prima di D07 chiamava `capability.emetti()` fuori dai test per mandare davvero il primo messaggio con i bottoni. Senza D07 l'anello sarebbe rimasto aperto su un lato solo, un utente poteva rispondere a un messaggio che Atlas non avrebbe mai spedito.

D08 ha corretto un errore di protocollo di D01: la capability firmata pensata in D01 pesa circa 270 byte, e Telegram limita `callback_data` a 64. Il difetto era già presente quando D06 ha iniziato a consumare le capability come `callback_data` per intero, e D07 lo avrebbe spedito così com'è al primo deploy reale, dove ogni tap sarebbe fallito all'invio dell'API Telegram. D08 lo ha chiuso spostando sul relay un identificativo opaco e corto che referenzia il token vero, senza toccare emissione e verifica lato client.

Sono queste due le correzioni che separano una catena dichiarata completa sulla carta da una che, salvo il deploy mai fatto, funzionerebbe davvero al primo tap reale.

### Scelte non canoniche

Nessuna oltre quelle già dichiarate dai singoli nodi. Questo nodo ha solo verificato e sintetizzato, non ha deciso nulla di nuovo sul contratto o sull'implementazione.

### Debito dichiarato

Vedi "Il debito che resta" sopra: idempotenza del ledger per run e non per nodo, set di azioni ridotto rispetto alla issue #30, nove file di `payload/core/` sopra le 200 righe. Nessuno di questi tre punti nasce da questo nodo, tutti erano già dichiarati da A02, A05 ed E03.

### Autorizzazioni ricevute

Nessuna. Nessun commit né push eseguito durante questo lavoro, come da mandato.
