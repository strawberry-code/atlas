/* Il rinquadro (C05, contratto S3): non e' una chiamata sola ma tre, con
   padding/limiti/durata diversi. Modulo a se': calcola SOLO il bersaglio
   (x,y,k,durata) e lo chiede a canvas.js con l'evento "atlas:vai", che e'
   l'unico a toccare 'stato' e 'panel.style.transform' (contratto di
   scambio-solo-via-DOM fra IIFE). Deve caricare DOPO canvas.js: al mount
   dispatcha subito "atlas:vai" e canvas.js dev'essere gia' in ascolto. */
(function () {
  "use strict";

  var MIN_K = .15, MAX_K = 2.5;   // duplicati da canvas.js: due numeri, non vale un modulo condiviso

  // Nodavia e' corto e largo (padding .3/maxZoom .85 bastano da soli): i grafi
  // di Atlas sono spesso alti invece (rank a colonna, molti livelli), e lo
  // stesso fit calcolato sull'altezza scendeva sotto 0.25 - le card
  // diventavano un blocco di colore col testo illeggibile (gate 2, Q02).
  // Sotto questa soglia il rinquadro rinuncia a mostrare tutto il grafo e
  // preferisce restare leggibile: il resto si raggiunge scorrendo, come
  // qualunque lista piu' lunga della finestra che la mostra.
  var MIN_LEGGIBILE = .65;

  var vp = document.querySelector(".viewport");
  var svg = vp.querySelector(".pannello svg");
  var baseW = parseFloat(svg.getAttribute("width")) || 600;
  var baseH = parseFloat(svg.getAttribute("height")) || 200;

  function vai(x, y, k, durata) {
    vp.dispatchEvent(new CustomEvent("atlas:vai", { detail: { x: x, y: y, k: k, durata: durata } }));
  }

  // Punto in spazio-grafo sotto una coordinata di schermo (relativa al
  // viewport): stessa conversione di canvas.js (schermoAGrafo), duplicata
  // qui perche' i moduli si scambiano solo via DOM (contratto di progetto).
  // Letta dal 'dataset' che canvas.js pubblica a ogni disegna(), mai da uno
  // stato proprio: questo modulo non tiene un transform a parte.
  function grafoSottoPunto(px, py) {
    var vk = parseFloat(vp.dataset.vk) || 1, vx = parseFloat(vp.dataset.vx) || 0, vy = parseFloat(vp.dataset.vy) || 0;
    return { x: (px - vx) / vk, y: (py - vy) / vk };
  }

  /* Bounds = l'intero SVG, che render_svg.py gia' ritaglia sui nodi con un
     margine fisso (contratto S1): qui solo la scala perche' ci stia col
     padding voluto, senza superare 'maxZoom' ne' scendere sotto 'minZoomLocale'. */
  function bersaglio(padding, maxZoom, minZoomLocale) {
    var xZoom = vp.clientWidth / (baseW * (1 + padding));
    var yZoom = vp.clientHeight / (baseH * (1 + padding));
    var k = Math.min(xZoom, yZoom, maxZoom);
    if (typeof minZoomLocale === "number") k = Math.max(k, minZoomLocale);
    k = Math.min(MAX_K, Math.max(MIN_K, k));
    return { x: vp.clientWidth / 2 - (baseW / 2) * k, y: vp.clientHeight / 2 - (baseH / 2) * k, k: k };
  }
  // variante 1: al mount. Il pavimento locale di Nodavia era 0.2 (contratto
  // S3): qui e' MIN_LEGGIBILE, piu' alto, per la ragione sopra.
  function fitMount() { var b = bersaglio(.3, .85, MIN_LEGGIBILE); vai(b.x, b.y, b.k, 0); }
  // variante 2: dopo l'auto-layout. Stesso pavimento del mount: senza,
  // ricadrebbe sul minimo globale del canvas (0.15, ancora piu' illeggibile)
  // ogni volta che si preme "layout automatico" su un grafo alto.
  function fitDopoLayout() { var b = bersaglio(.3, .85, MIN_LEGGIBILE); vai(b.x, b.y, b.k, 280); }
  // variante 3: bottone "rinquadra" dei Controls, nessuna opzione locale:
  // ricade sui limiti globali del canvas (0.15/2.5), istantaneo. Bottone
  // esplicito: chi lo preme ha gia' scelto di vedere tutto il grafo, anche
  // a costo del testo piccolo, quindi qui il pavimento di leggibilita' non
  // si applica.
  function fitBottone() { var b = bersaglio(.1, MAX_K, undefined); vai(b.x, b.y, b.k, 0); }

  // Un doppio clic su un nodo o un arco resta il loro clic (sheet.js): qui
  // non deve anche zoomare sopra.
  var NON_PANABILE = "a[data-node],path.edge,circle.port";
  // Fattore ~2x in un colpo solo, stessa formula di canvas.js/minimap.js
  // (k*exp(-delta*.0022)): ln(2)/.0022 ~= 315. Nodavia lo eredita gratis dal
  // dblclick.zoom di default di d3-zoom (S3, C02): qui e' la stessa lettura,
  // non piu' il rinquadro totale che il codice faceva prima di questo gate.
  var DBLCLICK_DELTA = -315;
  vp.addEventListener("dblclick", function (e) {
    if (vp.dataset.locked === "true" || e.target.closest(NON_PANABILE)) return;
    e.preventDefault();
    var r = vp.getBoundingClientRect();
    var g = grafoSottoPunto(e.clientX - r.left, e.clientY - r.top);
    vp.dispatchEvent(new CustomEvent("atlas:zoomverso", { detail: { gx: g.x, gy: g.y, delta: DBLCLICK_DELTA } }));
  });
  vp.addEventListener("atlas:rinquadra-bottone", function () {
    if (vp.dataset.locked !== "true") fitBottone();
  });
  vp.addEventListener("atlas:rilayout", function () {
    if (vp.dataset.locked !== "true") fitDopoLayout();
  });

  (function avvia() {
    var salvata = null;
    try { salvata = JSON.parse(sessionStorage.getItem("atlas-map")); } catch (e) { /* niente da ripristinare */ }
    if (salvata && typeof salvata.k === "number" && typeof salvata.x === "number" && typeof salvata.y === "number") {
      vai(salvata.x, salvata.y, salvata.k, 0);
      return;
    }
    fitMount();   // il mount, come in Nodavia, e' sempre un fit: mai un salto a caso
  })();
})();
