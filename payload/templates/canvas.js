/* La superficie del grafo: un solo transform translate(x,y) scale(k) su
   '.pannello', dentro '.viewport' che ritaglia. Pan col puntatore, zoom a
   rotella ancorato al punto sotto il cursore, persistenza della vista
   attraverso i reload SSE, e l'applicatore generico "vaici" che chiunque
   (fitview.js, e i comandi da Controls/minimap sotto) puo' chiedere.
   Questo file e' il motore: decide COME muovere la vista, mai DOVE - il
   rinquadro (le tre varianti del contratto S3, C05) e' un modulo a se'
   (fitview.js), come i Controls (controls.js) e la minimap (minimap.js).
   Parlano tutti con questo solo tramite eventi custom su '.viewport' e il suo
   attributo 'data-locked' - mai per riferimento diretto fra IIFE (contratto
   del progetto). Il trascinamento delle card resta di C10. */
(function () {
  "use strict";

  var GRID = 22;      // passo della griglia in spazio-grafo, contratto S4
  var R0 = .55;        // raggio del puntino a zoom 1: scala con k, mai fissa,
                        // altrimenti a zoom basso diventa una nebbia grigia
  var MIN_K = .15, MAX_K = 2.5;   // limiti di zoom, contratto S3

  // Letto una volta sola non basta (C12): un'easing gia' in corsa (passoZoom
  // sotto) va portata di scatto al bersaglio quando la preferenza cambia a vivo.
  var mqQuiete = matchMedia("(prefers-reduced-motion: reduce)");
  var quiete = mqQuiete.matches;
  mqQuiete.addEventListener("change", function (e) {
    quiete = e.matches;
    if (quiete && rafZoom) { cancelAnimationFrame(rafZoom); rafZoom = 0; zoomTs = 0; impostaZoom(zoomVoluto, ancoraX, ancoraY); salvaVista(); }
  });
  var vp = document.querySelector(".viewport");
  var panel = vp.querySelector(".pannello");

  // Stato del viewport: coordinate del grafo -> coordinate schermo e' sempre
  // screen = viewport.rect + (grafo * k) + (x,y). Le due conversioni sotto
  // sono pure e si provano a mente senza aprire un browser.
  var stato = { x: 0, y: 0, k: 1 };

  function limita(k) { return Math.min(MAX_K, Math.max(MIN_K, k)); }
  function bloccato() { return vp.dataset.locked === "true"; }

  // Le due conversioni, pure: 'px,py' e 'gx,gy' sono sempre relative
  // all'origine del viewport (chi chiama toglie gia' rect.left/rect.top),
  // mai al documento. Si provano a mente, senza aprire un browser.
  function schermoAGrafo(px, py) {
    return { x: (px - stato.x) / stato.k, y: (py - stato.y) / stato.k };
  }
  function grafoASchermo(gx, gy) {
    return { x: stato.x + gx * stato.k, y: stato.y + gy * stato.k };
  }

  function disegna() {
    panel.style.transform = "translate(" + stato.x + "px," + stato.y + "px) scale(" + stato.k + ")";
    // il puntino resta ancorato al grafo solo se raggio e passo scalano
    // insieme: e' il rapporto fra i due a dover restare costante, non uno dei due
    var r = Math.max(.18, R0 * stato.k);
    vp.style.backgroundImage = "radial-gradient(circle,var(--gridline) " + r.toFixed(2)
      + "px,transparent " + (r + .55).toFixed(2) + "px)";
    vp.style.backgroundSize = (GRID * stato.k) + "px " + (GRID * stato.k) + "px";
    vp.style.backgroundPosition = stato.x + "px " + stato.y + "px";
    // Stato pubblicato sul DOM: Controls, minimap e fitview (moduli a se')
    // lo leggono da 'dataset' al proprio avvio e dall'evento per ogni cambio
    // successivo, senza polling e senza un riferimento diretto a questa IIFE.
    vp.dataset.vx = stato.x; vp.dataset.vy = stato.y; vp.dataset.vk = stato.k;
    vp.dispatchEvent(new CustomEvent("atlas:vista", { detail: { x: stato.x, y: stato.y, k: stato.k } }));
  }

  /* La dashboard si ricarica da sola a ogni sync (l'EventSource iniettato da
     serve.py): senza salvare qui, ogni reload azzererebbe pan e zoom. */
  function salvaVista() {
    try { sessionStorage.setItem("atlas-map", JSON.stringify(stato)); }
    catch (e) { /* sessionStorage assente: la vista vale solo per questo giro */ }
  }

  function impostaZoom(k, cx, cy) {
    // cx,cy: punto nel riferimento del viewport che deve restare fermo.
    // Si legge il punto-grafo sotto il cursore alla scala vecchia, si cambia
    // la scala, poi si trasla quanto serve perche' quel punto torni sotto cx,cy.
    k = limita(k);
    var g = schermoAGrafo(cx, cy);
    stato.k = k;
    var s = grafoASchermo(g.x, g.y);
    stato.x += cx - s.x;
    stato.y += cy - s.y;
    disegna();
  }

  /* Lo zoom a rotella non salta al valore nuovo: si avvicina, e la strada che
     copre dipende dal tempo passato, non dal numero di frame. Legarla al
     frame renderebbe la corsa doppia su uno schermo a 120 Hz rispetto a uno a
     60. Cosi' una raffica di eventi della rotella, che un trackpad produce a
     decine per un solo movimento del dito, diventa una corsa continua invece
     di una scalinata. I bottoni +/- e il rinquadro restano istantanei, come
     nel contratto (S3: nessuna delle due chiamate porta una durata). */
  var zoomVoluto = 1, ancoraX = 0, ancoraY = 0, rafZoom = 0, zoomTs = 0;
  function passoZoom(ts) {
    var dt = zoomTs ? Math.min(ts - zoomTs, 100) : 16;   // una scheda tornata in primo piano
    zoomTs = ts;
    var nuovo = stato.k + (zoomVoluto - stato.k) * (1 - Math.exp(-dt / 70));
    if (Math.abs(zoomVoluto - nuovo) < .002) nuovo = zoomVoluto;   // o non arriva mai
    impostaZoom(nuovo, ancoraX, ancoraY);
    if (nuovo === zoomVoluto) { rafZoom = 0; zoomTs = 0; salvaVista(); return; }
    rafZoom = requestAnimationFrame(passoZoom);
  }
  function versoRotella(k, cx, cy) {
    zoomVoluto = limita(k);
    ancoraX = cx;
    ancoraY = cy;
    if (quiete) { impostaZoom(zoomVoluto, cx, cy); salvaVista(); return; }
    if (!rafZoom) rafZoom = requestAnimationFrame(passoZoom);
  }
  function fermaRotella() {
    if (rafZoom) { cancelAnimationFrame(rafZoom); rafZoom = 0; zoomTs = 0; }
    zoomVoluto = stato.k;
  }

  // Un trascinamento che parte da un nodo o da un arco non deve panare: quei
  // punti hanno gia' un loro clic (apre la scheda del ticket, vedi sheet.js).
  var NON_PANABILE = "a[data-node],path.edge,circle.port";

  // Comandi da altri moduli su questo stesso '.viewport' (Controls, minimap,
  // fitview): zoomare verso un punto, zoomare di un fattore fisso ancorato al
  // centro, o andare direttamente a una vista (x,y,k), con o senza
  // transizione CSS - l'unico posto che tocca 'panel.style.transition', cosi'
  // non resta accesa durante un pan/zoom successivo. Tutti rispettano il
  // lucchetto come le interazioni dirette sotto.
  vp.addEventListener("atlas:zoomverso", function (e) {
    if (bloccato()) return;
    var s = grafoASchermo(e.detail.gx, e.detail.gy);
    versoRotella(stato.k * Math.exp(-e.detail.delta * .0022), s.x, s.y);
  });
  vp.addEventListener("atlas:zoomfattore", function (e) {
    if (bloccato()) return;
    fermaRotella();
    impostaZoom(stato.k * e.detail.fattore, vp.clientWidth / 2, vp.clientHeight / 2);
    salvaVista();
  });
  vp.addEventListener("atlas:centra", function (e) {
    if (bloccato()) return;
    fermaRotella();
    stato.x = vp.clientWidth / 2 - e.detail.x * stato.k;
    stato.y = vp.clientHeight / 2 - e.detail.y * stato.k;
    disegna();
    if (e.detail.fine) salvaVista();
  });
  vp.addEventListener("atlas:vai", function (e) {
    if (bloccato()) return;
    fermaRotella();
    var d = e.detail;
    if (d.durata && !quiete) {
      panel.style.transition = "transform " + d.durata + "ms var(--e-soft)";
      panel.addEventListener("transitionend", function fine() {
        panel.removeEventListener("transitionend", fine);
        panel.style.transition = "";
      });
    }
    stato.x = d.x; stato.y = d.y; stato.k = limita(d.k);
    disegna();
    salvaVista();
  });

  vp.addEventListener("wheel", function (e) {
    if (bloccato()) return;
    // niente tasto modificatore: qui non c'e' piu' uno scroll nativo da
    // lasciar passare, la superficie e' tutta il canvas (contratto S2)
    e.preventDefault();
    /* deltaY arriva in pixel dal trackpad e in righe dal mouse a scatti: senza
       normalizzarlo, e senza legare la scala a quanto vale, lo stesso gesto
       ingrandisce di una frazione su un dispositivo e di cinque volte sull'altro. */
    var d = e.deltaMode === 1 ? e.deltaY * 16
      : e.deltaMode === 2 ? e.deltaY * vp.clientHeight : e.deltaY;
    d = Math.max(-120, Math.min(120, d));       // un colpo secco non teletrasporta
    var r = vp.getBoundingClientRect();
    versoRotella(stato.k * Math.exp(-d * .0022), e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });

  vp.addEventListener("pointerdown", function (e) {
    if (bloccato()) return;
    if (e.pointerType === "mouse" && e.button !== 0) return;
    if (e.target.closest(NON_PANABILE)) return;
    fermaRotella();
    var px = e.clientX, py = e.clientY, ox = stato.x, oy = stato.y, mosso = false;
    try { vp.setPointerCapture(e.pointerId); } catch (err) { /* browser vecchio: pointermove basta lo stesso */ }
    function muovi(ev) {
      var dx = ev.clientX - px, dy = ev.clientY - py;
      if (!mosso && Math.abs(dx) + Math.abs(dy) > 4) { mosso = true; vp.classList.add("trascina"); document.body.classList.add("trascina"); if (window.getSelection) window.getSelection().removeAllRanges(); }   // C13: azzera anche la selezione gia' in corso altrove
      if (mosso) { stato.x = ox + dx; stato.y = oy + dy; disegna(); }
    }
    function fine() {
      try { vp.releasePointerCapture(e.pointerId); } catch (err) { /* gia' rilasciato */ }
      vp.removeEventListener("pointermove", muovi);
      vp.removeEventListener("pointerup", fine);
      vp.removeEventListener("pointercancel", fine);
      if (mosso) { vp.classList.remove("trascina"); document.body.classList.remove("trascina"); salvaVista(); }   // C13: tolta anche su pointercancel
    }
    vp.addEventListener("pointermove", muovi);
    vp.addEventListener("pointerup", fine);
    vp.addEventListener("pointercancel", fine);
  });
})();
