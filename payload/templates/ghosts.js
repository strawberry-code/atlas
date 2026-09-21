/* La trasparenza degli archi sotto le card, tenuta in pari col trascinamento.
   render_edge_ghosts.py genera lo stato a riposo (un piano opaco fra archi e
   card, piu' una copia sfumata dell'arco ritagliata sulla card): qui la stessa
   regola, rifatta sulle posizioni correnti ogni volta che drag.js ha
   ridisegnato gli archi ('atlas:archi-ricalcolati'). Senza questo modulo
   backing e ritaglio restavano fermi dove la card era nata, e trascinandola
   la si vedeva staccarsi dalla propria trasparenza. I due contenitori
   '.edge-backings' e '.edge-ghosts' (render_svg.canvas) si svuotano e si
   riempiono da capo: e' il modo piu' semplice di non avere mai un ghost
   orfano di una card che non ha piu' archi sotto. */
(function () {
  "use strict";

  var vp = document.querySelector(".viewport");
  var svg = vp && vp.querySelector(".map svg");
  var backings = svg && svg.querySelector(".edge-backings");
  var ghosts = svg && svg.querySelector(".edge-ghosts");
  if (!backings || !ghosts) return;
  var NS = "http://www.w3.org/2000/svg";
  var CORNER = 10;   // edge_geometry.CORNER: quanto smooth_step_path esce dalla scatola fra i due agganci

  function el(nome, attrs) {
    var e = document.createElementNS(NS, nome);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  // Le card correnti: il rect.card non si muove mai, lo scarto sta in
  // data-dx/dy (drag.js, positions.js) e qui si somma una volta sola.
  function card() {
    var out = {};
    svg.querySelectorAll(".n").forEach(function (g) {
      var r = g.querySelector("rect.card");
      if (!r) return;
      var dx = +g.dataset.dx || 0, dy = +g.dataset.dy || 0;
      out[g.id.slice(5)] = {
        dx: dx, dy: dy, x: +r.getAttribute("x") + dx, y: +r.getAttribute("y") + dy,
        w: +r.getAttribute("width"), h: +r.getAttribute("height")
      };
    });
    return out;
  }

  // Gli archi in avanti con gli agganci correnti: la 'd' e' gia' quella
  // ricalcolata da drag.js, i quattro numeri a riposo piu' i delta danno la
  // scatola d'ingombro. I ritorni restano fuori come in Python: loop_lane
  // li tiene gia' fuori dalle card.
  function archi(nodi) {
    var out = [];
    svg.querySelectorAll("path.edge[data-from]:not(.loop)").forEach(function (p) {
      var a = nodi[p.dataset.from] || { dx: 0, dy: 0 }, b = nodi[p.dataset.to] || { dx: 0, dy: 0 };
      out.push({
        from: p.dataset.from, to: p.dataset.to, cls: p.getAttribute("class"), d: p.getAttribute("d"),
        sx: +p.dataset.sx + a.dx, sy: +p.dataset.sy + a.dy, ex: +p.dataset.ex + b.dx, ey: +p.dataset.ey + b.dy
      });
    });
    return out;
  }

  // Stessa regola di render_edge_ghosts._sotto_per_nodo: la scatola fra i
  // due agganci allargata di CORNER incrocia la card, e la card non e' ne'
  // la partenza ne' l'arrivo dell'arco.
  function rifai() {
    var nodi = card(), edges = archi(nodi);
    backings.textContent = ""; ghosts.textContent = "";
    Object.keys(nodi).forEach(function (id) {
      var n = nodi[id];
      var sotto = edges.filter(function (e) {
        return e.from !== id && e.to !== id
          && Math.min(e.sx, e.ex) - CORNER < n.x + n.w && Math.max(e.sx, e.ex) + CORNER > n.x
          && e.sy < n.y + n.h && e.ey > n.y;
      });
      if (!sotto.length) return;
      var box = { x: n.x, y: n.y, width: n.w, height: n.h, rx: 14 };
      backings.appendChild(el("rect", Object.assign({ "class": "edge-backing" }, box)));
      var clip = el("clipPath", { id: "clip-" + id });
      clip.appendChild(el("rect", box));
      var g = el("g", { "class": "edge-ghost", "clip-path": "url(#clip-" + id + ")" });
      sotto.forEach(function (e) {
        g.appendChild(el("path", { "class": e.cls, "data-ghost-from": e.from, "data-ghost-to": e.to, d: e.d }));
      });
      ghosts.appendChild(clip); ghosts.appendChild(g);
    });
  }

  // Un giro per frame, non uno per pointermove: il rifacimento e' O(card x
  // archi) e il puntatore manda piu' eventi di quanti il browser ne disegni.
  var atteso = false;
  vp.addEventListener("atlas:archi-ricalcolati", function () {
    if (atteso) return;
    atteso = true;
    requestAnimationFrame(function () { atteso = false; rifai(); });
  });
})();
