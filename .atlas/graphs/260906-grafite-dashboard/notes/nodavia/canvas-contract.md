# Il contratto del canvas di Nodavia

Fonti: `nodavia/web/src/editor/GraphCanvas.tsx`, `LoopEdge.tsx`, `FlowStepEdge.tsx`,
`pulse.tsx`, `loopPath.ts`, `customNodes.tsx`, `src/styles/editor.css`, e il sorgente
leggibile (non minificato) di `@xyflow/react@12.11.2` e `@xyflow/system` in
`node_modules/@xyflow/react/dist/esm/index.mjs` e
`node_modules/@xyflow/system/dist/esm/index.mjs`. Ogni numero qui sotto o viene da una
riga di Nodavia o è marcato come default di React Flow con il file da cui viene: chi
esegue questo contratto non deve riaprire Nodavia per verificarlo.

Versione installata: `@xyflow/react` **12.11.2** (`node_modules/@xyflow/react/package.json`).

## 1. Il viewport e la sua trasformazione

Il canvas è un `<div className="react-flow">` che porta dentro un
`.react-flow__viewport` a cui React Flow applica `transform: translate(x,y) scale(zoom)`.
Lo stato `{x, y, zoom}` vive nello store interno (Zustand) di React Flow, non in Nodavia:
`GraphCanvas` non passa né `viewport` né `onViewportChange`, quindi il viewport è
**non controllato**, gestito internamente dal componente.

- Default di libreria per il viewport iniziale prima di un fit: `{x:0, y:0, zoom:1}`
  (`defaultViewport`, `@xyflow/react/dist/esm/index.mjs:177`).
- Nodavia lo sovrascrive sempre con un `fitView` al mount (vedi §3): in pratica il
  viewport a `{0,0,1}` non si vede mai.

## 2. Pan

`GraphCanvas.tsx` non passa nessuna delle prop di pan: valgono i default di
`@xyflow/react` (funzione `ReactFlow`, stesso file, riga ~3728):

- **Trascinamento del pane** (`panOnDrag = true`, default): click-and-drag sull'area
  vuota sposta il viewport. È un pan libero in entrambi gli assi (nessun vincolo su
  `translateExtent`, che resta `infiniteExtent`).
- **Rotellina/trackpad** (`panOnScroll = false`, default): lo scroll NON pana. Lo scroll
  di default zooma (§3), perché `zoomOnScroll = true` è anch'esso il default.
- **Tasto Spazio** (`panActivationKeyCode = 'Space'`, default): tenuto premuto forza il
  pan col trascinamento anche quando altrove è disattivato o quando è attiva la
  selezione a rettangolo (vedi §6).
- Non c'è nessun vincolo di `translateExtent`/`nodeExtent`: si può panare all'infinito in
  ogni direzione, il grafo non ha bordi.

## 3. Zoom: ancoraggio, limiti, `fitView`

### Limiti
`GraphCanvas.tsx:80-81`: **minZoom = 0.15**, **maxZoom = 2.5** (espliciti, sostituiscono i
default di libreria 0.5/2, `ReactFlow` stessa riga ~3728).

### Ancoraggio: puntatore per i gesti, centro per i bottoni
Questo è il punto che il codice sorgente decide da solo, non un default dichiarato:

- **Rotellina e pinch-to-zoom** sono ancorati al **puntatore**. React Flow non
  reimplementa la logica di zoom: il suo `createZoomOnScrollHandler` fa solo un filtro
  (classe `nowheel`, `preventDefault`) e poi richiama **direttamente** l'handler nativo
  `wheel.zoom` di d3-zoom (`@xyflow/system/dist/esm/index.mjs:2764-2779`), che calcola la
  nuova trasformazione centrata sulle coordinate dell'evento. Stesso meccanismo per il
  doppio click (`zoomOnDoubleClick = true`, default): viene inoltrato al `dblclick.zoom`
  nativo di d3-zoom (stesso file, righe ~2943 e ~3022-3028), anch'esso ancorato al punto
  del click.
- **I bottoni +/- dei Controls** sono ancorati al **centro del viewport**. Il loro
  handler chiama `panZoom.scaleBy(1.2, options)` (zoom in) o `scaleBy(1/1.2, options)`
  (zoom out) **senza passare un punto** (`useViewportHelper`,
  `@xyflow/react/dist/esm/index.mjs:504-509`); d3-zoom, senza un punto esplicito, ancora
  la scala al centro dell'estensione del viewport. Fattore per click: **1.2×** (o **1/1.2**
  in uscita). Nessuna animazione: `options` non porta una `duration`.
- Lo `zoomActivationKeyCode` (default `Meta` su macOS, `Control` altrove,
  `isMacOs()` da `@xyflow/system`) è cablato ma **inerte in pratica**: serve a forzare lo
  zoom-su-scroll quando `panOnScroll` è vero, e Nodavia lascia `panOnScroll` a `false`.

### `fitView`: tre configurazioni diverse, non una sola
Il ticket cita "padding .3, maxZoom .85, durata 280ms" come se fosse un'unica chiamata:
nel codice sono **tre chiamate distinte**, con parametri leggermente diversi.

1. **Fit al mount** (prop `fitView` booleana su `<ReactFlow>`, `GraphCanvas.tsx:78-79`):
   `fitViewOptions={{ padding: 0.3, maxZoom: 0.85, minZoom: 0.2 }}`. Avviene durante
   l'inizializzazione dello store, **senza animazione** (nessuna `duration` in questa
   prop). Il `minZoom: 0.2` qui è un **pavimento locale per il solo fit iniziale**, più
   alto del pavimento globale del canvas (0.15): un grafo enorme al primo sguardo non
   scende sotto lo 0.2 di zoom, anche se dopo l'utente può zoomare fuori fino a 0.15.
2. **Ri-fit dopo l'auto-layout** (componente `FitOnKey`, `GraphCanvas.tsx:32-36`): ogni
   volta che la prop `fitKey` cambia (chi sposta le card d'ufficio incrementa un
   contatore), chiama `rf.fitView({ padding: 0.3, maxZoom: 0.85, duration: 280 })`.
   Qui c'è l'animazione (280ms) ma **non c'è un `minZoom` esplicito**: React Flow ricade
   sul minZoom globale del componente, cioè 0.15
   (`fitViewport`, `@xyflow/system/dist/esm/index.mjs:439-451`: `options?.minZoom ?? minZoom`
   dove `minZoom` è quello dello store, 0.15).
3. **Click sul bottone "fit view" dei Controls** (`ControlsComponent`,
   `@xyflow/react/dist/esm/index.mjs:4558-4577`): chiama `fitView(fitViewOptions)` dove
   `fitViewOptions` è la prop *del componente `<Controls>`*, non quella di `<ReactFlow>`.
   `GraphCanvas.tsx:88` istanzia `<Controls />` senza passargliela: è `undefined`. Il fit
   da bottone quindi usa i **default nudi di React Flow**: `padding: 0.1`
   (`fitViewport` sopra), nessuna `duration` (istantaneo), minZoom/maxZoom = quelli
   globali del canvas (0.15/2.5). È un fit visibilmente più stretto (10% di margine
   contro il 30% delle altre due chiamate) e senza animazione.

## 4. Griglia (`Background`)

`GraphCanvas.tsx:87`: `<Background color="#e8e8e7" gap={22} />`. Variante non
specificata → default `BackgroundVariant.Dots`
(`@xyflow/react/dist/esm/index.mjs:4422`, default parametro `variant`). Passo **22px**
in entrambi gli assi (gap è un solo numero, applicato a x e y). Raggio del punto: metà
della "size" di default per la variante dots, che è **1px**
(`defaultSize[BackgroundVariant.Dots] = 1`, stesso file riga ~4417) → raggio disegnato
0.5px, scalato col livello di zoom corrente (il pattern SVG scala con `transform[2]`).
Colore punti **#e8e8e7** (grigio quasi bianco, coerente col token `--line`/`--faint` di
Grafite). Nessun `bgColor` esplicito: lo sfondo del canvas resta quello del contenitore
(bianco/`--bg`), non quello che `Background` disegnerebbe di suo.

## 5. Minimap

`GraphCanvas.tsx:89`: `<MiniMap nodeColor={miniColor} maskColor="rgba(250,250,250,0.78)" pannable zoomable />`.

- **Geometria**: nessuna `style.width`/`height` esplicita → default **200×150px**
  (`defaultWidth`/`defaultHeight`, `@xyflow/react/dist/esm/index.mjs:4668-4669`).
  Posizione non specificata → default `position: 'bottom-right'`
  (stesso file, firma di `MiniMapComponent`, riga ~4703).
- **Colore dei nodi**: funzione `miniColor` (`GraphCanvas.tsx:26-27`), palette
  monocroma per tipo di nodo: `start`/`end` grigi (`#a3a3a3`/`#737373`), `agent` nero
  pieno (`#0a0a0a`); qualunque tipo non mappato ricade su `#a3a3a3`. I nodi `shell` non
  hanno una voce propria in `MINI_COLORS` e ricadono anch'essi sul grigio di default.
- **Maschera** (l'area che rappresenta il viewport visibile): `rgba(250,250,250,0.78)`,
  quasi bianca e semi-trasparente, coerente col resto della UI chiara. Default di
  libreria per confronto: `rgba(240,240,240,0.6)` (`base.css:16`).
- **Interattività**: `pannable` e `zoomable` sono **entrambi attivati esplicitamente**
  (default di libreria: `false` per entrambi, `MiniMapComponent` firma sopra). Si può
  quindi trascinare la minimap per panare il canvas grande, e la rotella sopra la
  minimap zooma il canvas grande.
- **Stile CSS**: `editor.css:226-227` arrotonda gli angoli (`border-radius:12px`,
  `overflow:hidden`) e aggiunge un'ombra (`0 8px 24px -12px rgba(10,10,10,.2)`); nessuna
  di queste è impostata via prop React, sono classi CSS sull'elemento generato.

## 6. Controls

`GraphCanvas.tsx:88`: `<Controls />`, nessuna prop. Tutti i default di libreria
(`ControlsComponent`, `@xyflow/react/dist/esm/index.mjs:4558`):

- **Posizione**: `bottom-left`, orientamento **verticale**.
- **Bottoni mostrati**: zoom-in (+), zoom-out (−), fit-view (icona a mirino),
  interattività (lucchetto), in quest'ordine — tutti e quattro con `showZoom`,
  `showFitView`, `showInteractive` di default a `true`.
- **Zoom-in/out**: vedi §3 (fattore 1.2×, ancorato al centro). I bottoni si disabilitano
  da soli quando si tocca `minZoom`/`maxZoom` (`disabled: maxZoomReached` /
  `minZoomReached`, derivati dallo store).
- **Fit-view**: vedi §3.3 (padding 0.1, istantaneo).
- **Bottone lucchetto (interattività)**: alterna in blocco `nodesDraggable`,
  `nodesConnectable`, `elementsSelectable`. Non è un default parziale: tocca tutti e tre
  insieme, non solo il drag dei nodi.
- **Stile**: `editor.css:221-225` arrotonda il pannello (`border-radius:10px`), aggiunge
  ombra, e ogni bottone ha un separatore inferiore (`border-bottom:1px solid var(--line)`)
  e hover (`background: var(--bg-soft)`); le icone SVG ereditano `fill: var(--ink)`.

## 7. Nodi custom

Quattro tipi (`nodeTypes` in `customNodes.tsx:97`): `start`, `agent`, `shell`, `end`.
Card bianca larga **190px** (`.rfnode`, `editor.css:85`), `border-radius:14px`,
ombra `0 8px 24px -12px rgba(10,10,10,.18)`. Stato:

- `.sel` (nodo selezionato): anello interno di 1.5px nel colore `--ink` invece
  dell'ombra sola (`inset 0 0 0 1.5px var(--ink)`).
- `.off` (nodo con `data.enabled === false`): opacità 0.45.
- `.vuoto` (start senza task, o shell senza comando): bordo tratteggiato interno di 1px
  in `--line`, testo placeholder in corsivo `--faint`.
- Pallino di stato (`.status-dot`) e, per gli agent, un "respiro" dell'intera card
  (`.beating`, keyframe `nodeBeat`) quando `data._breath` è valorizzato: succede solo
  durante uno *run*, mai nell'editor statico, e la sua durata è il ritmo vero dei token
  in streaming (non un tempo fisso).
- Gli **handle** sono cerchi neri di **7×7px** (`.react-flow__handle`, `editor.css:103-104`),
  non i quadratini di default di React Flow.

## 8. Archi

Due tipi (`edgeTypes` in `GraphCanvas.tsx:15`): `flow` (avanti, `FlowStepEdge.tsx`) e
`loop` (ritorno, `LoopEdge.tsx`). Geometria **ortogonale** (smoothstep), non bezier: la
scelta è dichiarata nel commento di `GraphCanvas.tsx:17-19` — con fan-out/fan-in larghi
le bezier collassano in una treccia illeggibile, lo smoothstep si fonde in un "bus"
pulito.

- **Arco in avanti**: stessa geometria del builtin `smoothstep` di React Flow
  (`getSmoothStepPath`, stesso raccordo), reimplementato solo per poter disegnare sopra
  un secondo path (le palline del pulse, che il builtin non permette di aggiungere).
  Raccordo degli angoli: `CORNER = 10` (`loopPath.ts:7`), condiviso fra i due tipi.
  `sourcePosition` default `Bottom`, `targetPosition` default `Top` (le card sono
  impilate in colonna dall'auto-layout).
- **Arco di ritorno**: instradato su una corsia laterale invece di ricalcare l'arco in
  avanti fra la stessa coppia di nodi (altrimenti il tratteggio sparirebbe sotto la
  linea piena). Geometria in `loopPath.ts`: corsia a **135px** dal nodo più esterno
  fra sorgente e target (`LANE`, metà del passo orizzontale fra colonne
  dell'auto-layout), tratto verticale di **26px** sotto la sorgente prima di scartare
  di lato (`DROP`), rientro nel target che sale tanto più in alto quanto più lungo è il
  giro (`rise = 26 + min(70, |lane - targetX| * 0.12)`, così più ritorni convergenti
  sullo stesso nodo non si sovrappongono sulla stessa quota). Visivamente: tratteggiato
  (`stroke-dasharray:5 5`, `editor.css:112`) in `--faint`, contro il grigio pieno
  (`--muted`) dell'arco in avanti.
- **Frecce**: `MarkerType.ArrowClosed`, colore **#737373**, **18×18px**
  (`defaultEdgeOptions`, `GraphCanvas.tsx:20-23`) — più grandi e più scure del default
  di libreria (`defaultMarkerColor = '#b1b1b7'`,
  `@xyflow/react/dist/esm/index.mjs:3728`, dimensione builtin più piccola).
- **Linea di connessione mentre si trascina un nuovo arco**: `ConnectionLineType.SmoothStep`
  esplicito (`GraphCanvas.tsx:77`), coerente con la geometria degli archi già disegnati;
  il default di libreria sarebbe `Bezier`.
- **Interazione**: hover ispessisce e scurisce (`stroke: var(--ink)`), selezione porta
  lo stroke a 2px pieno; un arco "inerte" (`edge-inert`, fuori dal flusso attivo di un
  run) diventa tratteggiato in `--warn` con opacità 0.75; un ritorno "morto" (dopo che
  il ciclo ha convergenza, non consegnerà mai più) si smorza a opacità 0.2 con
  transizione di 0.7s.

## 9. Le palline del pulse

`pulse.tsx`. Non sono un'animazione CSS a `dashoffset`: ogni pallina è un `<circle>` con
un proprio `<animateMotion>` SMIL che percorre il path dell'arco vero (`getTotalLength()`
su un path invisibile dedicato, perché il path disegnato appartiene a `BaseEdge` e non è
referenziabile). La velocità è funzione della **posizione** lungo l'arco, non del tempo:
`calcMode="spline"` con `keySplines="0.55 0 0.45 1"` (ease-in-out marcato, tutta
l'accelerazione al centro).

- **Quando appaiono**: un arco mostra le palline se tocca il nodo selezionato
  (`nodeId` nel contesto, modalità `idle`) o se sta consegnando davvero durante un run
  (`flowing`, modalità `flow`); non appaiono più su un ritorno "morto" (`dead`).
- **Numero e passo**: fra 2 e 8 palline per arco (`Math.min(8, Math.max(2, round(len/95)))`,
  `SPACING = 95`px), quindi un arco corto ne mostra poche, uno lungo fino a otto.
- **Durata del giro**: fra 0.9s e 3.2s (`clamp(len/110, 0.9, 3.2)`, `SPEED = 110`px/s
  medi), sfasate negativamente così sono già in viaggio al primo fotogramma invece di
  partire tutte insieme dal nodo.
- **Dimensione/colore**: raggio 3.4px in modalità `idle`, **4.6px** in modalità
  `flowing` (consegna vera, un filo più grosse); sempre colore `--ink` (nero pieno).
- **`prefers-reduced-motion: reduce`**: le palline **non** scompaiono, restano come
  segnale che quell'arco tocca il nodo selezionato, ma **ferme**: un tratteggio statico
  (`stroke-dasharray:0 30`, spessore 4.5px) al posto dei cerchi animati
  (`EdgeDots`, `pulse.tsx:60-92`, ramo `if (still) return <path className="edge-dots-still" ... />`).
  Confrontare le foto `02` (animate) e `03` (reduced-motion) dell'indice: stesso nodo
  selezionato, stesso istante, l'unica differenza è il flag.

## 10. Scorciatoie da tastiera

Nessuna è cablata da Nodavia: sono tutte i default di `@xyflow/react`
(`ReactFlow`, `@xyflow/react/dist/esm/index.mjs:3728`), tranne dove indicato.

| Tasto | Effetto | Note |
|---|---|---|
| **Backspace** (`deleteKeyCode`) | Cancella nodi/archi selezionati | Default di libreria. **Nell'editor** resta attivo; **in vista Run** Nodavia lo disattiva esplicitamente (`deleteKeyCode={null}`, `App.tsx:1158`) perché lì la rimozione passa dal server via `mutate`, mai da un delete locale di React Flow. |
| **Shift** (`selectionKeyCode`) tenuto + drag sul pane | Selezione a rettangolo invece del pan | Il pan si disattiva mentre Shift è premuto (`panOnDrag: !selectionKeyPressed && panOnDrag`, `@xyflow/system/…/index.mjs:2102`). |
| **Spazio** (`panActivationKeyCode`) tenuto + drag | Forza il pan | Vince anche sopra la selezione a rettangolo. |
| **Meta** (macOS) / **Control** (altri OS) (`multiSelectionKeyCode`, `isMacOs()`) + click | Aggiunge/toglie un nodo o arco dalla selezione multipla | `multiSelectionKeyCode` di libreria. |
| **Meta**/**Control** (`zoomActivationKeyCode`) + scroll | Forzerebbe lo zoom-su-scroll quando `panOnScroll` è vero | Inerte in Nodavia: `panOnScroll` resta `false`, quindi lo scroll zooma già di suo (§2). |
| **Frecce** (quando un nodo selezionato ha il focus da tastiera) | Sposta il nodo di **5px** per pressione, **20px** con **Shift** tenuto | `useMoveSelectedNodes`, `@xyflow/react/dist/esm/index.mjs:1713-1726` (`xVelo=yVelo=5`, `factor: shiftKey ? 4 : 1`). Solo se `disableKeyboardA11y` è `false` (default, non toccato da Nodavia) e il nodo è draggable. |
| **Escape** (nodo/arco con focus) | Deseleziona | `elementSelectionKeys`, gestito negli `onKeyDown` di `NodeWrapper`/`EdgeWrapper`. |
| **Doppio click** sul pane | Zoom-in ancorato al punto cliccato | Vedi §3, `zoomOnDoubleClick = true` default. |

## 11. Cosa NON fa questo canvas (per non progettarlo di più di quel che è)

- Nessun `snapToGrid`/`snapGrid`: il drag dei nodi è libero al pixel, non scatta su
  griglia (anche se la griglia visiva è a 22px).
- Nessun `translateExtent`/`nodeExtent`: pan e posizione dei nodi sono illimitati.
- `attributionPosition` nascosto via `proOptions={{ hideAttribution: true }}` **e**
  ribadito via CSS (`editor.css:228`, `.react-flow__attribution{display:none}`):
  doppia cintura, non un'unica fonte di verità.
- `colorMode="light"` fisso: non segue `prefers-color-scheme`, nessun tema scuro per il
  canvas (a differenza del resto della UI di Nodavia, che ha un tema scuro).
