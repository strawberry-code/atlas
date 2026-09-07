/* I Controls Grafite (C05): zoom avanti/indietro, rinquadra, lucchetto.
   Modulo a se': non tocca lo stato del canvas (privato all'IIFE di canvas.js),
   chiede solo con eventi custom su '.viewport' condiviso, e legge lo stato
   con cui aggiornare i bottoni dallo stesso '.viewport' (dataset.vk per il
   primo disegno, l'evento "atlas:vista" per ogni cambio dopo) - stesso
   contratto di scambio-solo-via-DOM di minimap.js. */
(function () {
  "use strict";

  var vp = document.querySelector(".viewport");
  var controlli = document.querySelector(".controls");
  if (!vp || !controlli) return;

  var MIN_K = .15, MAX_K = 2.5;   // duplicati da canvas.js: due numeri, non vale un modulo condiviso

  function comando(nome, dettaglio) {
    vp.dispatchEvent(new CustomEvent(nome, { detail: dettaglio }));
  }

  controlli.addEventListener("click", function (e) {
    var b = e.target.closest("[data-zoom]");
    if (!b) return;
    if (b.dataset.zoom === "fit") return comando("atlas:rinquadra-bottone");
    comando("atlas:zoomfattore", { fattore: b.dataset.zoom === "in" ? 1.2 : 1 / 1.2 });   // fattore contratto S3
  });

  // I bottoni +/- si disabilitano da soli ai limiti di zoom, il lucchetto li
  // blocca tutti tranne se stesso e il rinquadro (contratto S6).
  function aggiorna(k) {
    var bloccato = vp.dataset.locked === "true";
    var kk = typeof k === "number" ? k : parseFloat(vp.dataset.vk) || 1;
    var in_ = controlli.querySelector('[data-zoom="in"]');
    var out_ = controlli.querySelector('[data-zoom="out"]');
    if (in_) in_.disabled = bloccato || kk >= MAX_K;
    if (out_) out_.disabled = bloccato || kk <= MIN_K;
  }

  var lucchetto = controlli.querySelector("[data-lock]");
  if (lucchetto) {
    lucchetto.addEventListener("click", function () {
      var bloccato = vp.dataset.locked !== "true";
      vp.dataset.locked = bloccato ? "true" : "false";
      lucchetto.setAttribute("aria-pressed", String(bloccato));
      lucchetto.setAttribute("aria-label", bloccato
        ? lucchetto.dataset.labelUnlock : lucchetto.dataset.labelLock);
      var fitBtn = controlli.querySelector('[data-zoom="fit"]');
      if (fitBtn) fitBtn.disabled = bloccato;
      aggiorna();
    });
  }

  aggiorna();   // primo disegno gia' avvenuto: si legge subito, non si aspetta il primo evento
  vp.addEventListener("atlas:vista", function (e) { aggiorna(e.detail.k); });
})();
