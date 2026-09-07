/* Dove vivono le posizioni trascinate (C10): in localStorage, una chiave per
   grafo (data-slug su '<body>', render.py), MAI in graph.json - quello e' il
   grafo condiviso fra macchine e si fonde con un merge driver, le coordinate
   della finestra di qualcuno non gli appartengono. Restano quindi locali alla
   macchina per sempre: non c'e' nessun altro canale che le porti altrove, e
   la fog che se lo chiedeva (voce 1) si chiude con questa scelta.

   Un nodo nuovo che nessuno ha mai spostato non ha voce qui: prende la
   posizione calcolata (il layout a rank di sempre) senza bisogno di codice
   apposta. Un nodo sparito lascia una voce che le letture successive
   scartano (vedi pulisci()): la mappa non cresce all'infinito.

   Il ripristino del layout automatico e' il bottone Controls "data-reset-
   layout" (render_canvas.py): azzera la mappa salvata e chiede a drag.js
   (unico modulo che sa disegnare un nodo o un arco) di ridisegnare tutto da
   capo, poi rinquadra come fitview.js gia' sa fare dopo un rilayout. */
(function () {
  "use strict";

  var vp = document.querySelector(".viewport");
  if (!vp) return;
  var CHIAVE = "atlas-layout:" + (document.body.dataset.slug || "");

  function leggi() {
    try { return JSON.parse(localStorage.getItem(CHIAVE)) || {}; }
    catch (e) { return {}; }   // localStorage assente o voce corrotta: si riparte da un layout vuoto
  }
  function scrivi(mappa) {
    try { localStorage.setItem(CHIAVE, JSON.stringify(mappa)); }
    catch (e) { /* niente da salvare: la card resta dov'e' solo per questo giro */ }
  }

  function scriviDelta(g, dx, dy) {
    g.dataset.dx = dx; g.dataset.dy = dy;
    g.style.setProperty("--dragx", dx + "px");
    g.style.setProperty("--dragy", dy + "px");
  }

  // Scarta le card sparite dal grafo attuale: e' l'unico posto che pulisce,
  // e gira una volta sola al caricamento, non a ogni spostamento.
  function pulisci(mappa) {
    var vive = {}, tocco = false;
    for (var id in mappa) {
      if (document.getElementById("node-" + id)) vive[id] = mappa[id];
      else tocco = true;
    }
    if (tocco) scrivi(vive);
    return vive;
  }

  var mappa = pulisci(leggi());
  for (var id in mappa) {
    var g = document.getElementById("node-" + id);
    if (g) scriviDelta(g, mappa[id][0], mappa[id][1]);
  }
  // Le card sono gia' al posto salvato: gli archi che le toccano vanno
  // ridisegnati per raggiungerle, un solo giro per l'intera pagina.
  vp.dispatchEvent(new CustomEvent("atlas:ricalcola-archi"));

  vp.addEventListener("atlas:nodo-spostato", function (e) {
    mappa[e.detail.id] = [e.detail.dx, e.detail.dy];
    scrivi(mappa);
  });

  var bottone = document.querySelector("[data-reset-layout]");
  if (bottone) {
    bottone.addEventListener("click", function () {
      mappa = {};
      scrivi(mappa);
      document.querySelectorAll(".map .n").forEach(function (g) { scriviDelta(g, 0, 0); });
      vp.dispatchEvent(new CustomEvent("atlas:ricalcola-archi"));
      vp.dispatchEvent(new CustomEvent("atlas:rilayout"));
    });
  }
})();
