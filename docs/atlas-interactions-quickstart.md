# Interazioni Atlas: quick start e diagnostica

Un'**Interaction** è la richiesta puntuale con cui Atlas interrompe una persona:
una decisione (nodo HITL o gate), un run fermo (blocco non recuperabile o
retry esauriti) o una fine rilevante (END, o un fallimento terminale). Il
contratto completo, stati, azioni consentite e testi delle card, è nella
Risposta di [A02](../.atlas/graphs/260830-atlas-interactions/tickets/A02.md).
Questa pagina è il percorso pratico: come vedere il primo alert, come collegare
Telegram con un bottone, come capire che una consegna non è arrivata. I
dettagli di relay e sicurezza restano fuori dal percorso principale e stanno
nella sezione Diagnostica in fondo.

## Quick start, due minuti

### 1. Vedi il primo alert

Serve un grafo Atlas con un nodo `HITL` raggiungibile, questo stesso progetto
ne ha diversi. In un terminale tieni viva la dashboard:

```sh
atlas serve
```

In un altro avvia un run:

```sh
atlas run --parallelism 1
```

Quando Automata arriva al nodo HITL apre l'Interaction: la card compare nel
pannello **notifiche** della dashboard, sotto **attenzione richiesta**, col
testo `Serve una decisione per <nodo>.` e i bottoni `Conferma`/`Rifiuta`. Nello
stesso momento arrivano, senza nessuna configurazione:

- un **avviso di sistema** (`notify_local.py`: `osascript` su macOS,
  `notify-send` su Linux, un balloon su Windows), sempre attivo perché non
  chiede né credenziali né setup;
- un **avviso browser**, se la dashboard è aperta e ha il permesso di
  notifica del browser concesso: clicca l'avviso e la pagina scorre fino alla
  card.

Se in ambiente è dichiarato `ATLAS_HIMALAYA_TO` (e opzionalmente
`ATLAS_HIMALAYA_ACCOUNT`), lo stesso evento arriva anche per email via
`himalaya message send`: è il canale pensato per chi non ha lo schermo
davanti, non un duplicato del pannello. Senza quella variabile il canale non
viene nemmeno pianificato, per costruzione: niente tentativi falliti in
silenzio.

Rispondi dal pannello (`Conferma` o `Rifiuta`): il run riprende da solo senza
polling, e la card passa a **risolte oggi**.

### 2. Collega Telegram con un bottone

In cima al pannello notifiche c'è un solo bottone, **collega Telegram**,
senza campi da compilare: nessun token bot, chat ID o hostname da inserire a
mano. Un clic chiede al relay un codice monouso; se lo ottiene, la dashboard
mostra il link `https://t.me/<bot>?start=<codice>` da aprire e resta in
attesa (`apri Telegram e premi Avvia per completare`), interrogando lo stato
finché non arriva `Telegram collegato` o il codice scade.

Perché il bottone funzioni serve un Atlas Relay già raggiungibile, con bot e
pairing configurati: in questo ambiente non c'è (vedi Diagnostica), quindi
oggi il clic torna l'errore generico `non è andata: riprova` invece del link
da aprire (il server risponde 503, perché `relay_client.da_ambiente` non
trova `RELAY_PUBLIC_URL`/`RELAY_HTTPS_HOSTNAME` né `ATLAS_RELAY_TOKEN_REF`
nell'ambiente di chi esegue `atlas serve`). Il codice del pairing è pronto e
testato (`payload/core/serve_pairing.py`, `relay/pairing.py`), il gate è lo
stesso che riguarda l'intero relay, non un difetto di questo passo.

**Anche a pairing completato, oggi nessun messaggio Telegram parte da solo.**
Un tap su un bottone di un messaggio Telegram già esistente arriva fino al
lifecycle Atlas (capability verificata, Interaction risolta, messaggio
aggiornato), ma niente costruisce e invia quel primo messaggio con i bottoni:
è il gap aperto in [fog](../.atlas/graphs/260830-atlas-interactions/map.md)
da D06, nessun nodo di questo grafo lo copre. Finché non esiste, Telegram è
un canale di risposta, non ancora un canale di alert.

### 3. Capisci una consegna mancata

Una card che non ha raggiunto nessuno resta comunque nel grafo: niente sparisce
in silenzio.

- **Pannello notifiche**: una card ancora `open` mostra quanto manca alla
  scadenza (`scade tra <t>`) o da quanto è scaduta (`scaduta da <t>`); il
  `<details>` **registro** della card elenca apertura, risposta o scadenza con
  l'orario. Attenzione: lo stato passa a `expired` solo quando Automata
  ritorna a controllare quella card (nel suo giro di attesa), non da solo a
  orologio: un run fermo non riletto la lascia `open` anche oltre la
  scadenza dichiarata. `atlas run-status` dice se il run che l'ha aperta è
  ancora attivo o si è fermato.
- **Ledger di consegna** (`.atlas/graphs/<slug>/notify-state.json`): per ogni
  coppia interazione/canale registra l'ultimo esito, `delivered`, `pending`
  (in backoff, non ancora un problema) o `failed` (tentativi esauriti). È la
  fonte per sapere se un canale specifico ha davvero provato a consegnare,
  non solo se la card esiste.
- **Motivi tipici di una mancata consegna**: la dashboard non era aperta (gli
  avvisi browser esistono solo mentre la pagina è caricata), `ATLAS_HIMALAYA_TO`
  non è dichiarata sulla macchina che ha eseguito il run (l'unico canale
  rimasto è allora l'avviso di sistema, utile solo se qualcuno guardava lo
  schermo), oppure il canale è Telegram e la sua parte di invio, come detto
  sopra, non esiste ancora.
- `atlas run-log --tail 20` mostra la sequenza vera: `interaction-opened`,
  l'attesa, un eventuale `retry`, la chiusura. Utile per distinguere "nessuno
  ha risposto" da "il run non è mai arrivato a chiedere".

## Diagnostica: relay e sicurezza

Questa sezione esiste perché il percorso sopra non deve mostrarli, non perché
siano opzionali da sapere quando qualcosa non torna.

- **Stato del deploy**: nessun relay OCI, bot Telegram o hostname HTTPS è mai
  stato messo in piedi in questo ambiente. Il gate dei prerequisiti
  ([A01](../.atlas/graphs/260830-atlas-interactions/tickets/A01.md)) resta
  chiuso, quindi tunnel, webhook e pairing restano codice pronto e testato,
  mai eseguito contro un host reale. `relay/README.md` è il documento
  operativo completo: cosa c'è in `relay/`, quali variabili d'ambiente
  servono (`RELAY_HTTPS_HOSTNAME`, `ATLAS_RELAY_TOKEN_REF`,
  `ATLAS_RELAY_DEPLOY_HOST`, `ATLAS_RELAY_DEPLOY_PATH`,
  `TELEGRAM_BOT_TOKEN_REF`, `TELEGRAM_WEBHOOK_SECRET_REF`,
  `TELEGRAM_BOT_USERNAME`) e come lanciare `relay/deploy.py` quando quelle
  variabili esistono davvero.
- **Protocollo client-relay**: un tunnel outbound in stile SSE su HTTPS (mai
  WebSocket, mai polling), autenticato con un bearer per progetto che non
  lascia mai il processo `atlas serve` verso il browser. Definito da
  [D01](../.atlas/graphs/260830-atlas-interactions/tickets/D01.md),
  implementato lato client da `payload/core/relay_client.py` e lato relay da
  `relay/tunnel.py`.
- **Capability token**: ogni azione che un tap Telegram può risolvere porta
  un token opaco, firmato HMAC, monouso (`jti`) e con scadenza non superiore a
  quella dell'Interaction che rappresenta. Lo emette e lo verifica solo il
  client, mai il relay: il relay inoltra un evento firmato, non decide un
  bel niente sul lifecycle. `payload/core/capability.py`.
- **Webhook Telegram**: verifica l'header
  `X-Telegram-Bot-Api-Secret-Token` prima di fidarsi che una chiamata venga
  davvero da Telegram, deduplica per `update_id`, e rifiuta con un 200 muto
  (mai un errore che riveli l'esistenza del progetto) una chat non associata
  da pairing. `relay/telegram_webhook.py`.
- **Pairing**: un codice monouso per progetto, persistito su disco lato
  relay (sopravvive a un restart), mai un token o un chat ID digitato a
  mano lato client. `relay/pairing.py`.

Per chi lavora sul codice del relay, non solo per chi lo usa, il resto dei
dettagli operativi e i comandi di verifica in isolamento sono in
`relay/README.md`.

## Cosa non fa, oggi

Due limiti reali, per non promettere quello che questo grafo non ha ancora
costruito:

- **Nessun bot Telegram che parla per primo.** Il messaggio iniziale con i
  bottoni oggi Atlas non lo manda a nessuno: un tap su un messaggio esistente
  funziona, aprire la conversazione no.
- **Nessun deploy reale.** Relay OCI, bot Telegram e hostname HTTPS non sono
  mai stati messi in piedi: tutto quello che serve un servizio esterno resta
  verificato in isolamento, mai contro un host vero.
