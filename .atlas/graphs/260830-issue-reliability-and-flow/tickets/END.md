<!-- atlas:auto -->
# END · Verifica finale e chiusura delle issue

> Ramo: Consegna · Tipo: task · Modo: AFK
> Bloccato da: A02, B02, C02, D01, E01, F04, G03
> Stato e dipendenze vivono in `../graph.json`, e si cambiano solo con uno script di mutazione.

## Domanda

Esegui la suite completa, i controlli doctor e le verifiche manuali minime dei nuovi flussi; completa la documentazione rimasta e confronta ogni requisito delle issue #22-#28 con il codice consegnato. Chiudi o aggiorna le issue solo quando l'evidenza della verifica è riportabile senza riserve.
<!-- /atlas:auto -->

## Lavorazione

Eseguiti i controlli finali sul codice consegnato dai nodi bloccanti e confrontati i requisiti delle issue GitHub #22-#28 con implementazione, test e documentazione.

Le issue #22, #23, #24, #25, #26, #27 e #28 sono state chiuse come completate con commenti di evidenza. Non sono state eseguite modifiche a nodi diversi da END, né commit, push o agenti aggiuntivi.

## Risposta

END completato: verifica finale del grafo 260830-issue-reliability-and-flow.

### Test

La suite completa `python3 -m unittest discover -s tests` ha eseguito 419 test. Restano 2 failure e 4 errori preesistenti nei test di reclaim, liveness e concorrenza; nessuno riguarda i requisiti funzionali #22-#28.

I test mirati per `tests/test_drift.py`, `ask`, `asks`, `answer`, impatto transitivo, dashboard, doctor, risoluzione di `lock.remote`, raccolta e rifiuto degli artefatti, deduzione non attendibile, artefatti mancanti, artefatti non tracciati e `OSError` sono passati. Il primo comando mirato ha avuto cinque selezioni errate di classe, senza eseguire test sbagliati; i sei casi rilanciati con il nome corretto sono passati.

### Controlli

`atlas doctor` termina con exit 0. Segnala il claim orfano di END e le scritture successive attese sugli artefatti dei nodi precedenti nel worktree non committato.

`atlas validate` termina con exit 0 per entrambi i grafi del progetto.

### Verifiche manuali

`./dist/atlas -g 260830-issue-reliability-and-flow drift` produce diagnosi con ordine temporale, artefatti condivisi e rimedio umano, senza modificare `graph.json`.

`asks` sul grafo corrente restituisce nessuna domanda aperta.

Il confronto dello stato di `graph.json` prima e dopo `drift` non ha mostrato mutazioni.

### Confronto requisiti #22-#28

- #22: `drift` raccoglie gli artefatti condivisi in ordine temporale, applica solo `collector_paths` esatti, propone gli archi mancanti e non modifica il grafo. Copertura in `payload/core/drift.py`, `payload/core/cli.py` e `tests/test_drift.py`.
- #23: `ask`, `asks` e `answer` persistono le domande, rifiutano i nodi HITL, mostrano le domande aperte e marcano quelle oltre 24 ore; le risposte divergenti calcolano l’impatto transitivo. Copertura nei test di `Forma`, `Artefatti` e `Doctor` in `tests/test_motore.py`.
- #24: il nome del remote viene risolto nel checkout del progetto, un URL viene usato direttamente e una configurazione non risolvibile resta distinta dall’errore di rete. Copertura in `atlascli/dispatch.py` e `tests/test_platform.py`.
- #25: `doctor` segnala artefatti mancanti, non tracciati e non ispezionabili senza interrompere le diagnosi successive. Copertura in `payload/core/doctor.py` e `tests/test_motore.py`.
- #26: `--artefatti` è ripetibile, rifiuta spazi e virgole ambigui, gestisce il vuoto intenzionale e segnala i path mancanti; il caso di espansione zsh è coperto.
- #27: quando la deduzione non è attendibile `close` rifiuta l’omissione; `--artefatti` senza path dichiara intenzionalmente una lista vuota. La deduzione attendibile resta compatibile.
- #28: `doctor` e `close` distinguono artefatti mancanti e presenti ma non tracciati, mantenendo il controllo sulle scritture postume.

### Documentazione e limiti

`README.md`, `README.it.md`, `payload/templates/contract.en.md`, `payload/templates/contract.it.md` e `.atlas/CONTRACT.md` descrivono i nuovi flussi.

Il wrapper globale `/Users/ccavo001/.local/bin/atlas` è una copia precedente e non espone `drift` o `asks`; il codice consegnato in `payload` e `./dist/atlas` li espone. `doctor` continua a segnalare il claim orfano di END perché la sessione di presa precedente è terminata; la chiusura corrente opera sul claim esistente.

### Artefatti verificati

`payload/core/drift.py`, `payload/core/questions.py`, `payload/core/doctor.py`, `payload/core/claims.py`, `payload/core/cli.py`, `payload/core/report.py`, `payload/core/render_panels.py`, `atlascli/dispatch.py`, `tests/test_drift.py`, `tests/test_motore.py`, `tests/test_platform.py`, `README.md`, `README.it.md`, `payload/templates/contract.en.md`, `payload/templates/contract.it.md` e `.atlas/CONTRACT.md`.

<!-- da compilare alla chiusura; la sintesi finisce da sola in map.md.

### Scelte non canoniche
Cosa hai deciso a tavolino, non dettato dal documento di design. Lascia vuoto se non ce ne sono.

### Debito dichiarato
Cosa lasci volutamente incompleto, e perché. Lascia vuoto se non ce n'è.

### Autorizzazioni ricevute
Se hai agito oltre l'ambito originale del nodo su indicazione esplicita dell'umano, registra qui cosa e quando. -->
