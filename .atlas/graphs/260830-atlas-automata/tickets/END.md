<!-- atlas:auto -->
# END · Collaudo finale e chiusura dell'enhancement

> Ramo: Verifica e consegna · Tipo: task · Modo: AFK
> Bloccato da: E01, E02
> Stato e dipendenze vivono in `../graph.json`, e si cambiano solo con uno script di mutazione.

## Domanda

Esegui la suite completa, la validazione Atlas, le verifiche CLI e almeno un run controllato con parallelism=1. Confronta ogni requisito della issue #29 con l'evidenza prodotta, verifica che non restino nodi aperti o rami orfani e chiudi l'unica issue enhancement solo quando il comportamento è documentato e riproducibile.
<!-- /atlas:auto -->

## Lavorazione

- Eseguito il collaudo finale sul codice sorgente e sull'artefatto `dist/atlas`, senza modificare `graph.json`, senza delegare agenti e senza creare commit o push.
- Verificato che i difetti della suite globale restano confinati a claim/liveness e non toccano il runner Automata; non sono state applicate correzioni fuori perimetro.
- Verificata la riproducibilità del run seriale con adapter fake, compresa la persistenza diagnostica esercitata dai test Automata.

## Risposta

Collaudo finale completato per l'enhancement #29. Il comportamento richiesto è documentato in `docs/atlas-automata-contract.md`, nei README bilingui e nel contratto installabile, ed è riproducibile con il codice sorgente, `dist/atlas` e la suite Automata.

### Requisiti issue #29 ed evidenza

- Parallelismo per run: `./dist/atlas ... run --parallelism 1` configura la modalità seriale; 0, valori negativi e testo non intero sono rifiutati con exit 2. I test Automata verificano anche il limite bounded per valori maggiori.
- Campo `model` opzionale e default Luna: validazione, compatibilità dei grafi esistenti e selezione di `codex-luna` sono coperti da `test_automata_contract`, `test_model_selection` e `test_motore`.
- Fallback Luna-Sonnet: il test end-to-end verifica un solo passaggio a `claude` quando Luna è indisponibile e nessun fallback per modello esplicito, errore del lavoro o terminazione ambigua.
- Adapter estensibili e provider: registry, identità Luna/Claude/Gemini/Terra e `SubprocessAdapter` sono coperti da `test_adapters` e `test_provider_process`; il contratto verifica argv separata, stdin chiuso, AFK, fuori sandbox e bypass dei permessi.
- Retry e guasti: timeout, crash, rate limit, provider unavailable e terminazione ambigua sono classificati e ritentati con backoff 60/120 secondi nel run controllato; gli errori permanenti non vengono ritentati e il budget è bounded.
- Frontier, serialità, eventi, resume e idempotenza: `test_automata_run`, `test_automata_e2e` e `test_retry` verificano claim, rilettura Atlas, eventi duplicati o mancanti, resume, claim vivi e assenza di doppi avvii.
- Diagnostica: `run-state.json`, `atlas run-status` e `atlas run-log --tail N` sono verificati da `test_run_state` e `test_automata_run`; il contratto distingue stati, eventi e retry.
- CLI, documentazione e validazione: `test_automata_contract`, `test_readme`, `compileall`, `git diff --check`, build, checksum e `./dist/atlas ... validate` passano.

### Test

- Suite Automata completa: 74 test passati.
- Suite completa del repository: 493 test, 487 passati, 2 failure e 4 errori preesistenti nei test claim/liveness (`test_concorrenza`, `test_lease`, `test_motore`), indipendenti da Automata.
- E2E CLI storico: 89/97 verifiche passate; le 8 verifiche fallite sono le regressioni preesistenti su claim, close e liveness.
- Run controllato `parallelism=1`: 4 scenari end-to-end passati, inclusi retry multipli, backoff, fallback Luna-Sonnet e terminazione ambigua.
- `python3 build.py`, checksum SHA-256, `compileall`, `git diff --check`, `validate`, `doctor` e verifiche CLI locali: passati.

### Artefatti

- `docs/atlas-automata-contract.md`
- `.atlas/CONTRACT.md`, `.atlas/README.md`, `README.md`, `README.it.md`
- `payload/core/automata.py`, `payload/core/adapters.py`, `payload/core/providers.py`, `payload/core/retry.py`, `payload/core/run_state.py`
- `tests/test_automata_contract.py`, `tests/test_automata_run.py`, `tests/test_automata_e2e.py`, `tests/test_adapters.py`, `tests/test_model_selection.py`, `tests/test_provider_process.py`, `tests/test_retry.py`, `tests/test_run_state.py`, `tests/test_readme.py`
- `dist/atlas`, `dist/atlas.sha256`

### Limiti reali

- I provider esterni reali non sono stati avviati: il run riproducibile usa adapter fake deterministici; non sono state usate credenziali esterne.
- Il processo provider non viene serializzato tra processi; il resume riconcilia claim, retry e chiusure Atlas senza duplicare un claim vivo, ma non riprende l'handle originale.
- La suite globale conserva 2 failure e 4 errori storici claim/liveness e l'e2e conserva 8 verifiche storiche fallite, tutti fuori dalla superficie Automata.
- Il binario locale aggiornato `./dist/atlas` espone `run`; `~/.local/bin/atlas` è un'installazione precedente che non espone ancora il comando. Questo è drift dell'installazione locale, non un difetto del sorgente o di `dist/atlas`, e non è stato modificato.
- `atlas run` configura e valida il contesto; l'esecuzione effettiva del runner con adapter e waiter è l'entry point programmatico verificato dalla suite.

Il grafo `260830-atlas-automata` ha un solo nodo ancora in lavorazione, END, e nessun ramo orfano o frontiera inattesa oltre al claim di END necessario alla chiusura.

<!-- da compilare alla chiusura; la sintesi finisce da sola in map.md.

### Scelte non canoniche
Cosa hai deciso a tavolino, non dettato dal documento di design. Lascia vuoto se non ce ne sono.

### Debito dichiarato
Cosa lasci volutamente incompleto, e perché. Lascia vuoto se non ce n'è.

### Autorizzazioni ricevute
Se hai agito oltre l'ambito originale del nodo su indicazione esplicita dell'umano, registra qui cosa e quando. -->
