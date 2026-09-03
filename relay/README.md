# Atlas Relay — servizio isolato (D02), tunnel (D03), adapter Telegram (D04), pairing (D05), inoltro azioni (D06)

Non fa parte del prodotto Atlas (`payload/`, `atlascli/`): è infrastruttura reale,
un servizio a parte da distribuire sull'host OCI che già ospita il bot WhenAGI e
Claude Proxy, senza toccarli.

## Cosa c'è qui

- `atlas_relay.py` — il servizio: stdlib pura, endpoint `/healthz` sempre attivo,
  `GET /tunnel` (D03, il tunnel client→relay), `POST /tunnel/tap-result` (D06,
  il client chiede di aggiornare un messaggio Telegram dopo aver risolto
  un'Interaction, stesso bearer del tunnel) e `POST`/`GET /pairing` (D05,
  disattivato finché `TELEGRAM_BOT_TOKEN_REF`/`TELEGRAM_BOT_USERNAME` non ci
  sono). Bind di default su `127.0.0.1`, nessuna porta aperta dal processo
  stesso: gli aggiornamenti Telegram arrivano dal long polling di
  `telegram_polling.py` (G01), non da un endpoint HTTP esposto (G02). Il
  tunnel e il pairing restano invece chiamate in ingresso da un client
  remoto e per quelle serve ancora un reverse proxy pubblico davanti al bind
  locale — vedi "La parte pubblica che resta" più sotto. `main()` collega il
  sink del traduttore (D06,
  `tunnel.costruisci_instradamento`) al `RegistroTunnel` solo se pairing e
  tunnel sono entrambi configurati; altrimenti resta il sink di default
  (`telegram_webhook.CodaTap`).
- `telegram_webhook.py` — il traduttore (D04): `GestoreWebhook.processa_update`
  rifiuta le chat non associate a un progetto (`PairingStore`, implementato da
  `pairing.GestorePairing`, D05), deduplica le redelivery per `update_id`,
  risponde `answerCallbackQuery` subito, e riconosce un messaggio
  `/start <codice>` come pairing (D05) invece che come tap da inoltrare.
  Payload minimo: mai il corpo completo dell'update Telegram oltre il confine
  del relay. `costruisci_modifica_messaggio` (D06) chiama `editMessageText` e
  toglie i bottoni dal messaggio aggiornato, cosi' un secondo tap sullo stesso
  messaggio non genera un altro evento.
- `telegram_polling.py` — il long polling verso `getUpdates` (G01): alimenta
  `processa_update` con gli update gia' decodificati da Telegram stesso,
  nessun segreto da verificare perche' e' questo processo a chiamare
  Telegram, non il contrario (decisione di disegno §7/3, grilling 5: nessuna
  porta aperta, nessun hostname pubblico, nessun certificato). L'offset
  dell'ultimo update consegnato e' persistito su disco, un thread demone
  dentro `atlas_relay.main()`, nessun secondo processo.
- `pairing.py` — il pairing one-tap (D05/A02) e il cancello d'ingresso (A03):
  un codice monouso per installazione (`GestorePairing.richiedi`), consumato
  da un `/start <codice>` su Telegram (`richiedi_ingresso`, monouso per
  costruzione). Il servizio e' chiuso (S11/3): la richiesta resta 'in attesa
  di via libera' finche' il gestore non la approva o la rifiuta con un tap
  (`approva`/`rifiuta`), mai una stringa da digitare per nessuno dei due. Il
  gestore stesso non e' un valore scritto nel codice ne' indovinabile: nasce
  da un tap su un deep link di bootstrap monouso (`emetti_bootstrap_gestore`/
  `conferma_gestore`), emesso una sola volta da `bootstrap_gestore.py`. Tutto
  persistito su disco (JSON, sopravvive a un restart del servizio) e
  interrogabile per stato dal pannello Notifiche del client
  (`GET /pairing?code=`).
- `bootstrap_gestore.py` — comando locale (A03), si lancia una sola volta
  sull'host del servizio, subito dopo il deploy: stampa il deep link t.me da
  aprire sul telefono di chi deve diventare gestore. Se un gestore e' gia'
  registrato non stampa nulla di nuovo.
- `tunnel.py` — il lato relay del tunnel D03: bearer (`verifica_bearer`) e
  `RegistroTunnel`, le code aperte in memoria per installazione (A05,
  SS4-bis: mai per progetto). Nessuna coda di rimessaggio: un `push` verso
  un'installazione senza linea aperta in quel momento si perde, per
  costruzione (D01, grilling 8), e chi ha premuto lo scopre subito (SS7-bis/13).
  `costruisci_instradamento` (D06) risolve a quale installazione spingere un
  tap gia' associato a una chat (`pairing.installazioni_di`) e lo spinge
  sulla sola linea aperta di quella installazione, a nessun'altra.
- `peers.py` — l'avviso "qualcosa e' cambiato" fra installazioni che
  condividono un progetto (E01, `POST /peers/notify`, stesso bearer del
  tunnel). La chiave e' il codice opaco che il progetto porta con se'
  (`payload/core/project_code.py`, versionato in `config.json`): il relay non
  impara mai il nome ne' il contenuto del progetto, `RegistroPeer` ricorda
  solo quali installazioni hanno gia' avvisato per quel codice.
  `costruisci_avviso` registra chi avvisa e spinge un testo fisso e muto
  (`TESTO_AVVISO`, mai il nome del progetto o del nodo) a ogni pari gia' noto
  che ha una chat associata (`pairing.chat_id_di`): nessuna capability nasce
  da qui, sapere chi avvisare non e' potere ricevere o risolvere una
  decisione.
- `atlas-relay.service` — unit systemd dedicata: utente di sistema proprio
  (`atlas-relay`), `ProtectSystem=strict`, nessuna condivisione di processo, porta
  o percorso con le unit esistenti.
- `deploy.py` — orchestratore: rollout su una directory versionata sul remote
  (i moduli sopra), restart della unit, health check via la stessa sessione
  ssh (nessuna porta pubblica da bussare, G02) e rollback automatico
  sull'ultimo rilascio funzionante se il nuovo non risponde.

## Stato del deploy reale

`deploy.py` verifica gli stessi prerequisiti dichiarati da A01/D01 prima di
muovere qualunque cosa: `ATLAS_RELAY_TOKEN_REF`, più `ATLAS_RELAY_DEPLOY_HOST`
(bersaglio ssh, `utente@host`) e `ATLAS_RELAY_DEPLOY_PATH` (directory base sul
remote), che D02 aggiunge alla stessa lista. `TELEGRAM_WEBHOOK_SECRET_REF` non
serve più (G02): quel segreto proteggeva l'endpoint che riceveva da Telegram,
e con il polling (G01) è il relay a chiamare Telegram, mai il contrario.
`RELAY_HTTPS_HOSTNAME` non è più un prerequisito **di `deploy.py`**, che copia
i moduli e riavvia la unit senza mai toccare il proxy. Resta però necessario
**nell'ambiente del processo Caddy**, perché `Caddyfile.atlas-relay` lo legge da
lì con `{$RELAY_HTTPS_HOSTNAME}`: senza, il blocco non dichiara nessun hostname
e i client non raggiungono il relay. Vedi "La parte pubblica che resta". A01 ha già trovato l'ambiente
privo di bot Telegram approvato; questa sessione lo riconferma (nessuna delle
variabili sopra è dichiarata qui). Il deploy quindi non è stato eseguito
contro l'host OCI reale: farlo partire avrebbe richiesto scegliere bersaglio
ssh o segreti da sola, esattamente ciò che A01 vieta.

Codice e template sono completi e pronti: una volta che i riferimenti sopra
sono dichiarati nell'ambiente di chi esegue, il deploy si lancia con

```sh
ATLAS_RELAY_TOKEN_REF=... \
ATLAS_RELAY_DEPLOY_HOST=utente@host ATLAS_RELAY_DEPLOY_PATH=/opt/atlas-relay \
python3 relay/deploy.py <versione>
```

Il traduttore Telegram (D04, alimentato dal long polling di G01) ha un gate
proprio, verificato a ogni avvio del processo
(`costruisci_gestore_da_ambiente`, non da `deploy.py`, perché è il servizio in
esecuzione a doverlo controllare, non l'orchestratore di rollout):
`TELEGRAM_BOT_TOKEN_REF`, lo stesso nome già richiesto da A01. Se manca, il
servizio parte comunque (`/healthz` resta attivo), ma il thread di polling
non si avvia.

Il pairing (D05) ha un secondo gate, verificato anch'esso a ogni avvio
(`pairing.costruisci_da_ambiente`): `TELEGRAM_BOT_TOKEN_REF` (per mandare il
messaggio di esito su Telegram) e `TELEGRAM_BOT_USERNAME` (per costruire il
deep link `https://t.me/<username>?start=<codice>`, il nome pubblico del bot
non è nell'ambiente per nessun altro motivo finora). Nessuno dei due è
dichiarato in questo ambiente: `POST`/`GET /pairing` rispondono 404. Lo stato
del pairing (chi si è associato, chi è in attesa di via libera, chi è il
gestore) è persistito in un file JSON accanto al codice del servizio
(`ATLAS_RELAY_STATE_DIR`, opzionale: di default un sottodirectory `state/`
scrivibile sotto `ReadWritePaths` della unit systemd), non solo in memoria di
processo: un restart del servizio non scollega chi si era già associato né
dimentica chi è il gestore.

Il gestore (A03) va bootstrappato a mano, una volta sola, dopo che il pairing
è configurato: `ssh <host> 'cd <deploy-path>/current && python3
bootstrap_gestore.py'` stampa il deep link da aprire sul telefono di chi deve
approvare gli ingressi. Nessun gestore è dichiarato finché quel comando non
viene lanciato: ogni richiesta di ingresso arrivata prima resta segnata
`senza_gestore` invece di restare sospesa per sempre.

### La parte pubblica che resta

Il polling toglie l'ingresso pubblico da un lato solo, e conviene dirlo con
precisione perché il disegno lo aveva scritto in modo più largo del vero.

**Cosa il polling ha tolto davvero.** La direzione Telegram→relay: prima
arrivava un webhook, ora è il relay a chiamare `getUpdates` in uscita. Con
essa cadono il secret token dell'header, `setWebhook`, il vincolo sulle porte
che Telegram accetta e la necessità che il certificato sia valido per lui.

**Cosa resta pubblico, e non è mai stato del webhook.** Il tunnel client→relay
(`payload/core/relay_client.py`) e il pairing (`payload/core/serve_pairing.py`)
sono chiamate che partono dalla macchina di chi usa Atlas verso
`RELAY_PUBLIC_URL`/`RELAY_HTTPS_HOSTNAME`, un URL `https://` letto
dall'ambiente del progetto e mai cablato nel codice
(`relay_client.da_ambiente`). Il servizio è `http.server` senza TLS, in ascolto
su `127.0.0.1:8765`: senza un reverse proxy davanti nessun client remoto lo
raggiunge, per quanto gli update Telegram arrivino in uscita.

**Come è risolto.** `Caddyfile.atlas-relay` esiste di nuovo, e non è il
catch-all di prima: elenca i sette path che un client deve poter chiamare
(`/healthz`, `/tunnel`, `/tunnel/tap-result`, `/tunnel/deliver`,
`/tunnel/deliver-file`, `/pairing`, `/peers/notify`) e risponde 404 a tutto il
resto, così la superficie esposta è solo quella che serve e un endpoint nuovo
non finisce su Internet per distrazione. `tests/test_relay.py`
(`SuperficiePubblica`) confronta quell'elenco con i path che il servizio serve
davvero e fallisce se i due divergono, in un verso o nell'altro.

**Cosa serve ancora da una persona, e non può venire da qui:** un hostname
pubblico con il suo DNS verso l'host, e il certificato che Caddy ottiene da
solo una volta che l'hostname esiste. Sono scelte di chi fa il deploy, non di
un agente.

## Verifica fatta qui

`tests/test_relay.py`: il gate dei prerequisiti di deploy (rifiuta senza le
variabili, passa con tutte dichiarate), l'health check via ssh con backoff
(successo, fallimento dopo N tentativi), il rollback automatico quando il
nuovo rilascio non risponde (verificato sui comandi ssh/systemctl emessi,
senza rete né host reali), il servizio stesso (`/healthz` risponde 200, ogni
altro path incluso il vecchio `/telegram/webhook` risponde 404), e la
traduzione HTTP degli endpoint `/tunnel` e `/pairing` (401/400/404 a seconda
del caso).

`tests/test_telegram_webhook.py`: il gate del traduttore (nessun gestore
senza `TELEGRAM_BOT_TOKEN_REF`, gestore costruito con quello dichiarato),
l'estrazione dell'evento minimo da un update Telegram vero (incluso il
testo, e il nome del mittente solo su un `/start`, per il messaggio al
gestore di A03), il rifiuto di una chat non associata con
`answerCallbackQuery` comunque chiamato prima del rifiuto, la deduplica per
`update_id` su una redelivery, il routing di un `/start <codice>` verso
`pairing_start` (con codice, chat e nome) invece che verso il sink, e il
routing di un callback verso `admin_decision` prima del cancello
`is_paired` (fermato se gestito, altrimenti il percorso normale prosegue).

`tests/test_pairing.py`: `GestorePairing` in isolamento (codice fresco,
`richiedi_ingresso` che sospende senza associare, `approva`/`rifiuta` che
risolvono una sola volta ciascuno, scadenza, persistenza su disco fra istanze
diverse), il bootstrap del gestore (emissione idempotente, reclamo monouso,
nessun secondo gestore), `costruisci_pairing_start` (bootstrap, richiesta con
o senza gestore configurato, codice invalido) e `costruisci_admin_decision`
(approva/rifiuta, tap da chi non è il gestore assorbito senza traccia, doppio
tap senza secondo effetto). `tests/test_pairing.py` copre anche
`bootstrap_gestore.py` (link valido, nessun prerequisito, gestore già
presente).

`tests/test_tunnel.py` (D06/A05): `RegistroTunnel` e `costruisci_instradamento`
in isolamento (instrada alla sola linea dell'installazione risolta e a
nessun'altra, ignora una chat non associata, un'installazione senza tunnel
aperto perde l'evento). `tests/test_telegram_webhook.py` (D06):
`costruisci_modifica_messaggio` (chiama `editMessageText` col testo e senza
bottoni, un `URLError` non risale al chiamante). `tests/test_relay.py`
(D06): l'endpoint `/tunnel/tap-result` (200/401/400/404) e un test end-to-end
(`InoltroTapEndToEnd`) che assembla traduttore, sink e `RegistroTunnel` come
farebbe `main()` e verifica che un tap di una chat associata arrivi come
frame `event: tap` sulla linea dell'installazione giusta.

`tests/test_telegram_polling.py` (G01): `OffsetStore` (persistenza atomica su
disco), `_get_updates` e `ciclo_polling` (dedup per `update_id`, avanzamento
dell'offset dopo ogni update, backoff fisso su errore di rete o risposta
malformata), l'avvio/arresto del thread demone. Nessuna rete reale: `opener`
sempre iniettato.
