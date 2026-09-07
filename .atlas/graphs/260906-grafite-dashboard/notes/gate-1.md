# Gate 1 — esito verifica (Q01)

## Il giro

- `python3 -m unittest discover -s tests`: **verde**, 1055/1055 test, 264.7s.
- `python3 build.py`: **ok**, `dist/atlas` rigenerato (1003.1 KB, versione 0.18.1). Era stale (precedente a tutti i fogli spezzati), ora è aggiornato.
- `python3 tests/e2e.py`: **97/97** dopo un fix (vedi sotto). Prima del fix: 96/97, un solo rosso.
- `atlas render --all` da sorgente: 6 grafi rigenerati senza errori (`260825-sync-distribuita`, `260830-atlas-automata`, `260830-atlas-interactions`, `260830-issue-reliability-and-flow`, `260902-atlas-relay`, `260906-grafite-dashboard`).
- Screenshot headless (Chrome, `--force-prefers-reduced-motion`, 1600×1100): guardati `260906-grafite-dashboard` (10/34 nodi) e `260902-atlas-relay` (27/27 nodi, il più pesante, 592KB) come campione di un grafo diverso. Layout leggibile, tipografia Grafite (display/mono/sans) applicata correttamente, legenda e colori di stato coerenti, nessuna scenografia del tema scuro residua.

## Difetto trovato e riparato qui

**e2e.py, riga 197-198**: il controllo "dashboard senza risorse remote" usava `"cdn" not in html` come euristica. Con i font Grafite incorporati in base64 (~200KB di rumore), la tripletta di caratteri `cdn` ricorre per puro caso dentro il blob (`...LdZicdnoDISp...`), facendo scattare un falso positivo indipendente da qualunque caricamento remoto reale. Verificato a mano: nessun `<script src=`, nessun `<link>`, nessun host CDN vero nel pacchetto generato. Corretto il controllo per cercare URL `http(s)://` reali (escludendo l'xmlns SVG, che li contiene per specifica e non per un caricamento), non una sottostringa. Rieseguito: 97/97 verdi. Fix chirurgico, un file, nessun cambio di disegno.

## Voci del ticket, una per una

1. **I fogli spezzati non hanno perso regole.** Confrontati gli insiemi di selettori CSS e di funzioni/selettori JS fra l'ultimo dashboard.css/dashboard.js monolitico (commit `3210ee2`, l'ultimo prima dello split) e i fogli/moduli nuovi:
   - CSS: 293 selettori nel vecchio file (tema scuro escluso a mano dal confronto) contro 288 nei sette fogli nuovi. Le uniche differenze: persi `.theme`, `.theme svg`, `.theme:hover`, `:root[data-theme="dark"]` e le sue due regole figlie (il pulsante e le regole del tema scuro, rimozione intenzionale di F04); guadagnato `code` (nuova regola dichiarata in tokens.css: codice/id in JetBrains Mono ovunque). Nessun'altra perdita.
   - JS: 32 funzioni nominate nel vecchio file, 32 nei cinque moduli nuovi, **nessuna persa, nessuna aggiunta**. Unico selettore DOM sparito: `.theme` (il toggle del tema, coerente con la rimozione).
   - **Esito: verde.**

2. **Grafite come dipendenza a monte, riga di provenienza in testa.** `grafite.offline.css` inizia con `/* Variante offline di grafite.css — Generato da: dist/grafite.css con node build-offline.mjs */`; `grafite.fonts.inline.css` con `/* Variante incorporabile di grafite.css — Generato da: fonts/ con node build-fonts-inline.mjs */`. **Esito: verde.**

3. **I token non hanno doppioni.** Contate le custom property (`--xxx:`) dichiarate nei nove fogli concatenati da `leggi_css_dashboard()`: 48 nomi distinti, **0 doppioni**. Il commento in cima a `tokens.css` documenta esplicitamente quali token Grafite non vengono ridichiarati (`--ink`, `--muted`, `--faint`, `--bg`) e quali diventano alias (`--pane`, `--border`, `--code-bg`). **Esito: verde.**

4. **I cinque colori di stato dei nodi sono quelli di prima, valore per valore.** Estratti i cinque blocchi `--st-*` (frontier/claimed/closed/blocked/out-of-scope, bordo+riempimento+testo = 15 valori) dal tema chiaro del vecchio `dashboard.css` (commit `11c3e22`) e confrontati carattere per carattere con `tokens.css` attuale: **identici**, valore per valore. (Il tema scuro aveva un secondo set di 15 valori diversi: quello è sparito con la rimozione di F04, correttamente.) **Esito: verde.**

5. **Il tema scuro non ha lasciato rovine.** `grep -rl` su tutto `payload/` per `prefers-color-scheme`, `data-theme`, `dark-theme`, `.dark` — **nessun risultato**. Nessun sorgente nomina più il tema scuro. **Esito: verde.**

6. **La pagina non contiene http:// o https:// fuori dai link ai ticket.** Sul dashboard renderizzato di `260906-grafite-dashboard`: un solo `http://`, ed è `xmlns="http://www.w3.org/2000/svg"` dentro le icone SVG (harmless, dichiarazione di namespace, non un link che carica qualcosa). Zero `https://`. Nessun ticket con URL in questo grafo per fare da controprova positiva, ma l'unica occorrenza reale è quella attesa e innocua. **Esito: verde.**

7. **Il peso di una dashboard è scritto nero su bianco.** Vedi sezione dedicata sotto. **Esito: verde** (misurato, nessun problema: è una scelta già presa da chi ha costruito i nodi a monte, qui solo la si documenta per V01).

## Le due voci aggiunte dall'utente

### 1. Topbar 29% / pannello 26%

**Non è un bug**: nell'HTML generato entrambi i numeri sono `29%` (verificato con grep diretto sul file, prima di qualunque rendering: `class="ro"...avanzamento...<b>29%</b>` in topbar, `class="pct" data-count="29">29%` nel pannello). Sono la stessa metrica (`model.progress()`: chiusi/totale sui nodi non-dropped, 10/34), calcolata una sola volta e passata identica a `_topbar` e a `render_panels.panels`.

Quello che ho visto nel primo screenshot (26%) era un **artefatto di cattura**: il pannello di sinistra anima il numero con un count-up JS (`chrome.js`, righe 17-27) che parte da 0 e sale fino al valore finale in ~1.1s, disattivato solo se il viewer ha chiesto `prefers-reduced-motion`. Il mio primo screenshot headless non passava quel flag a Chrome, quindi ha catturato un fotogramma a metà dell'animazione (26% invece di 29%, in salita). Rifatto lo screenshot con `--force-prefers-reduced-motion`: il pannello mostra 29%, identico alla topbar.

Nessuna riga toccata: il comportamento è corretto e accessibile (rispetta `prefers-reduced-motion` come da commento in tokens.css). L'unico correttivo è mio, nel modo di catturare lo screenshot.

### 2. Peso della dashboard: quanto pesano i font

Misurato su `260906-grafite-dashboard/dashboard.html` (10/34 nodi, grafo di riferimento del ticket):

- **Peso totale**: 537.833 byte (≈ 525,2 KB).
- **Font incorporati** (`grafite.fonts.inline.css`, tre famiglie × 3 pesi = 8 `@font-face`): 208.132 byte (≈ 203,3 KB) — **38,7%** del totale.
  - Inter (`--sans`): 96.988 byte (≈ 94,7 KB)
  - Space Grotesk (`--display`): 53.216 byte (≈ 52,0 KB)
  - JetBrains Mono (`--mono`): 57.666 byte (≈ 56,3 KB)
- **Resto della pagina** (HTML, CSS non-font di Grafite e di Atlas, JS, dati del grafo/ticket incorporati, mappa SVG): 329.701 byte (≈ 322,0 KB) — **61,3%**.
- **Se si incorporasse solo il carattere display** (Space Grotesk, quello usato per titoli/etichette/bottoni, non per il corpo del testo né per il codice): 329.701 + 53.216 = **382.917 byte (≈ 374,0 KB)**, cioè **~154,9 KB (~29%) più leggera** di oggi.

Il peso varia per grafo (dipende da quanti nodi/ticket porta con sé): sugli altri cinque grafi rigenerati va da 399.867 byte a 592.567 byte, ma la quota di font incorporati è la stessa cifra fissa (208.132 byte) su tutti, perché il foglio dei font non dipende dal contenuto del grafo — quindi la percentuale che i font pesano sul totale scende quanto più un grafo è grande (dal 52% del grafo più piccolo osservato al 35% di quello più grande).

Numeri per V01, decisione non mia.
