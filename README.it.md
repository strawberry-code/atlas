# Atlas

![Una carta nautica dove la costa è un grafo di dipendenze: a sinistra i nodi chiusi col sigillo di ceralacca, sulla frontiera illuminata due lucchetti d'ottone, a destra la nebbia di quel che non si sa ancora.](docs/hero.jpg)

*[English version](README.md)*

Harness di task a grafo. I task sono nodi, le dipendenze sono archi, la **frontiera** è quel che si può prendere adesso. Ogni nodo dichiara se la sua risposta si scrive con l'umano (**HITL**) o la scrive l'agente da solo (**AFK**).

## Cos'è, e quando ha senso usarlo

Atlas prende il lavoro di un progetto, lo scompone in nodi collegati da dipendenze e lo fa vivere in un grafo invece che in una lista. Ogni nodo è un ticket dimensionato su una sessione: una feature da costruire, una domanda da sciogliere, un'esplorazione da fare prima di poter decidere. La frontiera è l'insieme dei nodi prendibili adesso, quelli i cui blocker sono già chiusi: non si sceglie leggendo dall'alto in basso, si guarda cosa è davvero prendibile.

Ogni nodo dichiara anche chi scrive la sua risposta. Un nodo **AFK** (away from keyboard) lo lavora l'agente da solo, e l'output finisce sempre in un file: il ticket stesso o l'artefatto che produce. Un nodo **HITL** (human in the loop) si scioglie parlando: la domanda arriva all'utente una alla volta, e la risposta si scrive insieme.

Ha senso installarlo quando un pezzo di lavoro dura più sessioni e ha dipendenze vere fra le sue parti. Un'epic con una decina di task collegati è il caso tipico, un grafo per epic. Se il lavoro sta in una sessione sola, o è una lista senza dipendenze reali, il grafo aggiunge cerimonia invece di struttura.

## Come si lavora, in pratica

Si installa il CLI, si installa in un progetto (crea `.atlas/`, registra il progetto, aggiunge le skill), poi il ciclo è sempre lo stesso:

1. **Si crea o importa un grafo**, da un testo che già esiste oppure tracciandolo da zero se l'idea è ancora nebbia. Se ne occupano le skill `atlas-wayfinder` e `atlas-new-graph`.
2. **Si guarda la frontiera** con `atlas status`, o `atlas next` per ordinarla per impatto quando i nodi prendibili sono più d'uno.
3. **Si prende un nodo** con `atlas take <ID>`, prima di toccarlo: rivendica e stampa il suo contesto (domanda, Risposte dei bloccanti, nebbia che lo nomina) nello stesso passo.
4. **Si lavora**: se il nodo è AFK lo fa l'agente da solo, se è HITL la skill `atlas-work` porta le domande una alla volta e aspetta.
5. **Si chiude** con `atlas close <ID> -s "sintesi"`, dopo aver scritto la Risposta nel ticket. Mappa e dashboard si rigenerano da sole.

Un modo di orchestrare più nodi insieme, se il progetto ne ha molti prendibili: una sessione "principale" che guarda la frontiera e coordina, i nodi AFK delegati a sotto-agenti che lavorano in parallelo e scrivono i risultati nei rispettivi ticket, i nodi HITL riservati a una sessione dedicata. Non è una funzione del motore, è un modo di usarlo: Atlas resta la fonte di verità su cosa è fatto, chi coordina sopra è libero di organizzarsi come preferisce.

## Installare il CLI

```bash
curl -fsSL https://raw.githubusercontent.com/strawberry-code/atlas/main/install.sh | sh
```

Su Windows nativo (nessun WSL richiesto):

```powershell
irm https://raw.githubusercontent.com/strawberry-code/atlas/main/install.ps1 | iex
```

Finisce in `~/.local/bin/atlas` (`%USERPROFILE%\.local\bin\atlas` su Windows, override con `ATLAS_INSTALL_DIR`). Serve Python 3.10+: niente venv, nessuna dipendenza oltre la stdlib.

## Installare in un progetto

```bash
atlas install .                      # oppure atlas install /path/al/progetto
atlas install . --graph mio-epic     # crea subito il primo grafo
atlas install . --lang en            # contenuti e skill in inglese invece che italiano
```

In `.atlas/` finiscono solo i dati del progetto: `config.json`, i grafi, gli script di mutazione, le skill, il contratto e un `README.md` che spiega a chi trova quella cartella come procurarsi `atlas`. Il motore non ci finisce: vive nell'eseguibile, uno per macchina. Fuori da `.atlas/` resta un symlink per skill in `.claude/skills/`, l'hook di fine sessione in `.claude/settings.json` e il contratto in `CLAUDE.md`. Il progetto viene anche registrato in `~/.config/atlas.json` con uno slug (default: nome della cartella; `--slug` per un nome diverso).

```bash
atlas list                           # progetti registrati e il loro stato
atlas list mio-progetto              # la scheda di uno solo
atlas update                         # aggiorna atlas e riallinea i progetti registrati
atlas update --no-projects           # aggiorna solo l'eseguibile, i progetti restano indietro
atlas lang en                        # lingua dei contenuti di questo progetto
atlas lang --global en               # default per i progetti futuri
```

Il motore di un progetto non si aggiorna, perché in un progetto non c'è: vive nell'eseguibile, e appena `atlas` cambia versione ogni progetto usa quella nuova. Restano indietro i file veri scritti dentro il progetto, cioè le skill, `.atlas/CONTRACT.md`, `.atlas/README.md` e il blocco delimitato in `CLAUDE.md`, mentre il `README.md` del progetto non viene mai toccato. Quelli li rimette in pari `atlas update`, che dopo aver sostituito l'eseguibile ripassa i progetti del registro uno per uno. Lo fa anche quando non c'è niente da scaricare, limitandosi in quel caso ai progetti installati da una versione diversa: senza, chi ha aggiornato partendo da una versione che ancora non riallineava resterebbe indietro per sempre. Chi non c'è più sul disco viene saltato e detto; chi resta indietro per un errore suo non ferma gli altri. Il riallineamento rinfresca quel che il progetto ha, non aggiunge quel che non ha mai avuto: senza hook o senza blocco in `CLAUDE.md` si resta senza. Con `--no-projects` si aggiorna il solo eseguibile, e i progetti si rimettono in pari a mano con `atlas install <path>`.

Cambiare lingua a un progetto esistente rigenera `SKILL.md`, `CONTRACT.md` e ogni dashboard: un `map.md` già scritto nella vecchia lingua non viene toccato (le sue intestazioni non combaciano più), quel grafo resta com'era finché non lo si aggiorna a mano, mentre i ticket nuovi seguono la lingua corrente.

Quando il progetto è una repo git, `atlas install` registra anche un merge driver git per i file del grafo: una riga in `.gitattributes` (`merge=atlas-graph` su `.atlas/graphs/*/graph.json`) e una sezione `[merge "atlas-graph"]` nel config git locale, che punta ad `atlas merge-graph`. Da lì in poi un merge git che tocca `graph.json` passa dal driver invece che dal merge di git per righe. I progetti installati prima di questa funzione ricevono il driver al primo `atlas update`, insieme agli altri file riallineati. Per disattivarlo, togli la riga da `.gitattributes` e la sezione dal config git.

## Lavorare

I comandi del grafo valgono da dentro il progetto, che `atlas` trova da solo risalendo le cartelle:

```bash
atlas how-to                         # il briefing completo: contratto, comandi, mutazioni, skill, path
atlas status                         # frontiera, lucchetti, avanzamento
atlas next                           # frontiera ordinata per impatto, come suggerimento
atlas take F01                       # rivendica e stampa il contesto in un solo passo
# lavori, poi scrivi la sezione Risposta in .atlas/graphs/<slug>/tickets/F01.md
atlas close F01 -s "sintesi in una riga"
atlas amend F01 --artefatti src/a.py # corregge la contabilità di un nodo già chiuso
atlas render --open                  # dashboard
atlas serve --no-open                # dashboard su un server locale, viva (Ctrl-C per fermare)
atlas serve --port 8080              # la stessa, sulla porta che scegli tu
atlas doctor                         # controllo di salute: nodi dimenticati, lucchetti fermi, dashboard stantia
atlas conflicts                      # i conflitti di merge irrisolti del grafo attivo
atlas conflicts --resolve            # li dichiara risolti, dopo aver corretto graph.json a mano
```

Un nodo per sessione. `close` rifiuta se la Risposta è vuota.

### Un claim da un'altra macchina

Un claim può venire da un'altra macchina. Quando due macchine lavorano sullo stesso grafo, un claim è un lease: porta `host` e `lease_until`, e un claim remoto è vivo finché il suo lease non scade (default 3600 s, `lease_ttl_seconds` in `config.json`), non finché esiste il suo processo. I claim nostri rinnovano il battito a ogni comando che carica il grafo, quando manca meno di metà del TTL alla scadenza: un comando per TTL tiene vivo il lease, e una raffica non riscrive il file.

Il lucchetto remoto si accende per scelta. Metti `lock.remote` in `.atlas/config.json` con un remote git (per esempio `origin`), e Atlas coordina il claim su ref git condivise prima di toccare un nodo; senza, il comportamento resta quello di sempre, tutto locale. Senza rete il lucchetto degrada in lettura e chiude in mutazione: `status`, `next`, `show` e `brief` mostrano lo stato locale con l'avviso "remote non raggiungibile", mentre `take` su un nodo libero, `close` e `release` rifiutano di scrivere, perché senza la ref non si può escludere che un'altra macchina tenga il nodo; `doctor` riferisce lo stato del lucchetto remoto senza morire. Quando il lucchetto remoto è attivo, la finestra condivisa della deduzione degli artefatti vede anche le ref remote prese da altre macchine durante la lavorazione. `atlas serve` mostra i lucchetti delle altre macchine in un pannello dedicato quando il lucchetto è attivo, degradando con garbo quando il remote non si raggiunge.

## Chi fa cosa

Le assegnazioni sono facoltative e servono a chi si divide un grafo fra più persone. Un nodo assegnato resta prendibile da chiunque: il lucchetto continua a essere il `claim`, l'assegnazione dice di chi è il pezzo, non chi ci ha le mani sopra adesso.

```bash
atlas whoami marco                   # chi lavora da questa copia, ricordato in .atlas/whoami
atlas assign cristiano,pedro F01 F02 # assegna due persone ai nodi, sostituendone l'elenco
atlas assign lucia --branch B        # e i nodi che il ramo B ha adesso
atlas assign --me F04                # a te, senza riscrivere il nome
atlas assign --add pedro F01         # aggiunge pedro a chi il nodo ha già
atlas assign --remove pedro F01      # toglie solo pedro, lascia gli altri
atlas unassign F02                   # torna senza nessuno
```

I nomi sono testo semplice e la virgola li separa quando un nodo è di più di una persona; l'elenco cambia quando serve, perché non c'è un registro di persone da tenere aggiornato. `.atlas/whoami` non è versionato, perché è chi ha il repo davanti, non un dato del progetto. Nella dashboard compaiono un chip per persona e uno per i non assegnati: cliccandone uno restano illuminati solo i suoi nodi, come per il filtro di stato. Un nodo condiviso fra due persone compare sotto entrambi i chip.

## Cambiare il grafo

Mai a mano, sempre con uno script:

```bash
atlas new-script aggiunge-ramo-deploy
# scrivi le mutazioni in .atlas/scripts/002-aggiunge-ramo-deploy.py
atlas exec .atlas/scripts/002-aggiunge-ramo-deploy.py 003-sistema-bloccante.py # in ordine, una transazione per script
atlas renumber # chiude i buchi e i doppioni della numerazione
atlas renumber --dry-run # mostra le rinomine senza farle
```

```python
from core import mutate

def run(g):
    mutate.add_branch(g, "X", "Consegna", "#0f766e")
    mutate.add_node(g, id="X01", branch="X", type="task", mode="AFK",
                    title="Pipeline di build",
                    question="Che cosa produce, e come si verifica che sia buono?",
                    blockedBy=["F03"])
```

Ogni script gira nella sua transazione e viene validato prima di scrivere: cicli, archi verso il nulla e id duplicati fanno fallire lo script senza toccare il file. `atlas exec` accetta più script in una volta, li applica in ordine e si ferma al primo che fallisce.

`atlas renumber` rimette in ordine gli script di `.atlas/scripts/`. Senza argomenti chiude i buchi e i doppioni della numerazione; con dei file li sposta in coda, nell'ordine indicato, dopo il massimo degli altri. In una repo git le rinomine passano da `git mv`. Quando un grafo è condiviso e le storie divergono, la base è quella pubblicata e i propri script si riapplicano sopra: `graph.json` non si fonde mai a mano. Le chiusure già avvenute sull'altra copia si riportano con `mutate.restore_closure`; il ciclo completo è descritto nella skill `atlas-sync`.

Un merge di `graph.json` può comunque capitare: due macchine lavorano sullo stesso grafo, entrambe committano, e i rami si incontrano. A occuparsene è il merge driver git registrato all'installazione. Fonde per id di nodo invece che per riga, scrive sempre JSON valido e non lascia mai marker di conflitto di git nel file. Quando i due lati hanno cambiato lo stesso nodo in modi inconciliabili, esce in conflitto, git marca il file, e un campo `conflicts` in `graph.json` registra quel che non ha saputo fondere. `atlas conflicts` elenca quelle voci, e `atlas conflicts --resolve` le dichiara risolte una volta che hai corretto il file a mano:

```bash
atlas conflicts                  # elenca i conflitti di merge irrisolti
atlas conflicts --resolve        # li dichiara risolti, dopo aver corretto graph.json
```

Altre funzioni: `edit_node`, `link`, `unlink`, `drop` (fuori scopo), `remove_node`, `reopen`, `assign`, `unassign`, `fog_add`, `fog_drop`, `note_add`, `set_meta`, `restore_closure` (riporta una chiusura già avvenuta su un'altra copia). `mutate.assign(g, names, node_ids=(), branch=None, modo="set")` imposta, aggiunge o toglie gli assegnatari di un nodo: `names` accetta `"anna,marco"` o una lista di nomi, e `modo` è `"set"`, `"add"` o `"remove"`.

## Più grafi

Uno per epic, isolati. `atlas new` prende un nome tecnico e vi antepone da solo la data di creazione: `altro-epic` diventa `YYMMDD-altro-epic`, così ogni grafo si ordina per quando è nato già dal nome della cartella.

```bash
atlas new altro-epic -t "Titolo" -d "Dove si arriva."   # crea YYMMDD-altro-epic
atlas graphs                                             # elenca lo slug vero, data compresa
atlas use YYMMDD-altro-epic       # rende attivo un grafo, una volta sola
atlas render -g YYMMDD-altro-epic # oppure si sceglie sul singolo comando
```

Lo slug non si scrive al posto del comando: `atlas YYMMDD-altro-epic render` non esiste. `-g/--graph` vale sia prima sia dopo il comando (`atlas -g YYMMDD-altro-epic render` e `atlas render -g YYMMDD-altro-epic` sono la stessa cosa), e `ATLAS_GRAPH=<slug>` fa lo stesso per tutta la shell.

## Le skill

Si invocano da sole quando serve, e `atlas how-to` le elenca con le loro descrizioni.

Tre governano il ciclo di lavoro:

- **`atlas-wayfinder`** è il metodo che regge tutto il resto: nominare la destinazione, decidere invece di fare, distinguere la nebbia da un nodo, mettere fuori ambito quel che sta oltre la destinazione.
- **`atlas-new-graph`** costruisce un grafo nuovo, da un testo che hai già o tracciandolo da zero.
- **`atlas-work`** lavora un nodo dalla frontiera alla chiusura, e **`atlas-sync`** allinea la propria copia di un grafo condiviso prima di pubblicarci sopra.

Le altre cinque dicono come si lavora un nodo, una per tipo, perché un tipo di nodo che nessun documento definisce è solo un'etichetta:

- **`atlas-strategic-grilling`** e **`atlas-tactical-grilling`** sono i due modi di lavorare un nodo `grilling`. La prima è il metodo di Matt Pocock: una domanda alla volta, senza budget, finché l'albero del disegno non è percorso. La seconda lavora un ambito ristretto in tre fasi, la ricognizione dell'agente sul codice, un numero dichiarato di domande all'utente (dodici di default), la sintesi da confermare.
- **`atlas-research`** risponde a un nodo `research` andando alle fonti primarie e citando ogni affermazione con link e data.
- **`atlas-prototype`** costruisce l'artefatto usa e getta di un nodo `prototype`, una TUI per la logica o varianti di interfaccia da guardare accanto.
- **`atlas-domain-modeling`** affila il linguaggio del dominio mentre si decide, e registra come ADR le sole decisioni care da rovesciare.

## Licenza

AGPL-3.0. Vedi `LICENSE`.

## Sviluppare Atlas

```bash
python3 -m unittest discover -s tests   # motore + CLI globale (registry, self-update, install.sh)
python3 build.py && python3 tests/e2e.py  # dist/atlas, provato davvero
```

`payload/` è il motore che finisce nel progetto ospite, e deve restare stdlib pura, multipiattaforma (POSIX e Windows), senza rete. `atlascli/` è il CLI globale (install/update/uninstall/list, registro, self-update): stdlib pura anche lì, ma la rete verso GitHub è consentita perché è un prodotto diverso. Dopo ogni modifica va rigenerato `dist/atlas` con `build.py`. Per tagliare una release: `python3 release.py X.Y.Z` (bump versione, build, test, sha256 — i comandi git/GitHub restano manuali).
