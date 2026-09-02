# Atlas Relay — servizio isolato (D02), tunnel (D03), adapter Telegram (D04), pairing (D05), inoltro azioni (D06)

Non fa parte del prodotto Atlas (`payload/`, `atlascli/`): è infrastruttura reale,
un servizio a parte da distribuire sull'host OCI che già ospita il bot WhenAGI e
Claude Proxy, senza toccarli.

## Cosa c'è qui

- `atlas_relay.py` — il servizio: stdlib pura, endpoint `/healthz` sempre attivo,
  `GET /tunnel` (D03, il tunnel client→relay), `POST /tunnel/tap-result` (D06,
  il client chiede di aggiornare un messaggio Telegram dopo aver risolto
  un'Interaction, stesso bearer del tunnel), `POST /telegram/webhook` (D04,
  disattivato per costruzione finché `TELEGRAM_BOT_TOKEN_REF`/
  `TELEGRAM_WEBHOOK_SECRET_REF` non sono nell'ambiente) e `POST`/`GET /pairing`
  (D05, disattivato finché `TELEGRAM_BOT_TOKEN_REF`/`TELEGRAM_BOT_USERNAME` non
  ci sono). Bind di default su `127.0.0.1`. `main()` collega il sink del
  webhook (D06, `tunnel.costruisci_instradamento`) al `RegistroTunnel` solo se
  pairing e tunnel sono entrambi configurati; altrimenti resta il sink di
  default (`telegram_webhook.CodaTap`).
- `telegram_webhook.py` — l'adapter (D04): verifica l'header
  `X-Telegram-Bot-Api-Secret-Token` (prova che la chiamata viene davvero da
  Telegram, non solo che è HTTPS), rifiuta le chat non associate a un progetto
  (`PairingStore`, implementato da `pairing.GestorePairing`, D05), deduplica le
  redelivery per `update_id`, risponde `answerCallbackQuery` subito, e
  riconosce un messaggio `/start <codice>` come pairing (D05) invece che come
  tap da inoltrare. Payload minimo: mai il corpo completo dell'update Telegram
  oltre il confine del relay. `costruisci_modifica_messaggio` (D06) chiama
  `editMessageText` e toglie i bottoni dal messaggio aggiornato, cosi' un
  secondo tap sullo stesso messaggio non genera un altro evento.
- `pairing.py` — il pairing one-tap (D05): un codice monouso per progetto
  (`GestorePairing.richiedi`), consumato da un `/start <codice>` su Telegram
  (`conferma`, monouso per costruzione), persistito su disco (JSON, sopravvive
  a un restart del servizio) e interrogabile per stato dal pannello Notifiche
  del client (`GET /pairing?code=`).
- `tunnel.py` — il lato relay del tunnel D03: bearer di progetto
  (`verifica_bearer`) e `RegistroTunnel`, le code aperte in memoria per sessione
  `(graph, runId)`. Nessuna coda di rimessaggio: un `push` verso una sessione
  non connessa in quel momento si perde, per costruzione (D01).
  `RegistroTunnel.sessioni_di(graph)` e `costruisci_instradamento` (D06)
  risolvono a quale sessione spingere un tap gia' associato a un progetto:
  il pairing e' per progetto (D05), non per sessione, quindi il sink lo
  spinge a ogni runId connesso in quel momento per quel progetto.
- `atlas-relay.service` — unit systemd dedicata: utente di sistema proprio
  (`atlas-relay`), `ProtectSystem=strict`, nessuna condivisione di processo, porta
  o percorso con le unit esistenti.
- `Caddyfile.atlas-relay` — blocco Caddy isolato, un hostname proprio
  (`RELAY_HTTPS_HOSTNAME`) instradato alla porta locale del servizio; si importa
  nel Caddyfile principale, non lo sostituisce.
- `deploy.py` — orchestratore: rollout su una directory versionata sul remote
  (i quattro moduli sopra), restart della unit, health check via HTTPS pubblico
  e rollback automatico sull'ultimo rilascio funzionante se il nuovo non
  risponde.

## Stato del deploy reale

`deploy.py` verifica gli stessi prerequisiti dichiarati da A01/D01 prima di
muovere qualunque cosa: `RELAY_HTTPS_HOSTNAME`, `ATLAS_RELAY_TOKEN_REF`, più
`ATLAS_RELAY_DEPLOY_HOST` (bersaglio ssh, `utente@host`) e
`ATLAS_RELAY_DEPLOY_PATH` (directory base sul remote), che D02 aggiunge alla
stessa lista. A01 ha già trovato l'ambiente privo di bot Telegram approvato e di
hostname HTTPS; questa sessione lo riconferma (nessuna delle variabili sopra è
dichiarata qui). Il deploy quindi non è stato eseguito contro l'host OCI reale:
farlo partire avrebbe richiesto scegliere hostname, bersaglio ssh o segreti da
sola, esattamente ciò che A01 vieta.

Codice e template sono completi e pronti: una volta che i riferimenti sopra
sono dichiarati nell'ambiente di chi esegue, il deploy si lancia con

```sh
RELAY_HTTPS_HOSTNAME=... ATLAS_RELAY_TOKEN_REF=... \
ATLAS_RELAY_DEPLOY_HOST=utente@host ATLAS_RELAY_DEPLOY_PATH=/opt/atlas-relay \
python3 relay/deploy.py <versione>
```

Il webhook Telegram (D04) ha un gate proprio, verificato a ogni avvio del
processo (`costruisci_gestore_da_ambiente`, non da `deploy.py`, perché è il
servizio in esecuzione a doverlo controllare, non l'orchestratore di rollout):
`TELEGRAM_BOT_TOKEN_REF` e `TELEGRAM_WEBHOOK_SECRET_REF`, gli stessi due nomi
già richiesti da A01. Nessuno dei due è dichiarato in questo ambiente: il
servizio parte comunque (`/healthz` resta attivo), ma `/telegram/webhook`
risponde 404 finché quei riferimenti non ci sono.

Il pairing (D05) ha un secondo gate, verificato anch'esso a ogni avvio
(`pairing.costruisci_da_ambiente`): `TELEGRAM_BOT_TOKEN_REF` (per mandare il
messaggio di esito su Telegram) e `TELEGRAM_BOT_USERNAME` (per costruire il
deep link `https://t.me/<username>?start=<codice>`, il nome pubblico del bot
non è nell'ambiente per nessun altro motivo finora). Nessuno dei due è
dichiarato in questo ambiente: `POST`/`GET /pairing` rispondono 404. Lo stato
del pairing (chi si è associato) è persistito in un file JSON accanto al
codice del servizio (`ATLAS_RELAY_STATE_DIR`, opzionale: di default un
sottodirectory `state/` scrivibile sotto `ReadWritePaths` della unit
systemd), non solo in memoria di processo: un restart del servizio non
scollega chi si era già associato.

## Verifica fatta qui

`tests/test_relay.py`: il gate dei prerequisiti di deploy (rifiuta senza le
variabili, passa con tutte dichiarate), l'health check con backoff (successo,
fallimento dopo N tentativi), il rollback automatico quando il nuovo rilascio
non risponde (verificato sui comandi ssh/systemctl emessi, senza rete né host
reali), il servizio stesso (`/healthz` risponde 200, ogni altro path risponde
404), e la traduzione HTTP degli endpoint `/tunnel` e `/pairing` (401/400/404
a seconda del caso).

`tests/test_telegram_webhook.py`: il gate del webhook (nessun gestore senza
i due riferimenti, gestore costruito con entrambi), la verifica del secret
token (accetta il valore giusto, rifiuta assente/sbagliato senza timing
leak), l'estrazione dell'evento minimo da un update Telegram vero (incluso il
testo, per riconoscere un `/start`), il rifiuto di una chat non associata con
`answerCallbackQuery` comunque chiamato prima del rifiuto, la deduplica per
`update_id` su una redelivery, il routing di un `/start <codice>` verso
`pairing_start` invece che verso il sink, e l'integrazione HTTP end-to-end su
`atlas_relay.Handler` (200/401/404 a seconda del caso, mai una risposta
diversa che riveli perché una chat è stata scartata).

`tests/test_pairing.py`: `GestorePairing` in isolamento (codice fresco,
conferma che associa e torna il progetto, monouso — un secondo tentativo con
lo stesso codice fallisce —, scadenza, persistenza su disco fra istanze
diverse), e `costruisci_pairing_start` (il messaggio di esito, valido o no).

`tests/test_tunnel.py` (D06): `RegistroTunnel.sessioni_di` e
`costruisci_instradamento` in isolamento (instrada a ogni sessione connessa
del progetto giusto, ignora una chat non associata, un progetto senza
tunnel aperto perde l'evento). `tests/test_telegram_webhook.py` (D06):
`costruisci_modifica_messaggio` (chiama `editMessageText` col testo e senza
bottoni, un `URLError` non risale al chiamante). `tests/test_relay.py`
(D06): l'endpoint `/tunnel/tap-result` (200/401/400/404) e un test end-to-end
(`InoltroTapEndToEnd`) che assembla webhook, sink e `RegistroTunnel` come
farebbe `main()` e verifica che un tap di una chat associata arrivi come
frame `event: tap` sulla sessione giusta.
