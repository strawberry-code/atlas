/* Tabella: ordinamento per colonna, con confronto naturale. */
(function () {
  "use strict";

  var NUMERO = /^-?\d+(?:\.\d+)?$/;
  function confronta(a, b) {
    a = a == null ? "" : String(a);
    b = b == null ? "" : String(b);
    if (NUMERO.test(a) && NUMERO.test(b)) return parseFloat(a) - parseFloat(b);
    var ca = a.match(/\d+|\D+/g) || [];
    var cb = b.match(/\d+|\D+/g) || [];
    for (var i = 0; i < Math.max(ca.length, cb.length); i++) {
      if (ca[i] === undefined) return -1;
      if (cb[i] === undefined) return 1;
      if (/^\d+$/.test(ca[i]) && /^\d+$/.test(cb[i])) {
        var d = parseInt(ca[i], 10) - parseInt(cb[i], 10);
        if (d) return d;
      } else {
        var c = ca[i].localeCompare(cb[i], undefined, { sensitivity: "base" });
        if (c) return c;
      }
    }
    return 0;
  }
  var gridtbl = document.querySelector(".gridtbl");
  if (gridtbl) {
    var intestazioniTbl = Array.prototype.slice.call(gridtbl.querySelectorAll("thead th[data-col]"));
    var corpoTbl = gridtbl.querySelector("tbody");
    var ordinaTbl = function (indice, verso) {
      var righeTbl = Array.prototype.slice.call(corpoTbl.querySelectorAll("tr"));
      righeTbl.sort(function (r1, r2) {
        var esito = confronta(r1.children[indice].dataset.v, r2.children[indice].dataset.v);
        return verso === "desc" ? -esito : esito;
      });
      righeTbl.forEach(function (r) { corpoTbl.appendChild(r); });
      intestazioniTbl.forEach(function (h) { h.removeAttribute("aria-sort"); });
      intestazioniTbl[indice].setAttribute("aria-sort", verso === "desc" ? "descending" : "ascending");
      gridtbl.dataset.sortCol = indice;
      gridtbl.dataset.sortDir = verso;
    };
    intestazioniTbl.forEach(function (h, indice) {
      h.addEventListener("click", function () {
        var stessa = gridtbl.dataset.sortCol === String(indice);
        ordinaTbl(indice, stessa && gridtbl.dataset.sortDir === "asc" ? "desc" : "asc");
      });
    });
    if (intestazioniTbl.length) ordinaTbl(0, "asc");   // id crescente: ordine prevedibile alla prima apertura
  }
})();
