# Foto di riferimento del canvas Nodavia

Catturate con Chrome headless (`playwright-core`, Chrome di sistema) puntato su
`nodavia/web` in dev (`npm run dev`, porta 5173), finestra 1600×1100, viste in
`view=editor` sui grafi in `nodavia/server/graphs/`. Il server è stato avviato in
background, lavorato in parallelo (lettura sorgenti per il contratto) e **spento a fine
cattura** — non è rimasto acceso.

Nessun file di Nodavia è stato toccato: solo lettura e navigazione da browser.

| File | Grafo | Cosa mostra |
|---|---|---|
| `01-tre-pareri-vista-iniziale.png` | `02-tre-pareri` | Vista iniziale rinquadrata (fitView al mount): fan-out da `start` a 3 agent in parallelo, fan-in su `sintesi`, poi `end`. Nessun nodo selezionato, nessuna pallina di pulse (nessun nodo selezionato). Si vedono Controls (basso-sinistra) e MiniMap (basso-destra) nella loro posizione di default. |
| `02-tre-pareri-selezione-pulse-animato.png` | `02-tre-pareri` | Nodo `sintesi` selezionato (bordo interno pieno): le palline del pulse sui tre archi entranti (da `pragmatico`/`architetto`/`scettico`) e su quello uscente verso `end`, **in movimento** (nessun `prefers-reduced-motion`). Le palline sono in posizioni sparse lungo gli archi, non allineate: è l'animazione SMIL vera, non un fotogramma a metà di un'altra animazione. |
| `03-tre-pareri-selezione-pulse-reduced-motion.png` | `02-tre-pareri` | Stessa selezione, stesso istante, con `prefers-reduced-motion: reduce` forzato (`page.emulateMedia`). Le palline sono sostituite da un tratteggio statico e regolare sugli stessi archi: il confronto pixel-per-pixel con la `02` è la prova che il flag funziona (vedi contratto §9). |
| `04-tre-pareri-full-per-minimap-e-controls.png` | `02-tre-pareri` | Stessa inquadratura di `01`/`02`/`03`, usata come sorgente per i due ritagli sotto. |
| `05-minimap-crop.png` | `02-tre-pareri` | Ritaglio della sola MiniMap (200×150 default React Flow): nodi monocromi (agent neri, start/end grigi), maschera del viewport quasi bianca e semi-trasparente. |
| `06-controls-crop.png` | `02-tre-pareri` | Ritaglio della sola pulsantiera Controls: zoom-in, zoom-out, fit-view, lucchetto (interattività), in colonna verticale, angoli arrotondati. |
| `07-live-steering-back-edge.png` | `03-live-steering` | Il ciclo `autore → critico → autore`: l'arco di ritorno (`loop`) è instradato su una corsia laterale tratteggiata a destra della colonna, non sovrapposto all'arco in avanti. Nessun nodo selezionato. |
| `08-live-steering-back-edge-selezionato.png` | `03-live-steering` | Stesso grafo con `critico` selezionato: le palline del pulse toccano anche l'arco di ritorno (visibili come piccoli punti sulla corsia tratteggiata), non solo gli archi in avanti che entrano/escono dal nodo. |

## Cosa manca e perché

Nessuna scena della lista del ticket è mancante: vista iniziale, selezione con pulse
(animato e reduced-motion), arco di ritorno, minimap, pulsantiera sono tutte coperte.
Non c'è uno scatto dedicato al grafo `01-primo-grafo` (il più semplice, 4 nodi in
sequenza): non aggiunge nulla che `03-live-steering` non mostri già (stessa forma a
colonna, senza fan-out/fan-in né loop), quindi non è stato catturato per non moltiplicare
foto equivalenti.
