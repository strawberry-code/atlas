<!-- atlas:auto -->
# END · Chiudi il primo giro del relay

> Ramo: Consegna · Tipo: task · Modo: AFK
> Bloccato da: F01
> Stato e dipendenze vivono in `../graph.json`, e si cambiano solo con uno script di mutazione.

## Domanda

Verifica il metro di successo fissato in §11/12: il servizio serve se le decisioni si risolvono dal telefono invece di essere rimandate al computer. Controlla che chi lavora offline non veda comparire niente, che un progetto spento resti muto, che il contenuto dei ticket non sia mai passato dal server, e che i due punti scoperti di §7-ter siano stati davvero affrontati in A04 e C01. Aggiorna docs/atlas-relay-design.md con quel che l'uso reale ha smentito.
<!-- /atlas:auto -->

## Lavorazione

<!-- appunti, alternative scartate, link agli artefatti prodotti -->

## Risposta

Verificato leggendo il codice riga per riga (non i ticket dei nodi che lo
dichiarano già fatto), quattro controlli chiesti dalla domanda:

**Il metro di §11/12 non è misurabile.** Il metro è «quante decisioni hai
risolto dal telefono». `F01` non ha effettuato nessun deploy: mancano tutte le
variabili d'ambiente di `deploy.py` e la sessione non aveva credenziali ssh
verso l'host OCI (porta 22 viva, chiave rifiutata). Nessun bot Telegram vero è
collegato a questo relay, quindi zero decisioni reali risolte dal telefono da
contare. Non un fallimento del criterio: un lavoro non ancora cominciato.
Codice e 228 test coprono l'intero giro a livello di unità/integrazione
locale, non la prova che chiede §11/12.

**Chi lavora offline non vede comparire niente: parzialmente vero, e la
falla era nel documento, non solo nel codice.** `render_notif_telegram.py:39-57`
include il blocco «collega Telegram» + nota sperimentale in ogni render del
pannello Notifiche, senza nessun gate su `relay_client.da_ambiente`;
`dashboard.js:49-55` disabilita quel bottone solo per `file://`, mai per
assenza di configurazione relay. Un'installazione che non ha mai visto una
variabile d'ambiente del relay vede comunque il bottone e la nota. Non è un
bug isolato di A04: è la decisione 27 di §6-bis («bottone sempre presente»,
per la scopribilità) mai riconciliata con la promessa opposta di §0/§2 («non
stampa nulla»). Verificato che resti innocuo (`serve_pairing.py:34-42`, tap
senza relay configurato → 503 locale, nessuna richiesta esce dalla macchina).
Corretti §0 e §2 di `docs/atlas-relay-design.md` per dire la verità: il
silenzio riguarda la rete e le notifiche, non la presenza del bottone.

**Un progetto spento resta muto: confermato.** `B02`, `serve_notify.
telegram_abilitato(ref)` dentro `_canali_attivi`, test dedicati con relay e
capability presenti ma levetta spenta.

**Il contenuto dei ticket non passa mai dal server: confermato su tre
percorsi.** `autopilot._card` usa solo id/title del nodo (mai
`tickets/<ID>.md`, verificato a grep su `autopilot.py`/`notify_telegram.py`);
`render_lite.py` (D02) esclude esplicitamente domanda e riassunti delle
Interazioni; `B01` compone solo titolo progetto + titolo nodo + etichetta
evento.

**I due punti scoperti di §7-ter: entrambi affrontati.** `A04` mette la
promessa nulla di grilling 33 come riga fissa sotto il bottone, sempre a
video. `C01` costruisce la via di risposta per chi viene bloccato dal freno
automatico: bottone «Chiedi sblocco» verso il gestore, che riceve comunque
«Sblocca» già al primo blocco.

Aggiornato `docs/atlas-relay-design.md`: §0 e §2 corretti per riflettere il
comportamento vero del bottone di pairing, nuova §11-ter con il dettaglio dei
quattro controlli, §9 riscritto sui passi reali ancora aperti (deploy, poi
uso, poi il metro), §10 con la voce di chiusura, stato in testa al documento
aggiornato.

### Scelte non canoniche
Nessuna: solo verifica e correzione del documento, nessuna decisione di
design nuova.

### Debito dichiarato
La contraddizione fra §0/§2 e la decisione 27 (bottone sempre presente anche
senza relay configurato) è stata sanata nel documento, non nel codice: il
comportamento attuale (bottone sempre visibile, inerte senza configurazione)
resta quello giusto per la scopribilità voluta dal grilling, quindi non c'è
codice da cambiare. Restano debiti già dichiarati dai nodi precedenti e non
nell'ambito di questo nodo: lo scarto webhook/polling trovato da F01, il link
alla sessione governabile da remoto (fog, mai assegnato), il deploy vero e le
due settimane d'uso che sole misurano §11/12.

### Autorizzazioni ricevute
Nessuna: lavoro rimasto nell'ambito della domanda (verifica del metro di
successo e dei due punti di §7-ter, aggiornamento del documento).
