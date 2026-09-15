# Aree di memoria del grafo, disegno di riferimento

Documento sorgente del grafo `atlas-memory`. È la versione finale del disegno discusso il 2026-09-15, dopo tre simulazioni su un cantiere da 500 nodi e la revisione che ha introdotto il sigillo. I nodi del grafo lo citano come fonte: chi lavora un nodo lo legge per intero prima di toccare il codice, e se trova una contraddizione fra questo testo e la domanda del nodo vince la domanda del nodo e la contraddizione va in nebbia.

## Il termine

**Area di memoria**: un documento del grafo con una regola di scrittura, che ogni nodo riceve prima di iniziare. Non è nebbia (ciò che non ha ancora un nodo), non è un ticket (il diario di un nodo solo), non è la destinazione (immutabile), non è la sezione «Decisioni prese» della mappa (automatica e completa, una riga per nodo chiuso). Un'area esiste quando un terzo nodo, di un altro ramo, ha bisogno di quella conoscenza; altrimenti è un appunto di ticket.

Il principio che regge tutto: la lettura non deve dipendere dal ricordo dell'agente ma dal percorso che l'agente fa comunque. `take` e `brief` stampano le aree per intero; l'agente non deve andarle a cercare. È la distinzione recognition/recall dei «memory item» aeronautici (UX for AI, Nudelman e Kempka, p. 20): un passo che l'operatore dovrebbe ricordare salta sotto pressione, un passo che ha davanti no.

## Il modello: struttura nel grafo, prosa nel file

Lo stesso rapporto che c'è fra `graph.json` e i ticket.

In `graph.json`, una lista `memory` al livello di `nodes`, `fog`, `questions`:

```json
"memory": [
  {"id": "vincoli",
   "title": "Vincoli non negoziabili",
   "purpose": "Le cose che nessun nodo può rinegoziare",
   "usage": "Leggila prima di ogni stima o scelta di dimensionamento. Non si scrive: cambia solo per mano di una persona.",
   "policy": "locked",
   "branches": null,
   "seal": {"digest": "9f1c0a2b3d4e", "at": "2026-10-14T15:02:11+02:00", "by": "cristiano"}}
]
```

- `id`: kebab-case, `^[a-z][a-z0-9-]*$`, unico fra le aree. È anche il nome del file.
- `title`, `purpose`, `usage`: testo libero. `purpose` è una riga, `usage` un paragrafo che dice come e quando usarla.
- `policy`: uno di `locked`, `append`, `edit`. Vocabolario chiuso in `config.json` sotto `vocab.policies`, come `types` e `modes`.
- `branches`: `null` (tutti i nodi la leggono) oppure una lista di chiavi di ramo. Un nodo legge le aree senza filtro più quelle che nominano il suo ramo.
- `seal`: l'impronta del corpo come Atlas l'ha accettato per ultimo, con istante e autore. È il cuore del disegno, vedi sotto.

Il file `.atlas/graphs/<slug>/memory/<id>.md`:

```markdown
<!-- atlas:auto -->
# vincoli · Vincoli non negoziabili

> Regola: locked · Rami: tutti
> Scopo: Le cose che nessun nodo può rinegoziare
> Uso: Leggila prima di ogni stima o scelta di dimensionamento. Non si scrive: cambia solo per mano di una persona.
> La testa discende da `graph.json` e si riscrive a ogni rigenerazione; la memoria è quel che sta sotto il marker.
<!-- /atlas:auto -->

Tetto di spesa: 18,5 M€, tutto compreso.
Concessione demaniale: 20 anni (P08, 2026-10-14).
```

La testa fra i due marker si rigenera come quella dei ticket (`docs.rewrite_heads`); il corpo è di chi scrive. Il layout della testa sta in un template `memory.{it,en}.md`, e `build.py` rifiuta di impacchettare se manca una lingua. Il **corpo** è il testo dopo `<!-- /atlas:auto -->`, normalizzato (fine riga `\n`, spazi finali tolti, un solo `\n` in coda). L'**impronta** è `sha1(corpo)[:12]`, come `model.fingerprint`.

## Le tre regole

| `policy` | L'agente | Chi muove il sigillo |
|---|---|---|
| `locked` | legge e basta | una persona, a mano nel file, poi `atlas memory seal <id>`. Il divieto per l'agente sta nel contratto, come per la risposta di un nodo HITL: è l'unico punto di fiducia non meccanico |
| `append` | aggiunge righe in coda con `atlas memory add <id> "riga"`, mai riscrive | `memory add` lo muove da solo, sotto transazione. La potatura (togliere righe) è un gesto di persona: edita a mano, poi `memory seal` |
| `edit` | può riscrivere il corpo con il proprio editor | chi ha modificato, con `atlas memory seal <id>`. Un AFK che se ne dimentica lo scopre a `close`, con il rimedio nel messaggio |

La riga aggiunta da `memory add` ha la forma `- YYYY-MM-DD <firma>: <testo>`. La firma è l'id del nodo che l'identità corrente tiene rivendicato, se ne tiene esattamente uno; altrimenti `whoami`, altrimenti l'identità di processo. La firma col nodo è quella che conta: chi legge la riga fra tre settimane può aprire quel ticket e trovare il perché.

## Il sigillo e i tre confronti

Un file non sa se la sua ultima modifica è stata accettata da qualcuno. Il sigillo sì. Con tre stati (il file, il sigillo nel grafo, il sigillo che il claim ha visto al `take`) i controlli diventano tre confronti con tre messaggi, ognuno vero:

| Confronto | Significa | `close` |
|---|---|---|
| impronta del file ≠ `seal.digest` | qualcuno ha scritto senza sigillare | rifiuta, senza `--force`: è un guasto del grafo e si ripara. Su `edit`: «sigilla con `atlas memory seal <id>` se la modifica è tua». Su `append`: «le righe si aggiungono con `atlas memory add`; se hai potato, sigilla». Su `locked`: «quest'area non è tua da scrivere: ripristinala, o chiedi a una persona di sigillarla» |
| `seal.digest` ≠ `claim.memory[id]` | l'area è cambiata sotto di te, in modo accettato | rifiuta: «rileggila con `atlas memory show <id>` e decidi se la tua Risposta regge». `--force` chiude comunque, con lo stesso senso che ha già per l'impronta del nodo |
| uguali | niente da dire | chiude |

Un'area creata dopo il `take` (assente da `claim.memory`) conta come cambiata. Un'area rimossa dopo il `take` si ignora. Il primo confronto si fa per primo, perché un file non sigillato rende il secondo privo di senso.

`take` e `claim` scrivono in `node.claim.memory` il dizionario `{id: seal.digest}` delle aree visibili al nodo. `close` scrive sul nodo `memorySeals: {id: seal.digest}` con i sigilli letti al momento della chiusura. Nessun campo dice «l'agente ha toccato l'area X»: un'impronta dice *che* è cambiato, mai *chi*, e un campo dedotto così mentirebbe.

`memorySeals` serve a una domanda che nessun altro pezzo di Atlas sa fare: quando un vincolo cambia, quale lavoro già chiuso poggia sulla versione vecchia? `atlas memory show <id>` stampa «N nodi chiusi con un sigillo precedente: F19, F21 …». È un'informazione da chiedere, non un allarme di `doctor`: a cinquecento nodi diventerebbe rumore.

## Dove la memoria si vede

- **`atlas take <ID>` e `atlas brief <ID>`**: dopo la domanda del nodo, una sezione «Memoria del grafo» con ogni area visibile: `── id · titolo · regola [· rami]`, la riga di scopo, la riga d'uso, poi il corpo per intero, rientrato. Un'area con file non sigillato porta l'avviso sulla sua riga di testa. Senza aree, la sezione non compare.
- **Il briefing AFK di Autopilot** (`providers._prompt`) dice di lanciare prima `atlas brief <ID>` e leggere quella sezione. Non duplica il testo nel prompt: una fonte sola.
- **`atlas memory`**: elenco delle aree con regola, rami, righe del corpo, sigillo (quando, chi) e stato del file (sigillato, non sigillato, mancante). `atlas memory show <id>`: testa, corpo, sigillo, nodi chiusi con sigillo precedente.
- **`map.md`**, sezione «Note»: una riga per area, `- **id** · regola · scopo → memory/id.md`. Il sottotitolo della sezione nel template cambia di conseguenza.
- **`atlas how-to`**, sezione 5: il path `memory/` accanto a `tickets/`.
- **`atlas doctor`**: area dichiarata senza file; file in `memory/` non dichiarato; marker `<!-- /atlas:auto -->` sparito (l'area non si riallinea più, come per i ticket); file non sigillato (impronta ≠ sigillo); corpo oltre 120 righe («una memoria che non si legge per intero a ogni nodo smette di essere memoria: potala»). Mai un traceback su un grafo malato.
- **Dashboard**: fuori da questo grafo. In nebbia.

## Comandi e mutazioni

CLI, per chi lavora:

- `atlas memory` · `atlas memory show <id>` · `atlas memory add <id> "riga"` · `atlas memory seal <id>`.
- `add` rifiuta su `locked` e `edit`. Rifiuta anche se il file non è sigillato (prima si sigilla, poi si aggiunge), perché altrimenti sigillerebbe di nascosto una modifica di qualcun altro.
- `seal` è permesso dalla CLI su ogni regola: la distinzione persona/agente su `locked` la fa il contratto, come `assign` e `drop`. Stampa quante righe sono entrate e uscite rispetto al sigillo precedente.

Script, per chi cambia la forma:

- `mutate.memory_add(g, id, title, purpose, usage, policy, branches=None)`: crea l'area, con il file vuoto sigillato alla prima rigenerazione. Rifiuta id non conforme, duplicato, regola fuori vocabolario, ramo inesistente.
- `mutate.memory_remove(g, id)`: toglie l'area dal grafo. Il file resta su disco, e `doctor` lo segnala come non dichiarato: cancellarlo è un gesto di persona.
- `mutate.memory_edit(g, id, **fields)`: cambia titolo, scopo, uso, regola, rami. Non tocca il sigillo.
- Ogni funzione ha la sua voce `howto.mutate.<nome>` in entrambe le lingue; il test `HowTo.test_ogni_mutazione_ha_la_sua_voce_tradotta` lo pretende.

## Le note di mappa diventano un'area

`meta.notes` è la memoria che Atlas aveva già, senza saperlo: righe in `graph.json`, rese sotto «Note» nella mappa, che `take` non stampa. Con il sigillo diventano un'area `note` a regola `append`, a costo quasi zero, e il concetto doppio sparisce.

- `SCHEMA_VERSION` passa a 2. Un grafo a versione 1 si legge senza errore; `meta.notes` diventa l'area `note` (titolo dalla chiave `heading.note`, scopo e uso dal catalogo, `branches: null`), con una riga di corpo `- <riga>` per ogni nota, e `meta.notes` sparisce. La migrazione si persiste alla prima scrittura del grafo e scrive il file sigillato; prima di quella scrittura `brief` mostra comunque le note nella sezione memoria. Idempotente: un grafo a versione 2 non si tocca.
- `atlas new` crea l'area `note` di default, vuota, sigillata. `mutate.create_graph(notes=[...])` la riempie.
- `mutate.note_add(g, riga)` continua a esistere e appende all'area `note`: gli script già scritti e la skill `atlas-new-graph` non si rompono. La firma è quella della sezione «Comandi».
- La sezione «Note» di `map.md` elenca le aree (vedi sopra); le righe delle note si leggono nel file `memory/note.md`.

## Limiti dichiarati

- Due agenti che riscrivono la stessa area `edit` nello stesso minuto si pestano i piedi: il secondo lo scopre a `close`, non prima. Va scritto nel contratto. Il rimedio è tenere `edit` per poche aree.
- Il sigillo aggiunge un gesto a chi edita a mano. È il prezzo: senza un atto di accettazione non c'è modo di distinguere una modifica voluta da una subita.
- Che l'agente abbia *capito* l'area non lo verifica nessuno, come per la Risposta. La difesa è metterla davanti agli occhi.

## Vincoli di lavorazione per i nodi di questo grafo

- Stdlib sola, Python 3.10, POSIX e Windows. `payload/core/` sotto le 200 righe per file: se `memory.py` sfora, si spezza (per esempio `memory.py` per lettura e impronte, `memory_ops.py` per add e seal).
- Ogni stringa a video passa dai cataloghi con `t("...")`, accenti veri nei cataloghi, forma ASCII nei commenti del motore.
- Chi lavora un nodo non rigenera `dist/atlas`: lo fa solo il cancello Q01. Chi vuole provare l'e2e prima copia la repo in una cartella temporanea e costruisce lì.
- Due nodi prendibili insieme non condividono un sorgente: gli archi del grafo sono disegnati anche per questo, non solo per la logica.
- I nodi appendono le proprie righe di test a `tests/` con `unittest`; la suite intera si lancia con l'uscita rediretta su file, mai in pipe.
