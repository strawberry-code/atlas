/* Shell della dashboard Atlas: toggle mappa/tabella, count-up avanzamento,
   filtri di legenda per stato e persona, copia negli appunti. */
(function () {
  "use strict";

  var quiete = matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- vista: mappa o tabella, resta scelta e sopravvive al ricarico ---------- */
  var vista = document.querySelector(".viewmode");
  vista.addEventListener("click", function () {
    var tabellaOra = document.documentElement.dataset.view === "table";
    var scelto = tabellaOra ? "map" : "table";
    document.documentElement.dataset.view = scelto;
    try { localStorage.setItem("atlas-view", scelto); } catch (e) { /* vale solo per questa pagina */ }
  });

  /* ---------- count-up di ogni numero che conta all'apertura ----------
     Un solo motore per tutti i '[data-count]' della pagina (l'anello di
     avanzamento e i tre readout della topbar), cosi' due punti della stessa
     pagina non hanno ciascuno il proprio timer che poi diverge (legge 3 di
     Grafite: "un dato che appare senza contare e' un'occasione persa"). Chi ha
     chiesto quiete vede subito il valore finale, che il markup porta gia'. */
  function contaSu(el, finale) {
    var cifre = parseInt(el.dataset.pad, 10) || 0;
    var suffisso = el.dataset.suffix || "";
    var formatta = function (n) {
      var s = String(n);
      while (s.length < cifre) s = "0" + s;
      return s + suffisso;
    };
    var t0 = null;
    var passo = function (ts) {
      if (t0 === null) t0 = ts;
      var q = Math.min((ts - t0) / 1100, 1);
      q = 1 - Math.pow(1 - q, 3);
      el.textContent = formatta(Math.round(finale * q));
      if (q < 1) requestAnimationFrame(passo);
    };
    requestAnimationFrame(passo);
  }
  if (!quiete) {
    document.querySelectorAll("[data-count]").forEach(function (el) {
      contaSu(el, parseInt(el.dataset.count, 10) || 0);
    });
  }

  /* ---------- filtro per stato: dal chip di legenda o dal titolo di un pannello ----------
     Le due prese fanno la stessa cosa e si accendono insieme, cosi' il chip dice
     sempre qual e' il filtro in corso anche a chi l'ha attivato dalla colonna. */
  function filtraStato(stato) {
    var attivo = document.body.dataset.filter === stato;
    document.querySelectorAll(".legend .chip[data-state].on").forEach(function (c) {
      c.classList.remove("on");
    });
    if (attivo) {
      delete document.body.dataset.filter;
      try { sessionStorage.removeItem("atlas-filter-state"); } catch (e) { /* vale solo per questo giro */ }
      return;
    }
    document.body.dataset.filter = stato;
    var chip = document.querySelector('.legend .chip[data-state="' + stato + '"]');
    if (chip) chip.classList.add("on");
    try { sessionStorage.setItem("atlas-filter-state", stato); } catch (e) { /* vale solo per questo giro */ }
  }
  document.addEventListener("click", function (e) {
    if (!e.target.closest) return;
    var chip = e.target.closest(".legend .chip[data-state]");
    if (chip) return filtraStato(chip.dataset.state);
    // il titolo del blocco, non il blocco intero: le sue voci aprono il ticket
    var titolo = e.target.closest(".blocco[data-hl] > h2");
    if (titolo) filtraStato(titolo.parentElement.dataset.hl);
  });

  /* ---------- click-to-copy: slug del grafo, id e titolo di un nodo ----------
     Un id si incolla in un comando ('atlas take F01') e lo slug in '-g <slug>':
     riscriverli a mano guardando lo schermo e' il gesto che questa pagina fa fare
     piu' spesso. La Clipboard API non basta da sola: aperta da file:// la pagina
     non e' un contesto sicuro e navigator.clipboard puo' non esserci affatto, o
     esserci e rifiutare, quindi resta la textarea con execCommand, deprecata ma
     l'unica che funziona li'. */
  function copiaNegliAppunti(testo) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(testo).catch(function () { return ripiego(testo); });
    }
    return ripiego(testo);
  }
  function ripiego(testo) {
    var ta = document.createElement("textarea");
    ta.value = testo;
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;top:0;left:0;opacity:0";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) { /* niente appunti: resta il testo a video */ }
    document.body.removeChild(ta);
    return Promise.resolve();
  }
  var timerCopia = 0;
  document.addEventListener("click", function (e) {
    var el = e.target.closest && e.target.closest("[data-copy]");
    if (!el) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    copiaNegliAppunti(el.dataset.copy).then(function () {
      document.querySelectorAll(".copiato").forEach(function (x) { x.classList.remove("copiato"); });
      el.classList.add("copiato");
      clearTimeout(timerCopia);
      timerCopia = setTimeout(function () { el.classList.remove("copiato"); }, 1200);
    });
  });

  /* ---------- filtro per persona: chip di legenda e righe del pannello ----------
     Due prese sullo stesso filtro, quindi il click si ascolta una volta sola su
     entrambe. Il selettore resta ancorato a .legend e .side: sulla mappa anche i
     nodi portano data-owners, e senza ancoraggio aprire un ticket accenderebbe
     pure il filtro della persona a cui quel nodo e' assegnato. */
  function filtraOwner(chi) {
    var attivo = document.body.dataset.owner === chi;
    document.querySelectorAll("[data-owner].on").forEach(function (x) { x.classList.remove("on"); });
    if (attivo) {
      delete document.body.dataset.owner;
      try { sessionStorage.removeItem("atlas-filter-owner"); } catch (e) { /* vale solo per questo giro */ }
      return;
    }
    document.body.dataset.owner = chi;
    document.querySelectorAll(".legend .chip[data-owner='" + chi + "'], .side li[data-owner='" + chi + "']")
      .forEach(function (x) { x.classList.add("on"); });
    try { sessionStorage.setItem("atlas-filter-owner", chi); } catch (e) { /* vale solo per questo giro */ }
  }
  document.addEventListener("click", function (e) {
    var presa = e.target.closest && e.target.closest(".legend .chip[data-owner], .side li[data-owner]");
    if (!presa) return;
    filtraOwner(presa.dataset.owner);
  });
  (function ripristinaFiltri() {
    var stato = null, owner = null;
    try { stato = sessionStorage.getItem("atlas-filter-state"); } catch (e) { /* niente da ripristinare */ }
    try { owner = sessionStorage.getItem("atlas-filter-owner"); } catch (e) { /* niente da ripristinare */ }
    if (stato) filtraStato(stato);
    if (owner) filtraOwner(owner);
  })();
})();
