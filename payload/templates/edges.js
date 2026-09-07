/* Le palline sugli archi del nodo selezionato (A05, porta di Nodavia
   editor/pulse.tsx): dicono in che verso passa la dipendenza senza dover
   seguire la freccia a occhio. Il nodo selezionato e' quello con '.sel' su
   '.n' (sheet.js lo mette al clic, keyboard.js al focus da tastiera): questo
   modulo non possiede quella classe, la osserva via MutationObserver, perche'
   i moduli di questa pagina si scambiano solo per DOM, mai per riferimento
   diretto fra IIFE (contratto di progetto). Stessa ragione per cui non
   dispatcha niente su '.viewport': nessun altro modulo ha bisogno di sapere
   che le palline sono cambiate.

   L'andatura non e' un dashoffset animato: ogni pallina e' un <circle> con un
   proprio <animateMotion> SMIL che percorre il path vero dell'arco
   (getTotalLength), calcMode spline con keySplines a ease-in-out marcato, cosi'
   la velocita' dipende dalla posizione lungo l'arco (lenta ai nodi, veloce a
   meta' tratta) e non dal tempo: un dashoffset da' per forza la stessa
   velocita' istantanea a ogni pallina, questo no. Sfasamento iniziale
   negativo: le palline sono gia' in viaggio al primo fotogramma. */
(function () {
  "use strict";

  var svg = document.querySelector(".pannello svg");
  if (!svg) return;
  var vp = document.querySelector(".viewport");
  var NS = "http://www.w3.org/2000/svg";

  var SPEED = 110;    // px/s medi (porta di pulse.tsx)
  var SPACING = 95;   // distanza media fra due palline
  var EASE = "0.55 0 0.45 1";

  var mqQuiete = matchMedia("(prefers-reduced-motion: reduce)");
  var quiete = mqQuiete.matches;

  var selezionato = null;               // id del nodo scelto, null se nessuno
  var archiObs = new MutationObserver(schedulaRidisegno);
  var rafPendente = 0;

  function svuota() {
    var vecchi = svg.querySelectorAll(".edge-dots,.edge-dots-still");
    for (var i = 0; i < vecchi.length; i++) vecchi[i].remove();
  }

  function creaAnimazione(nome, attrs) {
    var el = document.createElementNS(NS, nome);
    for (var k in attrs) el.setAttribute(k, attrs[k]);
    return el;
  }

  // Una pallina in moto: posizione dal path (spline, non lineare) e opacita'
  // che nasce staccandosi dal nodo e si assorbe in quello dopo (0;1;1;0),
  // invece di comparire e sparire di scatto sul bordo dell'arco.
  function pallina(d, dur, begin) {
    var c = document.createElementNS(NS, "circle");
    c.setAttribute("r", "3.4");
    c.appendChild(creaAnimazione("animateMotion", {
      dur: dur.toFixed(2) + "s", begin: begin, repeatCount: "indefinite",
      calcMode: "spline", keyPoints: "0;1", keyTimes: "0;1", keySplines: EASE, path: d,
    }));
    c.appendChild(creaAnimazione("animate", {
      attributeName: "opacity", dur: dur.toFixed(2) + "s", begin: begin,
      repeatCount: "indefinite", values: "0;1;1;0", keyTimes: "0;0.12;0.86;1",
    }));
    return c;
  }

  // Numero di palline e durata del giro dalla lunghezza vera del path: un
  // arco corto con otto palline sarebbe una collana, uno lungo con due
  // resterebbe vuoto (porta di pulse.tsx, SPACING/SPEED sopra).
  function animate(path) {
    var d = path.getAttribute("d");
    var len = path.getTotalLength();
    if (!len) return;
    var n = Math.min(8, Math.max(2, Math.round(len / SPACING)));
    var dur = Math.min(3.2, Math.max(0.9, len / SPEED));
    var g = document.createElementNS(NS, "g");
    g.setAttribute("class", "edge-dots");
    g.setAttribute("pointer-events", "none");
    for (var i = 0; i < n; i++) {
      g.appendChild(pallina(d, dur, "-" + ((dur * i) / n).toFixed(3) + "s"));
    }
    path.parentNode.insertBefore(g, path.nextSibling);
  }

  // prefers-reduced-motion: restano i punti fermi sull'arco, che sono
  // comunque il segnale (questo arco tocca il nodo selezionato), senza moto.
  function ferma(path) {
    var still = document.createElementNS(NS, "path");
    still.setAttribute("class", "edge-dots-still");
    still.setAttribute("d", path.getAttribute("d"));
    path.parentNode.insertBefore(still, path.nextSibling);
  }

  function archiDi(id) {
    return svg.querySelectorAll('path.edge[data-from="' + id + '"],path.edge[data-to="' + id + '"]');
  }

  function disegna() {
    svuota();
    archiObs.disconnect();
    if (!selezionato) return;
    var archi = archiDi(selezionato);
    for (var i = 0; i < archi.length; i++) {
      archiObs.observe(archi[i], { attributes: true, attributeFilter: ["d"] });
      if (quiete) ferma(archi[i]); else animate(archi[i]);
    }
  }

  // drag.js (C10) riscrive 'd' in tempo reale mentre una card si sposta: le
  // palline gia' disegnate portano un 'path' proprio, copia statica della
  // stringa 'd' al momento della costruzione (SMIL non segue un riferimento
  // vivo), quindi vanno ricostruite quando l'arco cambia forma. Una mutazione
  // per pointermove sarebbe una ricostruzione per frame: si raccoglie con
  // requestAnimationFrame, cosi' un trascinamento lungo ne fa al piu' una a
  // fotogramma invece che una a evento.
  function schedulaRidisegno() {
    if (rafPendente) return;
    rafPendente = requestAnimationFrame(function () { rafPendente = 0; disegna(); });
  }

  function leggiSelezione() {
    var sel = svg.querySelector(".n.sel");
    return sel ? sel.id.replace(/^node-/, "") : null;
  }

  function aggiorna() {
    var attuale = leggiSelezione();
    if (attuale === selezionato) return;
    selezionato = attuale;
    disegna();
  }

  new MutationObserver(aggiorna).observe(svg, { attributes: true, attributeFilter: ["class"], subtree: true });
  mqQuiete.addEventListener("change", function (e) { quiete = e.matches; disegna(); });
  if (vp) {
    vp.addEventListener("atlas:nodo-spostato", disegna);
    vp.addEventListener("atlas:ricalcola-archi", disegna);
  }

  aggiorna();
})();
