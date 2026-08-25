# L04 · Dove abita il codice di rete del lucchetto remoto

> Nodo di grilling del grafo `260825-sync-distribuita` (ramo "Lucchetto fra macchine").
> Decisione presa in autonomia (AFK), interrogando il codice e le note di L01, L02, L03.
> Questa nota è la versione estesa; la Risposta del ticket `L04.md` è il vincolo operativo per L05, L07 e C01.

## La domanda in una riga

`payload/` non ammette rete e il lucchetto vive in `claims.py`: si dichiara la seconda eccezione dopo `self_update`, o il lucchetto remoto passa da un confine nuovo?

## Cosa dice il codice (verificato il 2026-08-25)

- **`payload/core/` non tocca mai la rete in uscita.** Nessun `urllib`, `socket`, `urlopen`, `requests` nei moduli del motore. L'unico servizio di rete è `serve.py`, che ascolta su `127.0.0.1` (localhost, non esce dalla macchina) con la sola stdlib.
- **`gitscan.py` usa git solo in locale.** Le chiamate a `subprocess.run(["git", ...])` sono `diff`, `ls-files`, `rev-list`, `mv`: nessun `remote`, `push`, `fetch`, `ls-remote`, `pull`, `clone`. È locale puro, quindi non tocca la regola "senza rete".
- **`claims.py` (180 righe, protocollo del lucchetto) non fa git.** Consuma `gitscan.touched` per la deduzione degli artefatti in `_artefatti` (righe 121-145), fuori dalla transazione, ma non lancia git per il lucchetto: il claim è stato locale scritto nel grafo (PID, session, identity, at, heartbeat, fingerprint).
- **L'eccezione di rete esistente vive nel layer che gestisce i progetti.** `atlascli/self_update.py` usa `urllib` verso l'API di GitHub; `install.sh` scarica l'asset. `atlascli/__init__.py` lo dichiara: "qui la rete è consentita (solo stdlib, verso GitHub), lì resta vietata per contratto".
- **I due strati viaggiano nello stesso eseguibile.** `build.py` copia `atlascli/` e `payload/core/` nella stessa staging e fa uno zipapp: `core` è importabile accanto ad `atlascli`. La separazione è convenzione documentata (CLAUDE.md, README, `__init__.py`), non un meccanismo di runtime.
- **Il motore può girare senza il CLI globale.** `core.cli.main` è "il motore invocato da solo, senza il CLI globale attorno: serve ai test". Quindi il motore non può assumere che un trasporto gli venga iniettato: deve degradare quando il trasporto non c'è.
- **La dipendenza oggi va da atlascli verso core.** `atlascli/dispatch.py` importa `from core.cli import ...`. L'inverso (core → atlascli) non esiste e non deve nascere.
- **Il progetto condiviso usa già git verso il remote** (la skill `atlas-sync` fa `git push`/`merge` verso `origin`), ma a livello di skill, cioè di istruzioni per l'agente, non nel motore. Il remote condiviso è lo stesso `origin` del progetto.

## Le tre opzioni e il loro peso

### (a) Seconda eccezione dichiarata

`claims.py` farebbe push/ls-remote direttamente, e la regola verrebbe emendata per ammettere rete nel motore per il trasporto del lucchetto.

Costi:
- Contraddice la frase esplicita della regola: "vale solo per il layer che gestisce i progetti, **mai per il motore che ci finisce dentro**". La promessa dell'ultima refactor (0.7) è che il motore lavori offline; qui entrerebbe la prima operazione di rete nel motore.
- Il motore dovrebbe gestire autenticazione, remote e credenziali git, che sono materia dell'host e del progetto, non del motore.
- Ogni test del motore che tocca il lucchetto dovrebbe avere a che fare con un remote o un fake: la suite smetterebbe di essere ermetica.

Vantaggio: il meno cablaggio. Ma il cablaggio che risparmia è esattamente il confine che tiene il motore offline.

### (b) Confine nuovo: interfaccia nel motore, trasporto nel layer che gestisce i progetti

`payload/core` definisce la semantica del lease e un'interfaccia per il trasporto (esito tipizzato, protocollo `RemoteLock`, holder iniettabile). L'implementazione su refs git vive in `atlascli/`, dove la rete è già consentita, e viene iniettata al boot del dispatcher quando il progetto dichiara un remote per il lucchetto.

Costi:
- Un pezzo di cablaggio in più: il punto di iniezione va dichiarato e mantenuto.
- Due moduli nuovi (`core/remotelock.py`, `atlascli/remotelock.py`), uno dei quali è il solo codice di rete nuovo del prodotto.

Vantaggi:
- La regola "rete vietata in payload/" regge senza seconda eccezione: il trasporto sta nel layer dove la rete è già ammessa.
- Il motore degrada da solo: senza trasporto iniettato, comportamento identico a oggi (lucchetto locale soltanto).
- Gli esiti del trasporto arrivano come dati (`Rete`, `Tenuto`, `Gara`, ...), mai come traceback: L07 ha un gancio tipizzato su cui decidere la politica senza rete.
- La suite del motore resta ermetica: i test iniettano uno stub, il trasporto si testa contro un bare repo locale (come ha già fatto il prototipo di L03).
- L02 aveva già dichiarato che il trasporto del lease è materia di L04 e che il confine no-rete di payload/ non viene toccato da quella decisione: (b) lo conferma.

### (c) Git come già si usa, gate-da-config

"payload/ chiama già git via subprocess; il trasporto remoto è git contro un remote, gate-da-config."

Questo non è una terza via: `gitscan.py` chiama git **in locale** (diff, ls-files, rev-list), e la regola vieta la **rete**, non git. Un `git push` verso un remote è rete a tutti gli effetti, anche se passa da subprocess. Quindi (c) si riduce a (a) con in più un cancello di configurazione. Il cancello è giusto e va tenuto, ma non decide dove vive il codice: lo decide il confine.

Il gate-da-config (nessun remote → feature spenta) è una **condizione necessaria** di qualunque scelta, non l'alternativa: senza remote configurato, il trasporto non deve esistere e il motore deve comportarsi come oggi.

## La decisione

**Scelgo (b): confine nuovo, senza seconda eccezione.** Il lucchetto remoto passa da un confine: la semantica e l'interfaccia restano nel motore, il trasporto (l'unica rete nuova) vive nel layer che gestisce i progetti. La regola "rete vietata in payload/" non si indebolisce: si allarga solo l'elenco dei consumatori di rete nel layer che gestisce i progetti.

### Il confine esatto, modulo per modulo

| Modulo | Layer | Cosa contiene |
|---|---|---|
| `payload/core/remotelock.py` (nuovo) | motore, offline | Il modello di esito (dataclass/enum: `Disattivo`, `Acquisito`, `Tenuto(holder, scadenza)`, `NonScaduto`, `NonTuo`, `Gara`, `Rete`), il protocollo `RemoteLock` con `acquire`, `ruba`, `rilascia`, `elenca`, e l'holder `set_trasporto` / `attivo()`. Nessuna rete, nessun import di atlascli. |
| `payload/core/claims.py` | motore, offline | Il lease (campi `host`, `lease_until`, rinnovo, `claim_state`/`close` remoti, da L02) e il consumo del lucchetto remoto **attraverso** l'holder: se `attivo()` è falso, il motore non tocca il remote, percorso identico a oggi. |
| `payload/core/config.py` | motore | I DEFAULTS guadagnano una sezione `lock` (schema, es. `{"remote": None}`) così doctor la conosce. |
| `atlascli/remotelock.py` (nuovo) | gestione, rete ammessa | Il trasporto git-refs che implementa `RemoteLock`: push non forzato = acquire, `--force-with-lease` = ruba/rilascia, `ls-remote` + fetch = elenca (le primitive di L03). Legge il remote dalla config del progetto, mappa rc ed errori localizzati di git sugli esiti tipizzati, la rete assente diventa `Rete`, mai un traceback. |
| `atlascli/dispatch.py` | gestione | Al boot, se `.atlas/config.json` dichiara `lock.remote` (stringa), costruisce il trasporto e chiama `core.remotelock.set_trasporto(...)` prima che girino i comandi del motore. Solo config al boot, rete solo al primo uso del lucchetto. |

La regola di dipendenza resta: `atlascli` importa `core`, mai l'inverso. Il motore non sa nulla del remote, delle credenziali o di come si parla a git: produce i dati (owner, scadenza) e consuma esiti.

### Perché l'interfaccia non è astrazione speculativa

La regola del progetto ("niente astrazioni per uso singolo") non si applica: l'interfaccia è il **meccanismo** che tiene la rete fuori dal motore. Senza di essa, o il motore importa il trasporto (inversione della dipendenza, violazione del confine) o il trasporto vive nel motore (violazione della regola). È la cucitura minima. C'è un solo implementatore oggi (git-refs), ma la cucitura serve al confine, non alla sostituibilità.

## Conseguenze operative

### Per L05 ("Il lease entra in claims.py")

1. I campi del lease nel claim (`host`, `lease_until`), il rinnovo-su-lettura, `claim_state` e `close` per holder remoti: tutto in `payload/core/claims.py`, secondo L02.
2. `payload/core/remotelock.py`: esiti, protocollo, holder. Nessuna rete.
3. I punti di chiamata in `claims.py` dove il lucchetto remoto viene consultato (take, close, rinnovo): il motore agisce solo quando `attivo()`, e gli esiti del trasporto sono dati, non eccezioni.
4. `atlascli/remotelock.py`: il trasporto git-refs, unico codice di rete nuovo.
5. Il cablaggio in `atlascli/dispatch.py` (o in un helper che chiama).
6. Test: il motore con nessun trasporto (comportamento attuale invariato) e con uno stub iniettato; il trasporto contro un bare repo locale (come il prototipo L03), mai rete vera.

### Per L07 ("I bordi: finestra condivisa e assenza di rete")

1. La politica sugli esiti `Rete` (rete assente ma trasporto configurato): cosa fanno take/close, con messaggio chiaro o con degradazione e avviso. Il confine garantisce che il motore abbia un esito tipizzato su cui decidere.
2. La finestra condivisa (`_condiviso`) che oggi guarda solo il grafo locale: come il motore scopre cosa ha chiuso l'altra macchina, attraverso il trasporto (`elenca()`) o attraverso il grafo fuso, ma sempre via cucitura.
3. `doctor` che riferisce lo stato del lucchetto remoto (configurato ma irraggiungibile, o skew oltre soglia, da L02 §6).

### Per C01 ("Documenti in pari")

La sostanza della regola non cambia (il motore resta offline), ma vanno aggiornati:

- **CLAUDE.md**: la frase che enumera i consumatori di rete va estesa a `atlascli/remotelock.py`, e "l'unica eccezione" va riformulata: la rete è consentita nel layer che gestisce i progetti (canale di aggiornamento + trasporto del lucchetto), vietata nel motore.
- **README.md / README.it.md**: "network access to GitHub is allowed" diventa "network access to GitHub and to the shared lock remote".
- **`atlascli/__init__.py`**: la docstring "verso GitHub" va estesa al remote del lucchetto.
- **contratto (contract.it/en.md)**: la sezione "Un nodo per sessione" descrive il lease (host, lease_until, holder remoti) e il lucchetto remoto opzionale (config `lock.remote`, modello di fiducia: cooperazione fra agenti, git non verifica il possesso, da L03). La sezione sul grafo condiviso menziona che con `lock.remote` attivo take/close serializzano via refs prima del ciclo di sync.
- **how-to**: se nasce una chiave di config, le sezioni dei path/config la riflettono.
- **skill atlas-sync**: menziona che con `lock.remote` attivo il lucchetto serializza via refs sullo stesso `origin`.

## Nebbia residua

- Il nome della chiave di config (`lock.remote`) e il default (riuso di `origin` vs chiave dedicata) sono indicati ma non verificati sul campo: L05 può rifinirli, l'importante è il gate esplicito (feature spente di default, nessun comportamento nuovo per i progetti esistenti).
- La scelta di L05 su dove il lucchetto remoto serializza (per nodo o per grafo) resta sua: il trasporto accetta nomi di lucchetto opachi, quindi entrambe le scelte passano dall'interfaccia.
- Il comportamento esatto con rete assente (bloccare o degradare) è di L07, non di L04: qui resta fissato che il motore riceve un esito `Rete` e decide.
