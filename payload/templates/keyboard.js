/* Navigazione da tastiera del canvas (C12): frecce per panare, piu'/meno per
   lo zoom, tab che scorre i nodi in ordine di rango con un anello di focus
   visibile, invio che apre la scheda del ticket. Nessun evento nuovo su
   canvas.js: pan e zoom riusano "atlas:centra"/"atlas:zoomfattore", gia'
   dispatchati da minimap.js/controls.js, cosi' il lucchetto e la quiete
   (prefers-reduced-motion) restano gestiti in un solo posto.

   Il tab nativo visiterebbe i nodi nell'ordine del DOM (quello di
   graph.json), non nel rango del layout: qui resta raggiungibile un nodo
   alla volta (tabindex 0/-1 a rotazione), cosi' il resto della pagina non
   cambia posto nel giro di tab - solo l'ordine FRA i nodi cambia, ed entrare/
   uscire dal gruppo resta il tab nativo (mai intercettato ai bordi). */
(function () {
  "use strict";

  var vp = document.querySelector(".viewport");
  if (!vp) return;

  // Ordine di rango: stessa lettura di minimap.js (rect.card x/y, gia'
  // disegnate dal layout server) - mai un ricalcolo lato client.
  var voci = Array.prototype.map.call(document.querySelectorAll(".map .n"), function (n) {
    var card = n.querySelector("rect.card");
    var a = n.closest("a[data-node]");
    return a && card ? { id: a.dataset.node, el: a, x: +card.getAttribute("x"), y: +card.getAttribute("y") } : null;
  }).filter(Boolean);
  voci.sort(function (p, q) { return p.y - q.y || p.x - q.x; });
  if (!voci.length) return;

  voci.forEach(function (v, i) { v.el.tabIndex = i === 0 ? 0 : -1; });

  function indiceDi(el) {
    for (var i = 0; i < voci.length; i++) if (voci[i].el === el) return i;
    return -1;
  }

  // L'anello di focus e' lo stesso '.sel' del clic (sheet.js, canvas.css):
  // duplicato qui apposta, i moduli si scambiano solo via DOM (contratto).
  function segna(id) {
    var precedente = document.querySelector(".map .n.sel");
    if (precedente) precedente.classList.remove("sel");
    var carta = document.getElementById("node-" + id);
    if (carta) carta.classList.add("sel");
  }

  // Il focus puo' arrivare anche da un clic (sheet.js seleziona() gia' marca
  // '.sel'): qui si allinea solo la rotazione del tabindex, segna() e' innocua
  // a rimarcare lo stesso nodo due volte.
  vp.addEventListener("focusin", function (e) {
    var i = indiceDi(e.target);
    if (i < 0) return;
    voci.forEach(function (v, j) { v.el.tabIndex = j === i ? 0 : -1; });
    segna(voci[i].id);
  });

  document.addEventListener("keydown", function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey) return;

    if (e.key === "Tab") {
      var i = indiceDi(document.activeElement);
      if (i < 0) return;
      var j = i + (e.shiftKey ? -1 : 1);
      if (j < 0 || j >= voci.length) return;   // bordo del giro: il tab nativo esce dalla pagina
      e.preventDefault();
      voci[j].el.focus();
      return;
    }

    if (e.key === "Enter") {
      if (indiceDi(document.activeElement) < 0) return;
      e.preventDefault();
      // Stesso evento di un clic vero (sheet.js ascolta "click" su document):
      // nessun riferimento diretto fra moduli, solo un evento sul DOM condiviso.
      document.activeElement.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
      return;
    }

    // 'sheet-open' e' sparita con la scheda modale (S12): il pannello destro
    // ora resta sempre visibile accanto alla mappa, e chiude solo con un
    // gesto esplicito (bottone o Escape, sheet.js), mai da solo. Le frecce
    // restano sue solo mentre mostra proprio la vista Nodo - la stessa
    // ragione di prima, il fuoco e' li' dentro (sheet.js sposta il fuoco sul
    // bottone di chiusura ad ogni apertura).
    var pannelloNodo = document.querySelector(".notifiche");
    if (pannelloNodo && document.documentElement.dataset.notifiche !== "chiuso"
        && pannelloNodo.dataset.vista === "nodo") return;
    var fuoco = document.activeElement;
    if (fuoco.closest && fuoco.closest("input,textarea,select,[contenteditable]")) return;

    if (e.key === "+" || e.key === "=" || e.key === "-" || e.key === "_") {
      e.preventDefault();
      var fattore = (e.key === "-" || e.key === "_") ? 1 / 1.2 : 1.2;   // stesso passo dei bottoni Controls (S3)
      vp.dispatchEvent(new CustomEvent("atlas:zoomfattore", { detail: { fattore: fattore } }));
      return;
    }

    var passi = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    var p = passi[e.key];
    if (!p) return;
    e.preventDefault();
    // Nessun evento di pan dedicato: si legge il centro corrente da
    // vp.dataset (canvas.js lo pubblica ad ogni disegna()), si sposta di un
    // passo in spazio-grafo e si richiede lo stesso "atlas:centra" della
    // minimap - istantaneo, quindi gia' quieto di suo (nessuna easing da spegnere).
    var k = parseFloat(vp.dataset.vk) || 1;
    var vx = parseFloat(vp.dataset.vx) || 0, vy = parseFloat(vp.dataset.vy) || 0;
    var passo = 60 / k;
    var gx = (vp.clientWidth / 2 - vx) / k + p[0] * passo;
    var gy = (vp.clientHeight / 2 - vy) / k + p[1] * passo;
    vp.dispatchEvent(new CustomEvent("atlas:centra", { detail: { x: gx, y: gy, fine: true } }));
  });
})();
