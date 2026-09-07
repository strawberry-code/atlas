# Gate 3 · lo schermo e' Grafite dal bordo al centro

Prima passata: verifica sulle foto di V03, due difetti che cambiavano il disegno
registrati con `atlas ask` (Q001 sull'accento, Q002 sui controlli a riquadro), gate
lasciato aperto. Risposta dell'utente: applicare entrambe, monocromo pieno. Questa e'
la rimisurazione dopo l'applicazione, su foto rifatte da zero (`tests/screenshot_
dashboard.py`, stesso metodo, sei grafi). Nel frattempo Q02 ha chiuso e toccato
`fitview.js` (pavimento di zoom, doppio clic): non ne fa parte questo gate, il canvas
resta suo.

## Le sette leggi

1. **Monocromo, colore solo come segnale.** VERDE (era rosso, Q001 risolto). `--accent`
   non esiste piu' in `tokens.css`: icona del brand, i tre numeri della topbar, l'anello
   di avanzamento (`rg-a`/`rg-b` ora entrambi ink), ogni hover di bottone/link/chip e i
   link del markdown sono `var(--ink)`. Restano colorati solo i cinque stati dei nodi, i
   semantici Grafite dove segnalano davvero qualcosa (`--warn` sul badge di attesa,
   `--down` su "scaduta da 4g", `--ok` sulla conferma di copia), e i tre token senza
   equivalente (`--edge*`, `--gridline`, `--scrim`). Verificato in foto: numeri e icona
   neri, anello nero pieno, nessun teal residuo su nessuno dei sei grafi fotografati.
2. **Tre voci tipografiche, ruoli fissi.** VERDE, invariato.
3. **Numeri protagonisti e animati.** VERDE, invariato (count-up gia' a posto).
4. **Whitespace come materiale.** VERDE (era rosso, Q002 risolto). Tolti i bordi da
   readout topbar, icona del brand, `.viewmode`, `.sheet-close`, bottoni di notifiche/
   pairing, `.notif-card`, chip della legenda: ora sfondo pieno, e dove il controllo era
   un `<button>` nativo serviva anche `border:none` esplicito, non solo togliere la mia
   regola (trovato in foto sulla legenda: senza, torna il bordo nativo del browser,
   stesso bug su un secondo giro con `.mark`/`.viewmode` quando il loro sfondo pieno
   coincideva col fondo della topbar, `--bg-soft` = `--pane-2`: invisibili finche' non
   verificato in foto, corretti su `--pane`). Restano gli unici bordi ammessi da Grafite:
   hairline di separazione (intestazione tabella, `.md pre`) e dashed (`.notif-card.
   notif-contesto`, come la dropzone). I chip di stato (`.tchip`, canvas) non sono stati
   toccati: il loro bordo e' semantico, non decorativo (il "bloccato" ha riempimento
   trasparente e vive solo del bordo).
5. **Motion soft, due easing tre durate.** VERDE, gia' risolto nella prima passata.
6. **Micro-segnali vivi.** VERDE, invariato.
7. **Restraint.** VERDE (era giallo). Tolto il colore di marca diffuso e il linguaggio a
   riquadri: resta nero su bianco, stati a colore, movimento gentile.

## I tells

- **Pallino che respira**: presente, ora nero (era gia' ink, non toccato da Q001).
- **Label maiuscolo tracciato**: presente, invariato.
- **Righe che scivolano allo hover**: presente, esteso a `.notif-card` (prima bordo che
  scuriva, ora sfondo che scurisce + rientro come le altre righe dense).
- **Bottoni che si sollevano**: presente (era assente). `.notif-azioni button` e
  `.pairing-telegram` consumano `.btn-primary`/`.btn-ghost` di Grafite (lift -1px hover,
  scala .98 al clic, gia' incluso nella ricetta); `.viewmode`, `.sheet-close`, `.notif-
  muto`, i chip di legenda hanno lo stesso lift scritto a mano, perche' non sono bottoni
  di testo semplice. Gerarchia primaria/secondaria introdotta dove mancava: la prima
  azione di ogni card (retry/confirm/acknowledge) e' `.btn-primary` nera piena, le altre
  (cancel/decline) sono `.btn-ghost`: "Riprova" e "Annulla" non sono piu' lo stesso
  bottone due volte.

## Il difetto opposto

Confermato dalla prima passata (bshape/bmark, durate/easing) e chiuso li'. Nessuna
regola nuova ricopiata in questo giro: le sostituzioni sono state valore per token
(`var(--accent)` -> `var(--ink)`/`var(--ok)`), non nuovi hex.

## Cosa NON e' cambiato (deciso, non dimenticato)

- I cinque colori di stato dei nodi: stessi valori esatti di prima (`--st-frontier
  #7a5f00`, `--st-claimed #1d4ed8`, `--st-closed #04724f`, `--st-blocked #8ea0aa`,
  `--st-out-of-scope #b91c1c`, con le loro `-bg`/`-tx`), non toccati in nessun file.
- Il bordo di `.sheet` (la scheda del ticket) resta: non era nell'elenco approvato, e
  toccarlo avrebbe cambiato un pannello intero senza foto di verifica dedicate.
- `.legend .chip.on` non si inverte in nero pieno come `.seg-opt.on` di Grafite: il
  quadratino di stato dentro porta un colore tarato sul fondo chiaro, e nero pieno lo
  avrebbe spento. Diventa opaco (`--bg-soft`) invece che tradotto, stessa idea di
  "selezionato si nota", contrasto del quadratino intatto.

## Verifica

- `python3 -m unittest discover -s tests`: 1095/1095, verde su ogni giro dopo una
  modifica (compreso il fix del test `pairing-telegram` che assumeva la vecchia classe).
- Foto rifatte da zero con `tests/screenshot_dashboard.py` sui sei grafi (incluso
  `260830-atlas-interactions`, notifiche vere: badge "1" ambra, "scaduta da 4g" rosso,
  card di attenzione col bordo sinistro warn, tutti invariati, tutti semantici).
- Due difetti di sfondo-invisibile trovati SOLO guardando le foto (non nel codice a
  occhio): `.legend .chip` senza `border:none` esplicito tornava al bordo nativo del
  `<button>`; `.mark`/`.viewmode` con sfondo `--bg-soft` sparivano perche' identico al
  fondo della topbar (`--pane-2`). Corretti, rifotografati, confermati.

## Esito

Nessuna voce rossa. Chiudo il gate.
