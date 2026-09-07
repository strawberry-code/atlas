# Foto della dashboard Atlas, a fianco di quelle di Nodavia (V03)

Catturate con `tests/screenshot_dashboard.py` (Chrome di sistema via `playwright-core`,
stesso meccanismo di ricerca del browser di `payload/core/view_capture.py`, finestra
1600×1100 come `notes/nodavia/`). Il grafo primario e' `260906-grafite-dashboard` (34
nodi, il piu' grande dei sei); il nodo scelto per selezione/hover e' `Q01`, il fan-in/
fan-out piu' ricco (3 blockedBy + 5 dipendenti), equivalente al `sintesi` di Nodavia.
Le foto sono lette in memoria da `graph.json` (nessuna scrittura sul progetto), tranne
le due dell'arco di ritorno che vengono da una fixture sintetica (vedi sotto).

Come rilanciare: `python3 tests/screenshot_dashboard.py --node-modules <cartella-con-
node_modules/playwright-core>` (o `ATLAS_SHOT_NODE_MODULES`). Vedi il docstring del
file per la dipendenza dichiarata (Node.js + playwright-core, nessuno dei due nel
repo) e il degrado se manca.

## Le coppie con un confronto diretto in Nodavia

| Atlas | Nodavia | Confronto |
|---|---|---|
| `01-apertura-rinquadrata.png` | `01-tre-pareri-vista-iniziale.png` | Stessa idea (fitView/rinquadro all'apertura, nessuna selezione), superficie diversa **per progetto**: Atlas incornicia il canvas dentro una dashboard di gestione (topbar coi tre readout, colonna di pannelli a sinistra, notifiche a destra), Nodavia e' un editor nudo. I nodi sono colorati per **stato** (verde chiuso, blu in lavorazione, giallo prendibile, bianco bloccato): in Nodavia il colore e' per **tipo** di nodo (agent/start/end) e non porta stato. Differenza voluta, non un pezzo mancante: e' la ragione stessa per cui esiste una dashboard invece di un editor. |
| `03a/03b-selezione-pulse-animato-frame{1,2}.png` | `02-tre-pareri-selezione-pulse-animato.png` | Q01 prende l'anello `.sel`; le palline pulsano su **tutti** gli archi che lo toccano (3 verso l'alto, 5 verso il basso), non solo uno. Il diff pixel-a-pixel fra i due fotogrammi (396 pixel su un ritaglio di 335×312, a 350ms di distanza) conferma che si muovono davvero, non e' un fermo immagine. Corrisponde esattamente al comportamento di `sintesi` in Nodavia (3 archi entranti + 1 uscente, tutti insieme). |
| `04-selezione-pulse-reduced-motion.png` | `03-tre-pareri-selezione-pulse-reduced-motion.png` | Stessa selezione, `prefers-reduced-motion: reduce`: le palline spariscono e restano tratteggi statici sugli stessi archi. Comportamento identico a Nodavia, stessa intenzione (il segnale "quest'arco tocca il selezionato" resta, il movimento no). |
| `07-minimap-crop.png` | `05-minimap-crop.png` | Stessa geometria (rettangolo in basso a destra, nodi come rettangoli pieni). Colore: Atlas la colora per **stato** (verde/blu/giallo/grigio), Nodavia per **tipo** (agent nero, start/end grigio). Stessa differenza voluta di `01`, coerente in tutta la dashboard. |
| `08-controls-crop.png` | `06-controls-crop.png` | Stessi 4 bottoni nello stesso ordine (zoom in, zoom out, fit, lucchetto), stessa colonna verticale in basso a sinistra. Atlas ne aggiunge un quinto (ripristina il layout dopo un trascinamento, C10): funzione che Nodavia non ha perche' il suo editor non permette di trascinare le card fuori dall'auto-layout allo stesso modo. |
| `09-arco-di-ritorno-a-riposo.png` | `07-live-steering-back-edge.png` | Vedi la nota a parte sotto: qui la fonte non e' un grafo reale ma una fixture sintetica, per una ragione strutturale, non per pigrizia. |
| `10a/10b-arco-di-ritorno-selezionato-frame{1,2}.png` | `08-live-steering-back-edge-selezionato.png` | Stessa fixture. Selezionando `X` (che dipende sia da `AVVIO`, arco sano, sia da `Z`, il ritorno) le palline compaiono su entrambi, e quelle sulla corsia tratteggiata si spostano fra i due fotogrammi: la geometria e l'animazione del back-edge portate da Nodavia (A01, C08) funzionano. |

## Le scene senza equivalente in Nodavia (concetti solo di Atlas)

- `02-hover-su-nodo.png`: passare sopra Q01 attenua tutto il resto e illumina l'intera
  catena di dipendenze (ascendenti e discendenti), non solo l'arco toccato. Nodavia non
  ha catturato una scena di hover (il suo CSS lo supporta, piu' semplice: ispessisce
  l'arco sotto il puntatore, non l'intera catena), quindi non c'e' un confronto diretto,
  solo una nota: l'hover di Atlas e' piu' ambizioso (mostra la catena intera), non un
  sottoinsieme di quello di Nodavia.
- `05-scheda-ticket-aperta.png`: la scheda con stato/tipo/modo/assegnatario, la domanda,
  la sezione Lavorazione/Risposta e gli artefatti. Nodavia non ha un concetto di
  ticket: e' un editor di grafi di esecuzione, non un tracker di task. Nessun pezzo
  mancante, e' semplicemente un dominio che a Nodavia non serve.
- `06-vista-tabellare.png`: l'intero grafo come tabella ordinabile (ID, titolo, stato,
  ramo, tipo/modo, assegnatario, costo, bloccato da). Stessa ragione: Nodavia non ha
  bisogno di una vista tabellare perche' non e' un tracker.
- `11-apertura-<slug>.png` (le altre 5 grafi reali, 16-27 nodi): stessa vista iniziale
  del primo grafo, per riprova che l'auto-layout regge taglie diverse (16, 23, 27, 34
  nodi verificati) e non solo quella usata per le foto principali.

## L'arco di ritorno: perche' viene da una fixture sintetica, non da un grafo vero

Nessuno dei sei grafi reali contiene un ciclo, e non e' un caso da colmare: un ciclo in
Atlas e' un **difetto**, non uno stato valido come in Nodavia (dove il ritorno
`autore -> critico -> autore` e' controllo di flusso legittimo). Due presidi
indipendenti lo impediscono:

1. `editor.validate` (chiamato in chiusura di ogni `editing()`) solleva su un ciclo:
   il file non viene scritto affatto. Uno script che provi a chiudere un ciclo con
   `mutate.link` dentro una transazione normale fallisce li'.
2. Anche aggirando il primo punto (un `graph.json` modificato a mano, fuori
   dall'API), `atlas render` non produce comunque un dashboard.html intero:
   `render_panels.panels()` chiama `topology.convergence()` che chiama
   `topology.levels()`, e quest'ultima **solleva sempre** su un ciclo (e' scritto nel
   suo stesso docstring: "e' anche la sola convalida strutturale che serve a ogni
   comando"). Verificato costruendo la fixture: il messaggio esatto e' in
   `messaggio-ciclo.txt`, `ciclo di dipendenze su X`, sollevato da
   `render_panels.py:97`.

Quindi oggi **non esiste alcun graph.json, reale o costruito ad arte, da cui `atlas
render` produca un dashboard.html con un arco di ritorno disegnato**: il pannello
laterale crasha sempre prima. Il codice che disegnerebbe il ritorno (`render_svg.py`,
`render_edges.py`, `edge_geometry.py`, con la corsia laterale e il tratteggio portati
da Nodavia per la decisione A01/C08) e' scritto, testato in isolamento
(`test_edge_geometry.py`, `test_layout_rank.py`) e **funziona** quando lo si raggiunge
(le foto `09`/`10` lo dimostrano), ma non e' raggiungibile dal punto d'ingresso
normale: e' codice morto in pratica, non per un bug di per se', ma perche' nessun
grafo puo' arrivare fin li' con un ciclo davvero dentro.

Le foto `09`/`10` vengono quindi da una fixture sintetica costruita dentro
`tests/screenshot_dashboard.py` (`render_sintetico_ciclo`): un grafo AVVIO→X→Y→Z→W
costruito con la vera API (`mutate`/`editing`, cosi' lo schema e' quello giusto),
richiuso, e SOLO DOPO patchato a mano per aggiungere l'arco X←Z che chiude il ciclo
(bypassando deliberatamente `editor.validate`, cosa che il resto del progetto non fa
mai). La pagina si riassembla escludendo solo `render_panels.panels()` (il pezzo che
crasha, isolato con un try/except attorno alla sola chiamata che lo invoca): canvas,
tabella, notifiche, scheda e script restano quelli veri. Il pannello laterale nella
foto mostra al suo posto il messaggio di errore vero e proprio, non un placeholder
inventato.

**Segnalato al cancello con `atlas fog`**, non risolto qui: non e' un file di render_
lite.py/serve.py (fuori dal mio perimetro in questo nodo), ma tocca render_panels.py/
topology.py, di cui non sono l'agente assegnato.
