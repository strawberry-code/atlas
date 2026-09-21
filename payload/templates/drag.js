/* Il trascinamento delle card (C10): si afferra un nodo, si sposta in
   spazio-grafo, gli archi lo seguono. Sotto la soglia in pixel resta un clic
   (sheet.js apre la scheda: stesso trucco di canvas.js, la classe "trascina"
   su '.viewport' che il suo listener click gia' controlla). Sopra la soglia,
   sposta la card con una proprieta' CSS (--dragx/--dragy, canvas.css) invece
   del transform-attributo SVG, perche' ".n:hover" porta gia' un transform CSS
   suo e i due non si sommerebbero. La persistenza (dove si salva la card) e
   il ripristino del layout automatico restano di positions.js: qui solo il
   gesto e la geometria degli archi, che nessun altro modulo sa disegnare. */
(function () {
  "use strict";

  var vp = document.querySelector(".viewport");
  if (!vp) return;

  // Porta di edge_geometry.py (A01): stesse costanti, stessa forma. Duplicata
  // qui e non importata perche' i moduli di questa pagina si scambiano solo
  // via DOM (contratto di progetto), mai per riferimento diretto fra IIFE.
  var OFFSET = 20, CORNER = 10, STEP = .5, LANE = 135, DROP = 26;

  function dist(ax, ay, bx, by) { return Math.hypot(bx - ax, by - ay); }

  function bend(ax, ay, bx, by, cx, cy, size) {
    var r = Math.min(dist(ax, ay, bx, by) / 2, dist(bx, by, cx, cy) / 2, size);
    if ((ax === bx && bx === cx) || (ay === by && by === cy)) return "L" + bx + " " + by;
    if (ay === by) {
      var xd = ax < cx ? -1 : 1, yd = ay < cy ? 1 : -1;
      return "L " + (bx + r * xd) + "," + by + "Q " + bx + "," + by + " " + bx + "," + (by + r * yd);
    }
    var xd2 = ax < cx ? 1 : -1, yd2 = ay < cy ? -1 : 1;
    return "L " + bx + "," + (by + r * yd2) + "Q " + bx + "," + by + " " + (bx + r * xd2) + "," + by;
  }

  function smoothStepPath(sx, sy, tx, ty) {
    var sgx = sx, sgy = sy + OFFSET, tgx = tx, tgy = ty - OFFSET;
    var giu = sgy < tgy;
    var cx = (sgx + tgx) / 2, cy = sgy + (tgy - sgy) * STEP;
    var mid = giu ? [[sgx, cy], [tgx, cy]] : [[cx, sgy], [cx, tgy]];
    var pts = [[sx, sy]];
    if (!(sgx === mid[0][0] && sgy === mid[0][1])) pts.push([sgx, sgy]);
    pts.push(mid[0], mid[1]);
    if (!(tgx === mid[1][0] && tgy === mid[1][1])) pts.push([tgx, tgy]);
    pts.push([tx, ty]);
    var d = "M" + pts[0][0] + " " + pts[0][1];
    for (var i = 1; i < pts.length - 1; i++) {
      d += bend(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], CORNER);
    }
    var last = pts[pts.length - 1];
    return d + "L" + last[0] + " " + last[1];
  }

  function roundedPath(points) {
    var pts = [];
    for (var i = 0; i < points.length; i++) {
      if (i === 0 || Math.abs(points[i][0] - points[i - 1][0]) > .5 || Math.abs(points[i][1] - points[i - 1][1]) > .5) {
        pts.push(points[i]);
      }
    }
    if (pts.length < 2) return "";
    var d = "M " + pts[0][0] + "," + pts[0][1];
    for (var i = 1; i < pts.length - 1; i++) {
      var a = pts[i - 1], c = pts[i], b = pts[i + 1];
      var la = dist(a[0], a[1], c[0], c[1]), lb = dist(c[0], c[1], b[0], b[1]);
      var r = Math.min(CORNER, la / 2, lb / 2);
      d += " L " + (c[0] + (a[0] - c[0]) / la * r) + "," + (c[1] + (a[1] - c[1]) / la * r);
      d += " Q " + c[0] + "," + c[1] + " " + (c[0] + (b[0] - c[0]) / lb * r) + "," + (c[1] + (b[1] - c[1]) / lb * r);
    }
    var last = pts[pts.length - 1];
    return d + " L " + last[0] + "," + last[1];
  }

  function loopLane(sx, tx) { return sx >= tx ? Math.max(sx, tx) + LANE : Math.min(sx, tx) - LANE; }

  function loopPath(sx, sy, tx, ty) {
    var lane = loopLane(sx, tx), rise = 26 + Math.min(70, Math.abs(lane - tx) * .12);
    return roundedPath([[sx, sy], [sx, sy + DROP], [lane, sy + DROP], [lane, ty - rise], [tx, ty - rise], [tx, ty]]);
  }

  // Lo scarto corrente di un nodo, in spazio-grafo: positions.js lo scrive
  // (layout salvato o azzerato), il gesto sotto lo aggiorna in diretta. 0,0
  // finche' nessuno lo tocca (data-dx/dy assenti).
  function delta(id) {
    var g = document.getElementById("node-" + id);
    return g ? { x: +g.dataset.dx || 0, y: +g.dataset.dy || 0 } : { x: 0, y: 0 };
  }
  function scriviDelta(g, dx, dy) {
    g.dataset.dx = dx; g.dataset.dy = dy;
    g.style.setProperty("--dragx", dx + "px");
    g.style.setProperty("--dragy", dy + "px");
  }
  // data-sx/sy/ex/ey (render_edges.py) sono i quattro numeri "a riposo": non
  // si toccano mai, ogni ricalcolo riparte da li' sommando i due delta
  // correnti, cosi' un trascinamento lungo non accumula deriva. Se l'arco e'
  // un ritorno lo dice la classe "loop" scritta dal server (graph_walk.
  // back_edges: un arco che chiude un ciclo): trascinare una card cambia la
  // forma, mai la natura dell'arco, e un arco in avanti che risale resta
  // sullo smooth step, che il ramo speculare lo gestisce.
  function ricalcolaArco(path) {
    var dep = path.dataset.from, nid = path.dataset.to;
    var dDep = delta(dep), dNid = delta(nid);
    var sx = +path.dataset.sx + dDep.x, sy = +path.dataset.sy + dDep.y;
    var ex = +path.dataset.ex + dNid.x, ey = +path.dataset.ey + dNid.y;
    var loop = path.classList.contains("loop");
    path.setAttribute("d", loop ? loopPath(sx, sy, ex, ey) : smoothStepPath(sx, sy, ex, ey));
    var porta = document.querySelector('circle.port[data-from="' + dep + '"][data-to="' + nid + '"]');
    if (porta) { porta.setAttribute("cx", sx); porta.setAttribute("cy", sy); }
  }
  // Dopo ogni giro avvisa ghosts.js, che rifa' la trasparenza sotto le card
  // sulle 'd' appena scritte: non sa disegnare un arco, legge le nostre.
  function ricalcolaArchiDi(id) {
    document.querySelectorAll('path.edge[data-from="' + id + '"],path.edge[data-to="' + id + '"]').forEach(ricalcolaArco);
    vp.dispatchEvent(new CustomEvent("atlas:archi-ricalcolati"));
  }

  // Un trascinamento che parte da fuori una card resta il pan della
  // superficie (canvas.js, che su "a[data-node]" non fa nulla): qui e' il
  // contrario, si esce solo se il bersaglio non e' una card.
  var SOGLIA = 4;   // px schermo: sotto resta un clic, come il pan (canvas.js)

  // La card e' dentro un <a href>: senza questo, il browser la trascina come
  // trascinerebbe un link qualunque (drag nativo, fantasma incluso) appena il
  // puntatore si muove, e i pointermove che seguono arrivano tagliati o del
  // tutto persi. Va spento prima che parta, non dopo.
  vp.addEventListener("dragstart", function (e) {
    if (e.target.closest && e.target.closest("a[data-node]")) e.preventDefault();
  });

  vp.addEventListener("pointerdown", function (e) {
    if (vp.dataset.locked === "true") return;
    if (e.pointerType === "mouse" && e.button !== 0) return;
    var a = e.target.closest ? e.target.closest("a[data-node]") : null;
    if (!a) return;
    var id = a.dataset.node, g = document.getElementById("node-" + id);
    if (!g) return;
    var px = e.clientX, py = e.clientY, mosso = false, d0 = delta(id);
    // La cattura del puntatore si prende SOLO quando il gesto e' gia' un
    // trascinamento confermato, mai al pointerdown: presa subito, il clic
    // secco che segue arriva con e.target ri-targettato su '.viewport' invece
    // che sulla card, e sheet.js (che cerca "[data-node]" nel target) non
    // apre piu' nulla. E' il modo in cui questo gesto per poco non rompeva
    // la selezione di ogni singolo clic su un nodo.
    function muovi(ev) {
      if (!mosso && Math.hypot(ev.clientX - px, ev.clientY - py) <= SOGLIA) return;
      if (!mosso) {
        mosso = true;
        try { vp.setPointerCapture(e.pointerId); } catch (err) { /* browser vecchio: pointermove basta lo stesso */ }
        vp.classList.add("trascina"); g.classList.add("trascina"); document.body.classList.add("trascina");
        // Stesso schema di canvas.js/minimap.js (C13): azzera la selezione
        // gia' in corso, non solo la previene in avanti.
        if (window.getSelection) window.getSelection().removeAllRanges();
      }
      var k = parseFloat(vp.dataset.vk) || 1;
      scriviDelta(g, d0.x + (ev.clientX - px) / k, d0.y + (ev.clientY - py) / k);
      ricalcolaArchiDi(id);
    }
    function fine() {
      try { vp.releasePointerCapture(e.pointerId); } catch (err) { /* gia' rilasciato */ }
      vp.removeEventListener("pointermove", muovi);
      vp.removeEventListener("pointerup", fine);
      vp.removeEventListener("pointercancel", fine);
      g.classList.remove("trascina");
      if (!mosso) return;
      var df = delta(id);
      vp.dispatchEvent(new CustomEvent("atlas:nodo-spostato", { detail: { id: id, dx: df.x, dy: df.y } }));
      // La classe resta un giro in piu' (setTimeout 0), stessa ragione di
      // canvas.js: il 'click' che chiude il trascinamento arriva nello stesso
      // turno sincrono del 'pointerup', prima di questo rinvio sheet.js la
      // trovava gia' tolta e perdeva la selezione sul nodo scelto in precedenza.
      setTimeout(function () { vp.classList.remove("trascina"); document.body.classList.remove("trascina"); }, 0);
    }
    vp.addEventListener("pointermove", muovi);
    vp.addEventListener("pointerup", fine);
    vp.addEventListener("pointercancel", fine);
  });

  // positions.js chiede un ricalcolo completo dopo aver applicato il layout
  // salvato (al caricamento) o averlo azzerato (bottone "layout automatico"):
  // qui e' l'unico modulo che sa disegnare un arco, quindi risponde per intero.
  // '[data-from]' esclude le copie sfumate sotto le card (render_edge_ghosts.py,
  // '.edge-ghost path.edge'): non portano data-sx/sy/ex/ey, quindi
  // ricalcolaArco() le riscriverebbe con NaN e le farebbe collassare a zero -
  // invisibili anche a opacita' piena, il bug dietro S13/10.
  vp.addEventListener("atlas:ricalcola-archi", function () {
    document.querySelectorAll("path.edge[data-from]").forEach(ricalcolaArco);
    vp.dispatchEvent(new CustomEvent("atlas:archi-ricalcolati"));
  });
})();
