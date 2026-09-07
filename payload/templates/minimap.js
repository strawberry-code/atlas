/* La minimap Grafite (C05): sagoma di tutti i nodi colorata per STATO (non
   per tipo, come in Nodavia: contratto S5, e' l'unica differenza dichiarata),
   il rettangolo della vista corrente, maschera quasi bianca su cio' che non
   e' in vista, trascinabile e zoomabile.
   Modulo a se': non condivide stato con canvas.js (IIFE separate per
   contratto di progetto), legge le posizioni e gli stati gia' disegnati
   dall'SVG principale (niente layout duplicato lato server) e parla col
   motore di pan/zoom solo con eventi custom su '.viewport' condiviso, mai
   per riferimento diretto. */
(function () {
  "use strict";

  var host = document.querySelector(".minimap");
  var vp = document.querySelector(".viewport");
  if (!host || !vp) return;
  var svgGrande = vp.querySelector(".pannello svg");
  if (!svgGrande) return;

  var W = 200, H = 150;   // dimensione di default, contratto S5
  var baseW = parseFloat(svgGrande.getAttribute("width")) || 600;
  var baseH = parseFloat(svgGrande.getAttribute("height")) || 200;
  var scala = Math.min(W / baseW, H / baseH);
  var offX = (W - baseW * scala) / 2, offY = (H - baseH * scala) / 2;

  var NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs) {
    var n = document.createElementNS(NS, tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    return n;
  }
  function mmDaGrafo(gx, gy) { return { x: offX + gx * scala, y: offY + gy * scala }; }
  function grafoDaMm(mx, my) { return { x: (mx - offX) / scala, y: (my - offY) / scala }; }

  // La sagoma: un rettangolo per nodo, copiato dall'SVG gia' disegnato (x/y/
  // width/height in spazio-grafo, la stessa classe st-* per il colore).
  var svg = el("svg", { viewBox: "0 0 " + W + " " + H, width: W, height: H, "aria-hidden": "true" });
  var gNodi = el("g", { transform: "translate(" + offX + "," + offY + ") scale(" + scala + ")" });
  svgGrande.querySelectorAll(".n").forEach(function (n) {
    var card = n.querySelector("rect.card");
    if (!card) return;
    var stato = Array.prototype.filter.call(n.classList, function (c) { return c.indexOf("st-") === 0; })[0] || "";
    // positions.js gira prima di questo modulo e ha gia' scritto data-dx/dy
    // sulle card spostate: la sagoma nasce coerente col layout salvato, non
    // insegue pero' un trascinamento in corso nella stessa sessione.
    gNodi.appendChild(el("rect", {
      class: "mn " + stato,
      x: +card.getAttribute("x") + (+n.dataset.dx || 0), y: +card.getAttribute("y") + (+n.dataset.dy || 0),
      width: card.getAttribute("width"), height: card.getAttribute("height"), rx: 2
    }));
  });
  svg.appendChild(gNodi);
  // maschera evenodd: tutto il riquadro tranne il rettangolo della vista
  // corrente, cosi' il buco resta a piena tinta e il resto si vela (contratto S5).
  var maschera = el("path", { class: "mm-mask", "fill-rule": "evenodd" });
  var cornice = el("rect", { class: "mm-frame" });
  svg.appendChild(maschera);
  svg.appendChild(cornice);
  host.appendChild(svg);

  function rettVisibile() {
    var vk = parseFloat(vp.dataset.vk) || 1, vx = parseFloat(vp.dataset.vx) || 0, vy = parseFloat(vp.dataset.vy) || 0;
    var p1 = mmDaGrafo(-vx / vk, -vy / vk);
    var p2 = mmDaGrafo((-vx + vp.clientWidth) / vk, (-vy + vp.clientHeight) / vk);
    return {
      x1: Math.max(0, Math.min(p1.x, p2.x)), y1: Math.max(0, Math.min(p1.y, p2.y)),
      x2: Math.min(W, Math.max(p1.x, p2.x)), y2: Math.min(H, Math.max(p1.y, p2.y)),
    };
  }
  function aggiorna() {
    var r = rettVisibile();
    maschera.setAttribute("d", "M0,0H" + W + "V" + H + "H0Z"
      + "M" + r.x1 + "," + r.y1 + "H" + r.x2 + "V" + r.y2 + "H" + r.x1 + "Z");
    cornice.setAttribute("x", r.x1); cornice.setAttribute("y", r.y1);
    cornice.setAttribute("width", Math.max(0, r.x2 - r.x1));
    cornice.setAttribute("height", Math.max(0, r.y2 - r.y1));
  }
  aggiorna();   // canvas.js e' gia' passato al mount: si legge subito dal dataset, non si aspetta l'evento
  vp.addEventListener("atlas:vista", aggiorna);

  // Trascinabile: un puntatore giu' ovunque sulla minimap centra la vista
  // grande su quel punto-grafo, muoverlo la segue (contratto S5, "pannable").
  host.addEventListener("pointerdown", function (e) {
    if (vp.dataset.locked === "true") return;
    var r = host.getBoundingClientRect();
    function centra(ev, fine) {
      var g = grafoDaMm((ev.clientX - r.left) * (W / r.width), (ev.clientY - r.top) * (H / r.height));
      vp.dispatchEvent(new CustomEvent("atlas:centra", { detail: { x: g.x, y: g.y, fine: !!fine } }));
    }
    centra(e, false);
    try { host.setPointerCapture(e.pointerId); } catch (err) { /* browser vecchio: pointermove basta lo stesso */ }
    host.classList.add("trascina"); document.body.classList.add("trascina");
    // Stesso schema di canvas.js (C13): il gesto parte subito qui (nessuna
    // soglia sulla minimap), quindi la selezione gia' in corso va azzerata
    // subito e non solo prevenuta in avanti.
    if (window.getSelection) window.getSelection().removeAllRanges();
    function muovi(ev) { centra(ev, false); }
    function fine(ev) {
      centra(ev, true);
      // Tolta sempre: e' quel che impedisce a un pointercancel o a un
      // rilascio fuori dalla minimap di lasciare la pagina bloccata (C13).
      host.classList.remove("trascina"); document.body.classList.remove("trascina");
      host.removeEventListener("pointermove", muovi);
      host.removeEventListener("pointerup", fine);
      host.removeEventListener("pointercancel", fine);
    }
    host.addEventListener("pointermove", muovi);
    host.addEventListener("pointerup", fine);
    host.addEventListener("pointercancel", fine);
  });

  // Zoomabile: la rotella sopra la minimap zooma la vista grande, ancorata
  // allo stesso punto-grafo che sta sotto il cursore (contratto S5, "zoomable").
  host.addEventListener("wheel", function (e) {
    if (vp.dataset.locked === "true") return;
    e.preventDefault();
    var r = host.getBoundingClientRect();
    var g = grafoDaMm((e.clientX - r.left) * (W / r.width), (e.clientY - r.top) * (H / r.height));
    var d = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaMode === 2 ? e.deltaY * vp.clientHeight : e.deltaY;
    d = Math.max(-120, Math.min(120, d));
    vp.dispatchEvent(new CustomEvent("atlas:zoomverso", { detail: { gx: g.x, gy: g.y, delta: d } }));
  }, { passive: false });
})();
