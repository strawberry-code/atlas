# A01 · Come divergono davvero due copie del grafo

> Nodo: A01 · Ramo: Fondo condiviso · Tipo: research · Lette le fonti il 2026-08-25
> Le citazioni del codice sono `path:linea` sul sorgente di `payload/core/` letto in questa data.

## 1. Le fonti primarie: come atlas scrive graph.json

Atlas riscrive il grafo per intero a ogni mutazione, dentro una transazione col lock in mano (`store.transaction`, `payload/core/store.py:165-177`), con `scrivi_atomico` che sostituisce il file in un colpo solo (`store.py:141-156`). Il lock vive su un file separato che non viene mai rinominato né sincronizzato (`store.py:93-117`), ed è gitignorato (`.gitignore`: `.atlas/graphs/*/graph.json.lock`). Nel fondo condiviso non viaggia alcun lucchetto: viaggia solo il grafo.

Tre scelte di serializzazione governano i conflitti che poi git produce:

1. **La forma è canonica.** `store.dumps` (`store.py:68-70`) usa `json.dumps(graph, ensure_ascii=False, indent=2)` e compatta poi ogni array di stringhe su una riga sola con la regex `_STR_ARRAY` (`store.py:61`). Quindi `blockedBy`, `owner`, `artifacts`, `meta.notes`, `fog` e `outOfScope` compaiono come una riga unica. Il commento a `store.py:59-60` dice il perché: riespanderli renderebbe illeggibile il diff di un claim. Il costo è che due modifiche allo stesso array diventano due modifiche alla stessa riga, cioè un conflitto per git anche quando non si pestano. Poiché la scrittura è sempre l'intero file con `dumps`, non esiste deriva di formattazione fra macchine: lo stesso dato produce sempre gli stessi byte.

2. **Ogni mutazione tocca `meta.updated`.** La transazione di editing chiude con `data["meta"]["updated"] = now()[:10]` (`payload/core/editor.py:79`), cioè la data sola, senza ora. È uno stato derivato, non un contenuto: due macchine che lavorano in giorni diversi lo cambiano entrambe e git va in conflitto su quella riga anche quando hanno toccato nodi disgiunti.

3. **La transazione normalizza `owner` di ogni nodo.** `editing` riscrive `node["owner"] = owners_of(node)` per ogni nodo prima di ogni mutazione (`editor.py:75-76`), con `owners_of` che normalizza qualunque forma (`payload/core/owners.py:15-39`). Anche `owner` è stato derivato.

Le mutazioni che producono i contenuti sostantivi:

- `add_node` accoda un nodo nuovo alla lista `nodes` (`payload/core/mutate.py:33-38`): l'ordine di arrivo decide la posizione, e l'ordine non è mai riordinato dal motore. Per il motore l'ordine dei nodi non è significativo: `by_id` costruisce un indice (`payload/core/model.py:37-38`) e `validate` non controlla l'ordine (`editor.py:44-64`).
- `edit_node` protegge `id`, `status`, `assignee`, `claim`, `owner` e lascia cambiare gli altri campi descrittivi (`mutate.py:41-48`).
- `claim` scrive dentro il nodo uno status `claimed`, un `assignee` e un oggetto `claim` con `pid`, `session`, `identity`, `at`, `heartbeat`, `fingerprint` (`payload/core/claims.py:69-75`). Il battito rinfresca solo `claim.heartbeat` (`claims.py:56-58`).
- `close` scrive in un colpo `status`, `assignee`, `claim`, `answer`, `cost`, `closedBy`, `closedAt`, `artifacts` (`claims.py:175-179`): è un evento atomico, non campi indipendenti.
- `release` accoda a una lista di livello alto `data["releases"]` (`claims.py:85-88`), una lista di dizionari che la regex di `_STR_ARRAY` non tocca: resta su più righe.
- `fingerprint` è un hash del contenuto del nodo che esclude `claim` e `owner` (`model.py:69-88`). Serve al controllo locale premessa/chiusura (`claims.py:172-174`), non alla fusione.

Un grafo con i marker di conflitto di git dentro non è JSON valido, e atlas lo rifiuta alla lettura con `ConfigError` "grafo rotto" (`store.py:82-83`). Questo vincola il merge driver: deve produrre JSON valido anche quando non sa risolvere.

## 2. L'esperimento

Ho costruito due copie divergenti del grafo corrente e le ho fuse con git, usando il vero codice del motore per produrre le varianti.

Setup: una copia scratch di `.atlas` con i claim azzerati (l'antenato comune), poi due workspace copiati di lì. Ogni macchina ha mutato la sua copia con `payload/core` caricato via `PYTHONPATH` (le funzioni vere `claim`, `close`, `link`, `note_add`, `fog_add`, `fog_drop`, `add_node`), con identità `M1` e `M2` via `ATLAS_IDENTITY`. La serializzazione è quella reale di `store.dumps`. Poi `git merge-file -p ours base theirs` a tre vie.

Scenario `S8` è la divergenza realistica: la macchina A chiude `A01` e prende `V01`, la macchina B chiude `L01` e prende `V02`, ognuna scrive anche in una lista di livello alto. Il merge è pulito e il risultato passa la `validate()` del motore:

```
$ git merge-file -p ours_S8 base_S8 theirs_S8 > merged2_S8.json; echo $?
0
$ python3 -c "import json; g=json.load(open('merged2_S8.json'))"
A01 status=closed closedBy=M1
L01 status=closed closedBy=M2
```

Le due chiusure sopravvivono entrambe. Questo è il caso base: due macchine che chiudono nodi diversi non hanno bisogno del merge driver, git a righe già le fonde bene.

Tutti gli scenari e i loro esiti:

| # | Scenario | Esito `git merge-file` |
|---|---|---|
| S1 | A chiude A01, B chiude L01, stesso giorno | pulito, JSON valido, `validate()` ok |
| S2 | idem, ma B "il giorno dopo" (solo B cambia `meta.updated`) | pulito: git prende la data di B |
| S2b | A al giorno D+1, B al giorno D+2 | conflitto sulla sola riga `meta.updated` |
| S3 | entrambe chiudono A01 con risposte diverse | 2 conflitti: `answer` e `closedBy` |
| S4 | entrambe prendono V01 | conflitto su `claim.identity` |
| S5 | entrambe aggiungono un blocker a C01 | conflitto sulla riga `blockedBy` |
| S6 | entrambe aggiungono una nota | conflitto sulla riga `notes` |
| S7 | A promuove e aggiunge nebbia, B aggiunge | conflitto sulla riga `fog` |
| S8 | divergenza realistica piena | pulito, entrambe le chiusure sopravvivono |
| S9 | entrambe aggiungono un nodo nuovo in coda | 2 conflitti posizionali, i due nodi si mescolano |

## 3. La classificazione

### Famiglia A · ambigui per davvero

Entrambe le parti hanno toccato lo stesso campo sostantivo dello stesso nodo, e nessuna regola dice quale valga. Git li mostra come conflitto e ha ragione a mostrarli; il problema è che li spezza al grano del campo quando la decisione vera è più grossa.

**A1. La chiusura dello stesso nodo da due macchine (S3).** Conflitti su `answer` e `closedBy`:

```
<<<<<<< ours_S3
      "answer": "risposta A sul nodo A01",
=======
      "answer": "risposta B sul nodo A01",
>>>>>>> theirs_S3
      "claim": null,
      "artifacts": [],
      "createdAt": "2026-08-25T20:32:37+02:00",
      "cost": null,
<<<<<<< ours_S3
      "closedBy": "M1",
=======
      "closedBy": "M2",
>>>>>>> theirs_S3
```

`status`, `assignee`, `claim` si fondono da soli perché entrambe le parti li hanno scritti uguali. La decisione vera è una sola, "di chi è la chiusura", e porta con sé `answer`, `closedBy`, `closedAt`, `cost`. Git la presenta come due scelte indipendenti e così invita a una risoluzione impossibile: prendere `answer` di M1 con `closedBy` di M2 è uno stato che nessuna macchina ha mai scritto. In un ambiente reale si aggiungerebbe anche `closedAt` diverso, perché le due chiusure non avvengono nello stesso secondo.

**A2. Lo stesso nodo preso da due macchine (S4).** Conflitto su `claim.identity`:

```
<<<<<<< ours_S4
        "identity": "M1",
=======
        "identity": "M2",
>>>>>>> theirs_S4
```

Qui il conflitto è una gara vera: entrambe credono di tenere il lucchetto. `pid` e `session` sono rumore locale (in realtà sarebbero diversi e l'intero blocco `claim` andrebbe in conflitto), `at` e `heartbeat` sono timestamp di lease, `fingerprint` è un hash locale. La sola cosa che conta è `identity`, e nemmeno lei è risolvibile col contenuto: serve una politica (chi tiene il lease, chi è vivo, ultimo battito, o dichiarare il conflitto). Nota a margine: se il claim di una macchina è già stato fuso, la `claim` dell'altra viene rifiutata a monte da `node["status"] != OPEN` (`claims.py:60-61`); la gara si vede solo quando le due copie divergono prima che il claim passi da un lato all'altro.

**A3. Stesso campo descrittivo cambiato in modo diverso.** `title`, `question`, `branch`, `type`, `mode` o `blockedBy` rimossi, cambiati via `edit_node` in modo diverso da entrambe le parti. Non l'ho simulato separatamente: è la stessa classe di A1 con un altro campo, e la risoluzione dipende dal campo. Per `blockedBy` il caso in cui una aggiunge e l'altra toglie la stessa dipendenza è un disaccordo vero sul grafo.

### Famiglia B · artefatti del file-uno-solo

Il conflitto non riflette una scelta vera: o il campo è derivato, o la risoluzione giusta è deterministica, o la rappresentazione su riga unica lo inventa.

**B1. `meta.updated` (S2b).** Conflitto di una riga quando le due macchine scrivono in giorni diversi, con lavoro disgiunto:

```
<<<<<<< ours_S2b
    "updated": "2026-08-25",
=======
    "updated": "2026-08-26",
>>>>>>> theirs_S2b
```

È derivato da `editor.py:79`: si ricalcola come massimo delle date (o la data del merge), non si sceglie da una parte. Quando una sola parte lo cambia, git già fa la cosa giusta prendendolo (S2).

**B2. Array di stringhe su riga unica: unione per elemento (S5, S6).** `blockedBy`, `notes`, `artifacts`, `outOfScope`. Due append diverse sulla stessa riga:

```
<<<<<<< ours_S5
      "blockedBy": ["A03", "L06", "V02", "A01"],
=======
      "blockedBy": ["A03", "L06", "V02", "L01"],
>>>>>>> theirs_S5
```

```
<<<<<<< ours_S6
    "notes": ["nota scritta dalla macchina A"]
=======
    "notes": ["nota scritta dalla macchina B"]
>>>>>>> theirs_S6
```

La risoluzione giusta è l'unione degli elementi: `["A03", "L06", "V02", "A01", "L01"]`. Non c'è scelta, c'è una somma. Git la presenta come o/o perché la riga è una sola, e qui la responsabilità è della compattazione di `store.py:61`.

**B3. `fog`: set-merge con cancellazioni (S7).** Una parte promuove una voce e ne aggiunge una, l'altra ne aggiunge una:

```
<<<<<<< ours_S7
  "fog": ["manca una mutazione ...", "nuova voce di nebbia A"],
=======
  "fog": ["sotto --dry-run ...", "manca una mutazione ...", "nuova voce di nebbia B"],
>>>>>>> theirs_S7
```

L'unione ingenua sarebbe sbagliata: la parte che ha promosso la voce `dry-run` l'ha tolta di proposito e il merge non deve resuscitarla. Serve un set-merge a tre vie per elemento (base + aggiunte di entrambi, meno le cancellazioni). È deterministico, quindi non ambiguo, ma più sottile dell'unione cieca.

**B4. `claim.pid`, `claim.session`, `claim.heartbeat`, `claim.at`, `claim.fingerprint`.** Rumore locale: l'altra macchina non deve copiarli, sono significativi solo per chi tiene il lucchetto. Nel merge si ignorano o si regolano con la politica del lease (ramo L), non si fondono.

**B5. Ordine dei nodi nella lista `nodes` (S9).** Due inserti in coda alla lista:

```
<<<<<<< ours_S9
      "id": "N1",
      "title": "nodo nuovo di A",
      "branch": "A",
=======
      "id": "N2",
      "title": "nodo nuovo di B",
      "branch": "L",
>>>>>>> theirs_S9
```

La risposta giusta è "entrambi i nodi esistono". L'ordine non è sostantivo (il motore indicizza per id, `model.py:37-38`), quindi il merge per-nodo può ordinare in modo canonico, per esempio per id, e l'inserimento smette di essere un conflitto.

**B6. `owner`.** Normalizzato a ogni transazione (`editor.py:75-76`). Dopo un merge pulito la prossima scrittura lo riporta comunque in forma canonica; un conflitto sull'array `owner` si risolve con una politica (unione o sostituzione), non leggendo i contenuti.

## 4. Implicazioni per la fusione a tre vie per nodo (A02)

1. **Parsare, non diffare.** La compattazione degli array su riga unica (`store.py:61`) è la causa principale dei conflitti falsi. Il driver deve lavorare sul JSON parsato, per id di nodo, e ricostruire il file con `dumps`: la forma è canonica, quindi l'output è deterministico.
2. **La chiusura è atomica.** Quando due parti chiudono lo stesso nodo (A1), il driver presenta una scelta sola, "la chiusura di M1 o quella di M2", con `answer`, `closedBy`, `closedAt`, `cost` insieme. Mai scelte per campo. Lo stesso per il blocco `claim` (A2).
3. **I campi derivati si ricalcolano.** `meta.updated` = massimo delle date. `owner` = rinormalizzato. `fingerprint` = ricalcolato alla prossima presa. Mai conflitti.
4. **Gli array di stringhe si fondono per elemento.** `blockedBy`, `notes`, `artifacts`, `outOfScope` con l'unione; `fog` con set-merge che rispetta le cancellazioni. Sono liste di livello alto o campi di nodo, e il merge per-nodo copre i secondi ma deve dichiarare una regola per i primi.
5. **Ordine canonico dei nodi.** Ordinare per id (o accodare i nuovi) rende S9 un non-event.
6. **La gara di claim è un conflitto dichiarato.** Il driver non può risolverla col contenuto; o applica una politica di lease, o la lascia dichiarata per A04. Il merge driver non deve mai decidere in silenzio chi tiene un nodo.
7. **Mai marker nel JSON.** Un file con `<<<<<<<` non parsa e atlas lo rifiuta come "grafo rotto" (`store.py:82-83`). Il driver o risolve, o produce JSON valido con il conflitto annotato altrove (compito di A04).

## 5. Copertura e nebbia

Cosa non ho coperto, perché resti dichiarato:

- `releases` è una lista di dizionari su più righe (non compattata) e le append disgiunte si fondono da sole; non l'ho verificato con un esperimento dedicato.
- Il dizionario `branches`: due macchine che aggiungono rami diversi toccano chiavi diverse di un oggetto multilinea, probabilmente si fondono; aggiungere la stessa chiave con colori diversi è un conflitto vero non simulato.
- Ticket `*.md` e `map.md` sono versionati accanto al grafo e divergono a loro volta; `rewrite_heads` e `rewrite_lists` (`payload/core/docs.py:86-108,157-165`) le rigenerano dal grafo, quindi un grafo fuso pulito seguito da un render le riallinea. Il merge per-nodo non le copre.
- Le combinazioni di mutazioni di stato (una parte chiude, l'altra riapre, `drop`, `amend`) non le ho simulate una per una: cadono nella classe A3 (stesso campo, valori diversi) ma ciascuna merita la sua politica.

Proposte di nebbia per il grafo, da valutare con chi lavora A02/A04:

- Il merge per-nodo di A02 copre i campi dei nodi; `fog`, `notes`, `outOfScope` e `releases` restano liste di livello alto che hanno bisogno di una regola di unione propria. La domanda "chi possiede queste liste nel merge" è aperta.
- Il conflitto di chiusura dello stesso nodo (A1) si può presentare solo come scelta fra chiusure intere; se le due chiusure portano artefatti diversi, A04 deve decidere se unirli o tenerne uno.
