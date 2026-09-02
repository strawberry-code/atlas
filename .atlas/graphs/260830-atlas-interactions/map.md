# Atlas Interactions

> Grafo `260830-atlas-interactions` · la verità sta in `graph.json`, questa mappa è la sua faccia leggibile.

## Destinazione

<!-- atlas:auto -->
Interazioni Atlas a basso attrito: pannello Notifiche, avvisi locali, email Himalaya e Telegram con relay OCI, risposta valida e ripresa Automata senza polling.

## Note

Preferenze permanenti e skill da consultare a ogni sessione.

<!-- atlas:auto -->
- Issue #30. Tutti i nodi sono AFK e non specificano model: Automata usa Codex Luna di default.
- Il deploy Telegram richiede un bot, hostname e segreti OCI già approvati nel suo ambiente; il grafo li verifica ma non li crea né li espone.

## Come si lavora un nodo

Si guarda la frontiera con `atlas status`, si rivendica un nodo con `atlas claim <ID>` prima di toccare qualsiasi cosa, si lavora, si scrive la sezione Risposta del suo ticket e si chiude con `atlas close <ID> -s "sintesi"`, che aggiunge da sé la riga qui sotto. Il contratto completo sta in `.atlas/CONTRACT.md`.

## Decisioni prese

Una riga per nodo chiuso, in ordine di chiusura: quanto basta per giudicarne la rilevanza, poi si apre il ticket.

<!-- atlas:auto -->
- **A01** Verifica i prerequisiti del relay: Prerequisiti Telegram e HTTPS mancanti; credenziali OCI locali presenti senza esposizione di segreti. · [ticket](tickets/A01.md)
- **A02** Definisci il contratto UX e delle Interazioni: Contratto Interaction definito: tre eventi, quattro stati, capability dichiarate e card senza dettagli di trasporto. · [ticket](tickets/A02.md)
- **A03** Implementa ledger e schema Interaction: Ledger Interaction atomico e idempotente nel graph.json, con audit, contesto e scadenza. · [ticket](tickets/A03.md)
- **A04** Implementa lifecycle e risposta validata rilasciato: run Automata del 2026-08-30 interrotto: il nodo non fu mai lavorato · [ticket](tickets/A04.md)
- **A04** Implementa lifecycle e risposta validata: Lifecycle Interaction transazionale, risposta validata e audit completo implementati · [ticket](tickets/A04.md)
- **A05** Collega Automata alle Interazioni: Interazioni Automata e risveglio event-driven · [ticket](tickets/A05.md)
- **B01** Proietta le Interazioni nella dashboard: Proiezione dashboard del ledger Interaction: nuovo modulo interactions_view.project() con età, urgenza (timedelta residuo), stato, nodo, run e azioni consentite, senza rileggere gli eventi di audit · [ticket](tickets/B01.md)
- **B02** Costruisci il side panel Notifiche rilasciato: run interrotto, lucchetto orfano · [ticket](tickets/B02.md)
- **B02** Costruisci il side panel Notifiche: Pannello destro Notifiche: compatto, richiudibile, badge, tre sezioni (attenzione richiesta/in attesa/risolte oggi), card a una frase con al massimo due azioni · [ticket](tickets/B02.md)
- **B03** Risolvi Interazioni dalla UI locale: Bottoni del pannello Notifiche collegati al lifecycle atomico via POST /interactions/<id>/<action> in 'atlas serve'; il commit risveglia Automata come A05. Corretto un difetto di propagazione ereditato da B02 (un'azione apriva anche la scheda); azioni non ammesse e doppio invio impossibili lato server. Log di audit e artefatti del nodo ora consultabili su richiesta. · [ticket](tickets/B03.md)
- **C01** Implementa il coordinatore notifiche: Coordinatore notifiche: notify.py (plan/dispatch, NotifyState ledger JSON con dedup permanente) e channels.py (registro canali stile AdapterRegistry) implementati; retry bounded riusa retry.RetryPolicy/classify_failure; escalate falso solo su retry pending, vero su delivered/failed. 8 test nuovi, suite completa verde. · [ticket](tickets/C01.md)
- **C02** Aggiungi avvisi browser e di sistema: Avvisi locali senza setup: canale di sistema (notify_local.py) e canale browser (dashboard.js) agganciati alla ronda di 'atlas serve', dedup via NotifyState/localStorage, click sulla notifica browser che riporta alla card · [ticket](tickets/C02.md)
- **D01** Definisci il protocollo client-relay: Protocollo definito: tunnel outbound client-relay in stile SSE su HTTPS (no WebSocket, no polling), autenticato con bearer per-progetto; capability token opachi HMAC-firmati, monouso e a scadenza <= quella dell'Interaction, emessi e verificati solo dal client, mai dal relay · [ticket](tickets/D01.md)
- **C03** Aggiungi avvisi Himalaya: Canale Himalaya per alert ed escalation: notify_himalaya.py (solo invio via 'himalaya message send', nessuna lettura mailbox, credenziali via env ATLAS_HIMALAYA_TO/ACCOUNT mai nel grafo) agganciato alla ronda di 'atlas serve' via serve_notify.py, dedup/retry riusati da C01 · [ticket](tickets/C03.md)
- **D02** Distribuisci Atlas Relay su OCI: Servizio relay isolato e tubatura di deploy (systemd/Caddy, health check, rollback automatico) implementati e testati in isolamento; deploy reale non eseguito perché il gate di A01 (bot Telegram/hostname HTTPS approvati) è ancora chiuso in questo ambiente · [ticket](tickets/D02.md)
- **D04** Implementa il bot Telegram con webhook: Adapter Telegram lato relay (D04): webhook verificato via secret token, utenti non associati rifiutati con 200 silenzioso, callback inline deduplicati per update_id con ack sempre inviato; payload minimo, nessun log di segreti o contenuto sensibile · [ticket](tickets/D04.md)
- **D03** Apri il tunnel Atlas verso il relay rilasciato: claim fantasma della suite e2e, nessun lavoro svolto · [ticket](tickets/D03.md)
- **D03** Apri il tunnel Atlas verso il relay: Connessione uscente resiliente client-relay (D03): payload/core/relay_client.py (riconnessione con backoff esponenziale e full jitter, identità di sessione graph/runId, nessun polling, zero import verso interactions/mutate/run_state quindi una disconnessione non può inventare chiusure né toccare lo stato Atlas) e relay/tunnel.py + endpoint GET /tunnel su relay/atlas_relay.py (bearer, RegistroTunnel in memoria per sessione, nessuna coda di rimessaggio). Wiring in atlas serve/Automata e instradamento del sink Telegram lasciati a D06, che ha anche capability e pairing. · [ticket](tickets/D03.md)
- **D05** Crea il pairing Telegram one-tap: Pairing Telegram one-tap dal pannello Notifiche: un bottone, un codice monouso persistito lato relay, nessun campo per token bot/chat ID/hostname; corretto anche un bug latente di D03 in deploy.py che non rsyncava tunnel.py. · [ticket](tickets/D05.md)
- **D06** Inoltra le azioni Telegram ad Atlas: Tap Telegram inoltrato da relay/tunnel al lifecycle Atlas: capability D01 verificata (firma, scadenza, jti monouso), Interaction risolta dentro mutate.editing, messaggio Telegram aggiornato, Automata ripreso senza polling; deliver iniziale con bottoni segnalato in fog come gap non coperto da alcun nodo precedente · [ticket](tickets/D06.md)
- **E01** Esegui la verifica end-to-end: Verifica end-to-end: 732/732 unit test (729 preesistenti + 3 nuovi) e 97/97 e2e.py verdi; nuovo tests/test_verifica_e2e_interazioni.py con thread e server HTTP reali prova il risveglio Automata da un vero POST di 'atlas serve' e il comportamento di run_state su crash-a-meta'-attesa vs stop-pulito-su-HITL; Telegram outbound resta non verificabile perche' non esiste (gap gia' noto da D06) · [ticket](tickets/E01.md)
- **E02** Scrivi Quick Start e diagnostica: Quick start e diagnostica delle Interazioni in docs/atlas-interactions-quickstart.md: primo alert (locale/browser/Himalaya, tutti reali), pairing Telegram one-tap e diagnosi di una consegna mancata; i due gap noti (invio Telegram iniziale assente, deploy relay mai eseguito) dichiarati esplicitamente, non nascosti · [ticket](tickets/E02.md)
- **E03** Completa hardening e release readiness: Suite 732/732 + 97/97 verdi su dist/atlas rigenerato (era rimasto disallineato da E02); capability/relay/dedup/rollback verificati solidi; corrette due lacune di documentazione (CLAUDE.md sulla rete in payload/, README su Interazioni); confermati e non toccati i gap noti (Telegram outbound, deploy reale, idempotenza per run) e il set di azioni ridotto rispetto alla issue #30 · [ticket](tickets/E03.md)
- **D07** Manda la notifica Telegram con i bottoni: Canale Telegram in uscita costruito: deliver iniziale con bottoni via C01/D03, chat_id risolto lato relay dal pairing di D05, esito registrato nel ledger di consegna. Deploy reale mai eseguito (A01/D02); gap sul limite callback_data di Telegram (D01) appuntato in fog. · [ticket](tickets/D07.md)
- **D08** Fai stare il callback Telegram in 64 byte: Callback Telegram sotto i 64 byte: nel bottone va un identificativo corto emesso da un nuovo store del relay (relay/capability_store.py), la capability D01 per intero resta li' e si risolve al tap, invariati emissione e verifica lato client. · [ticket](tickets/D08.md)
- **END** Chiudi Atlas Interactions: Interazioni Atlas verificate per intero, 772/772 test unitari e 97/97 e2e verdi: ledger, dashboard, notifiche locali/Himalaya e ciclo Telegram completo fino al tap che risolve una decisione; resta il solo deploy reale (bot Telegram, hostname HTTPS, OCI, webhook), gate ancora chiuso da A01 · [ticket](tickets/END.md)

## Non ancora specificato

Quel che è emerso e non ha ancora un nodo. Si appunta con `atlas fog "una riga"`.

<!-- atlas:auto -->
- La quota Codex e' esaurita fino al 30 settembre 2026: i run di questo periodo lavorano con Claude via fallback automatico, senza toccare il campo model dei nodi.
- per B01: Finche' i canali di avviso non esistono, una card aperta da Automata non la vede nessuno: il runner ora la lascia scadere in 15 minuti e chiude con la sua diagnosi.
- per C01: La coda degli eventi delle Interazioni vive in memoria di processo: una risposta scritta nel grafo da un altro processo sveglia il runner solo alla sua rilettura, ogni 30 secondi.
- per C02: gli avvisi locali (browser e sistema) partono dalla ronda di 'atlas serve', non dal runner Automata: se Automata gira senza dashboard servita, una nuova Interazione resta visibile solo nel grafo finche' qualcuno non apre 'atlas serve' o la dashboard scade da sola.
- Nessun canale Telegram lato client invia ancora la notifica iniziale con i bottoni (il deliver di D01): capability.emetti esiste (D06) ma nessuno lo chiama fuori dai test. Serve un TelegramChannel che implementi channels.Channel, generi una capability per bottone ed emetta un deliver via relay_client verso il chat_id risolto lato relay dal pairing (serve l'inverso di progetto_di).
- per A05: Rilanciare 'atlas run' prima di chiudere a mano un nodo HITL gia' notificato non riprende quel run: run_state chiude a 'failed' su uno stop pulito (terminale, non resumable), quindi il run successivo prende un run_id nuovo e apre una seconda card indipendente per lo stesso nodo (idempotenza A03 per run_id, non per nodo). Verificato con codice vero in tests/test_verifica_e2e_interazioni.py.
- per D01: capability.emetti produce token da ~270 byte (base64 payload+firma HMAC): Telegram limita callback_data a 64 byte. D06 li consuma gia' come callback_data e D07 li spedisce cosi': in un deploy reale ogni tap fallirebbe all'invio API Telegram, mai testato perche' A01/D02 restano chiusi. Serve ripensare il trasporto del capability sul bottone (es. un id corto lato client che referenzia il token vero, mai il relay) prima del primo deploy reale.

## Fuori scopo

Quel che sta oltre la destinazione, e il perché.

<!-- atlas:auto -->
_niente, per ora._
