# GATE 2 — il canvas è quello di Nodavia (Q02)

Confronto fra `notes/nodavia/` (C01, foto + `canvas-contract.md`) e `notes/atlas/`
(V03, foto + `INDEX.md`), riga per riga sul codice in `payload/templates/*.js`.
Due correzioni applicate qui (`fitview.js`), una segnalazione registrata a valle
(`atlas fog --for Q04`).

## Confronto coppia per coppia

| Coppia | Esito |
|---|---|
| Apertura rinquadrata (`01` vs `01`) | Stessa idea (fitView al mount, nessuna selezione). Prima di questa sessione: **difetto**, non differenza voluta — vedi sotto. Superficie diversa per progetto (dashboard con topbar/pannelli/notifiche vs editor nudo): voluto. Colore nodi per **stato** (Atlas) vs per **tipo** (Nodavia): voluto, è la ragione stessa della dashboard. |
| Selezione, pulse animato (`03a/03b` vs `02`) | Identico: anello `.sel`, palline su tutti gli archi che toccano il nodo (3 su + 5 giù in Atlas, 3+1 in Nodavia), `<animateMotion>` SMIL con lo stesso `calcMode=spline`/`keySplines`. Confermato via codice: `SPEED=110`, `SPACING=95`, raggio 3.4, clamp durata 0.9-3.2s — stessi numeri di `pulse.tsx` (`payload/templates/edges.js`). |
| Reduced motion (`04` vs `03`) | Identico: palline sostituite da tratteggio statico sugli stessi archi, stesso segnale senza moto. |
| Minimap (`07` vs `05`) | Stessa geometria (200x150, basso-destra, maschera quasi bianca, pannable+zoomable). Colore per stato vs tipo: stessa differenza voluta di sopra. |
| Controls (`08` vs `06`) | Stessi 4 bottoni, stesso ordine (zoom-in, zoom-out, fit, lucchetto). Quinto bottone Atlas (ripristina layout, C10): voluto, Nodavia non ha drag libero delle card da ripristinare. |
| Arco di ritorno a riposo (`09` vs `07`) | Stessa geometria quando raggiunta: corsia laterale, tratteggio, non sovrapposta all'arco in avanti. Verificato nel codice: `LANE=135, DROP=26, CORNER=10, rise=26+min(70,|lane-tx|*.12)` (`drag.js`) — stessi numeri di `loopPath.ts`. Ma vedi la terza segnalazione: nessun grafo reale ci arriva. |
| Arco di ritorno selezionato (`10a/10b` vs `08`) | Identico: le palline compaiono anche sulla corsia tratteggiata quando il nodo tocca sia un arco sano sia il ritorno, si spostano fra i due fotogrammi. |
| Hover (`02`, solo Atlas) | Concetto solo Atlas (illumina l'intera catena di dipendenze), Nodavia ha solo un ispessimento dell'arco sotto il puntatore. Non è un sottoinsieme, è più ambizioso: nessun pezzo mancante. |
| Scheda ticket / vista tabellare (`05`, `06`, solo Atlas) | Fuori perimetro di Q02 (superficie, non canvas — Q03). Concetti che Nodavia non ha (non è un tracker): nessun pezzo mancante. |

## Gesti verificati riga per riga sul codice

- **Zoom ancorato al puntatore** (rotella/pinch): confermato in `canvas.js`,
  `impostaZoom(k,cx,cy)` — legge il punto-grafo sotto il cursore alla scala
  vecchia, poi trasla per farlo tornare sotto lo stesso punto schermo. Stesso
  principio del `wheel.zoom` nativo di d3-zoom (contratto S3).
- **Zoom dei bottoni ancorato al centro**: `controls.js` dispatcha
  `atlas:zoomfattore` senza punto, e `canvas.js` lo applica a
  `vp.clientWidth/2, vp.clientHeight/2`. Fattore **1.2x** / **1/1.2x**, come
  Nodavia (`scaleBy(1.2)`).
- **Limiti 0.15 / 2.5**: `MIN_K=.15, MAX_K=2.5` in `canvas.js`, duplicati (per
  contratto di modulo) in `fitview.js` e `controls.js`. Identici a Nodavia.
- **`fitView`, tre varianti**: verificate una per una in `fitview.js`.
  - Mount: `bersaglio(.3, .85, MIN_LEGGIBILE)`, durata 0. Nodavia: padding .3,
    maxZoom .85, minZoom **.2** locale. **Cambiato qui**: vedi decisione 1.
  - Dopo-layout: `bersaglio(.3, .85, MIN_LEGGIBILE)`, durata 280ms. Nodavia:
    stesso padding/maxZoom, nessun minZoom locale (ricade sul minimo globale
    .15). **Cambiato qui per la stessa ragione della decisione 1** (altrimenti
    il bottone "layout automatico" riproduce lo stesso difetto su un grafo alto).
  - Bottone Controls: `bersaglio(.1, MAX_K, undefined)`, istantaneo. Identico
    a Nodavia (fit nudo di React Flow: padding .1, nessun minZoom locale).
- **Passo griglia**: `GRID=22` in `canvas.js`. Identico a Nodavia
  (`<Background gap={22}>`).
- **Soglia clic/trascinamento**: `SOGLIA=4` in `drag.js` (nodo), soglia
  equivalente (Manhattan, >4) in `canvas.js` (pan). Non è un numero del
  contratto Nodavia (lì il drag è nativo di React Flow, non un gesto
  costruito a mano): coerenza interna verificata, non c'è un termine di
  paragone esterno da rispettare.

## Le tre segnalazioni: decisioni prese

**1. Leggibilità all'apertura — corretto qui.**
Misurato sul grafo vero (34 nodi, SVG 1390x3334, viewport 972x1046 nella
finestra 1600x1100 delle foto): il fit naturale sull'altezza dava k=0.241,
sopra il pavimento locale di Nodavia (.2) quindi mai corretto da quello.
Risultato: testo a ~2.8px, illeggibile (confermato dallo screenshot
`01-apertura-rinquadrata.png`). Decisione: **minimo di zoom leggibile con
scorrimento**, non fit a tutti i costi — coerente con l'opzione che la
nebbia stessa proponeva. Aggiunta una costante `MIN_LEGGIBILE=.65` in
`fitview.js`, usata come pavimento locale sia per il mount sia per il
ri-fit dopo l'auto-layout (che aveva lo stesso problema, nessun pavimento
locale, ricadeva sul minimo globale .15, ancora peggio). Verificato con
Playwright su tre candidati (.45/.55/.65): a .65 il testo delle card
(11.5px/14px SVG) è comodamente leggibile, a costo di mostrare ~5-6 righe
invece del grafo intero (si scorre per il resto, come qualunque lista più
lunga della finestra). Il bottone esplicito "rinquadra" dei Controls resta
senza pavimento: chi lo preme ha già scelto di vedere tutto, testo piccolo
incluso.

**2. Doppio clic — corretto qui, allineato a Nodavia.**
Prima: rinquadrava tutto il grafo (comportamento proprio di Atlas, non un
default ereditato). Nodavia eredita gratis lo zoom-in ancorato al punto di
`dblclick.zoom` di d3-zoom (default, contratto S3/S10). Cambiato in
`fitview.js`: il listener ora calcola il punto-grafo sotto il cursore
(nuova `grafoSottoPunto`, stessa formula di `schermoAGrafo` di `canvas.js`,
duplicata per lo stesso motivo delle altre costanti) e dispatcha
`atlas:zoomverso` con un fattore ~2x (`DBLCLICK_DELTA=-315`,
`k*exp(-delta*.0022)~=k*2`), lo stesso canale già usato dalla rotella e
dalla minimap. Verificato con Playwright: il punto-grafo sotto il cursore
resta lo stesso identico prima e dopo il doppio clic (1393.46,1687.00 in
entrambi i casi), zoom passato da .65 a 1.30 (esattamente 2x). Il
rinquadro-tutto non è più raggiungibile da un doppio clic (resta il
bottone "fit" dei Controls).

**3. Arco di ritorno irraggiungibile — registrato, non risolto qui.**
Confermato leggendo il codice: `doctor.show_doctor` avvolge già
`convergence()` in un `try/except (ConfigError, StateError)` per-grafo e
stampa una diagnosi (`payload/core/doctor.py:127-139`); `render_panels.py`
(`_blocco_caution`, riga 97) chiama la stessa `convergence()` **senza** quella
rete, quindi un ciclo fa fallire `atlas render` per intero, per qualunque
grafo del progetto, non solo per il back-edge. Il codice che disegna il
ritorno (`render_svg.py`, `render_edges.py`, `edge_geometry.py`) è corretto
e testato (vedi `09`/`10` sopra), semplicemente irraggiungibile in pratica.
Fuori dal perimetro di questo cancello (tocca `render_panels.py`/
`topology.py`, non `canvas.js`/`canvas.css`) e fuori da quello di V03 per lo
stesso motivo. **Registrato con `atlas fog --for Q04`**: Q04 decide se
allineare `render_panels.panels()` allo stesso try/except di `doctor` fa
parte di questo epic o va tracciato come difetto atlas-core a sé, prima
della consegna. Non blocca la chiusura di Q02: la fedeltà del canvas (fit,
zoom, drag, palline, geometria dell'arco) è verificata a prescindere da
questo crash, che riguarda la pipeline di rendering, non l'aspetto del
canvas.

## Il prezzo

- File toccati: solo `payload/templates/fitview.js`, 96 righe (era 66) —
  ben sotto le 200.
- Nessun altro file di `payload/templates/` toccato: `canvas.js` (197),
  `drag.js` (179), `edges.js` (139), `minimap.js` (116), `keyboard.js` (103),
  `positions.js` (75), `controls.js` (54) — tutti letti e verificati riga
  per riga contro il contratto, nessuna modifica necessaria.
- `prefers-reduced-motion`: verificato via codice (`canvas.js` mqQuiete,
  `edges.js` mqQuiete) — animazioni SMIL e l'easing dello zoom a rotella si
  fermano entrambi, non solo le palline.
- Cinquanta nodi: il grafo di riferimento (34 nodi, 1390x3334 SVG) non mostra
  segni di rallentamento nelle catture Playwright; l'unico costo osservato
  è visivo (leggibilità), risolto sopra, non di prestazioni.
- Suite: `python3 -m unittest discover -s tests` — **1095/1095 verdi**,
  258.2s, nessun fallimento.

## Verdetto

Con le due correzioni sopra, il canvas Atlas e chi conosce Nodavia
riconoscerebbe la stessa interfaccia: stessi limiti di zoom, stesso
ancoraggio, stessa griglia, stesse palline, stessa geometria del ritorno,
stesso doppio clic. L'unica differenza voluta rispetto al fit-to-window di
Nodavia (il pavimento di leggibilità) è dichiarata e motivata sopra, non
nascosta. Il crash su ciclo (segnalazione 3) è un difetto reale ma non è
del canvas: registrato a Q04, non blocca questo cancello.
