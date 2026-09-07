/* Pannello Notifiche: card delle Interazioni, pairing Telegram, muto, avvisi locali. */
(function () {
  "use strict";

  var notificheData = document.querySelector(".notifiche").dataset;
  var servito = /^https?:$/.test(location.protocol);

  /* ---------- pannello Notifiche: richiudibile, stesso principio del tema ----------
     Lo stato aperto/chiuso lo ripristina render.py da localStorage prima del
     primo paint (data-notifiche su <html>, per non far lampeggiare la
     griglia): l'aria-expanded del bottone pero' resta quello statico del
     markup finche' nessuno lo riallinea, quindi un reload a pannello
     ricordato chiuso mostrerebbe "true" a chi legge lo screen reader pur
     essendo collassato a video. Si allinea qui, una volta, allo stato gia'
     scritto su <html> quando questo modulo parte (S12). */
  var notifToggle = document.querySelector(".notifiche-toggle");
  notifToggle.setAttribute("aria-expanded", String(document.documentElement.dataset.notifiche !== "chiuso"));
  notifToggle.addEventListener("click", function () {
    var chiusoOra = document.documentElement.dataset.notifiche === "chiuso";
    var scelto = chiusoOra ? "aperto" : "chiuso";
    document.documentElement.dataset.notifiche = scelto;
    notifToggle.setAttribute("aria-expanded", String(chiusoOra));
    try { localStorage.setItem("atlas-notifiche", scelto); } catch (e) { /* vale solo per questa pagina */ }
  });

  /* ---------- pannello Notifiche: azioni sul lifecycle atomico ----------
     Un bottone azione e un <summary> di log stanno dentro una card che porta
     anche data-node: senza fermare qui la propagazione, il click aprirebbe
     anche la scheda del ticket (il gestore [data-node] piu' sotto ascolta
     sullo stesso document). 'atlas render' apre un file:// senza server: li'
     i bottoni restano disabilitati dall'avvio, non c'e' nessuno a cui
     rispondere. Un solo invio alla volta per card: il bottone si disabilita
     subito, prima che la risposta torni, cosi' un doppio clic non spedisce
     due richieste per la stessa Interaction. */
  document.querySelectorAll(".notif-azioni button").forEach(function (b) {
    if (servito) return;
    b.disabled = true;
    b.title = notificheData.azioneOffline || "";
  });
  function erroreAzione(card) {
    card.classList.add("notif-errore");
    var testo = card.querySelector(".notif-errore-testo");
    if (!testo) {
      testo = document.createElement("p");
      testo.className = "notif-errore-testo";
      card.querySelector(".notif-azioni").appendChild(testo);
    }
    testo.textContent = notificheData.azioneErrore || "";
  }
  document.addEventListener("click", function (e) {
    var log = e.target.closest && e.target.closest(".notif-card summary");
    if (log) { e.stopImmediatePropagation(); return; }   // solo il <details> nativo, niente scheda
    var b = e.target.closest && e.target.closest(".notif-azioni button");
    if (!b) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    if (b.disabled) return;
    var card = b.closest(".notif-card");
    var bottoni = Array.prototype.slice.call(card.querySelectorAll(".notif-azioni button"));
    bottoni.forEach(function (x) { x.disabled = true; });
    card.classList.remove("notif-errore");
    fetch("/interactions/" + encodeURIComponent(b.dataset.interaction) + "/"
      + encodeURIComponent(b.dataset.action), { method: "POST" })
      .then(function (r) {
        if (r.ok) return;   // la ricarica SSE aggiorna la card da sola quando il grafo cambia
        bottoni.forEach(function (x) { x.disabled = false; });
        erroreAzione(card);
      })
      .catch(function () {
        bottoni.forEach(function (x) { x.disabled = false; });
        erroreAzione(card);
      });
  });

  /* ---------- pannello Notifiche: pairing Telegram one-tap (D05/A04) ----------
     Un solo bottone: POST /pairing/telegram genera un codice monouso e il link
     t.me da aprire, senza che l'utente inserisca token bot, chat ID, hostname o
     file di configurazione. Dopo l'apertura del link si interroga lo stato a
     intervalli finche' non arriva un esito terminale: e' un poll verso 'atlas
     serve' locale, mai verso il relay, e si ferma da solo (connesso, rifiutato
     dal gestore, nessun gestore ancora configurato, scaduto/sconosciuto), mai un
     giro infinito. 'in_attesa' e 'in_attesa_gestore' (A03: prima che l'utente
     apra Telegram, poi mentre il gestore decide) restano indistinti in UI, un
     solo messaggio d'attesa per entrambi: dal lato di chi preme il bottone e'
     comunque 'aspetto il via libera'. */
  (function pairingTelegram() {
    var bottone = document.querySelector(".pairing-telegram");
    if (!bottone) return;
    var stato = document.querySelector(".pairing-stato");
    if (!servito) {
      bottone.disabled = true;
      bottone.title = notificheData.azioneOffline || "";
      return;
    }
    var PASSO_POLL_MS = 2500;
    function messaggio(testo, classe) {
      stato.textContent = testo || "";
      stato.className = "pairing-stato" + (classe ? " " + classe : "");
    }
    function interroga(codice, scadenzaMs) {
      if (Date.now() > scadenzaMs) {
        messaggio(notificheData.pairingScaduto, "pairing-errore");
        bottone.disabled = false;
        return;
      }
      fetch("/pairing/telegram/status?code=" + encodeURIComponent(codice))
        .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
        .then(function (esito) {
          if (esito.status === "associato") {
            messaggio(notificheData.pairingConnesso, "pairing-ok");
            bottone.disabled = false;
            return;
          }
          if (esito.status === "scaduto" || esito.status === "sconosciuto") {
            messaggio(notificheData.pairingScaduto, "pairing-errore");
            bottone.disabled = false;
            return;
          }
          if (esito.status === "rifiutato") {
            messaggio(notificheData.pairingRifiutato, "pairing-errore");
            bottone.disabled = false;
            return;
          }
          if (esito.status === "senza_gestore") {
            messaggio(notificheData.pairingSenzaGestore, "pairing-errore");
            bottone.disabled = false;
            return;
          }
          setTimeout(function () { interroga(codice, scadenzaMs); }, PASSO_POLL_MS);
        })
        .catch(function () {
          setTimeout(function () { interroga(codice, scadenzaMs); }, PASSO_POLL_MS);
        });
    }
    bottone.addEventListener("click", function () {
      bottone.disabled = true;
      messaggio("", "");
      fetch("/pairing/telegram", { method: "POST" })
        .then(function (r) {
          return r.json().catch(function () { return {}; }).then(function (corpo) {
            return { ok: r.ok, corpo: corpo };
          });
        })
        .then(function (esito) {
          if (esito.ok && esito.corpo.ok && esito.corpo.url) {
            window.open(esito.corpo.url, "_blank", "noopener");
            messaggio(notificheData.pairingAttesa + " · "
                      + notificheData.pairingRipiego + "/start " + esito.corpo.code,
                      "pairing-attesa");
            interroga(esito.corpo.code, esito.corpo.expiresAt * 1000);
            return;
          }
          var testo = notificheData.azioneErrore;
          if (esito.corpo.motivo === "relay-non-configurato") testo = notificheData.pairingSenzaRelay;
          else if (esito.corpo.motivo === "relay-non-risponde") testo = notificheData.pairingRelayMuto;
          messaggio(testo, "pairing-errore");
          bottone.disabled = false;
        })
        .catch(function () {
          messaggio(notificheData.azioneErrore, "pairing-errore");
          bottone.disabled = false;
        });
    });
  })();

  /* ---------- pannello Notifiche: levetta muto Telegram per progetto (SS7-ter/1) ----------
     Un solo bottone che capovolge lo stato a ogni clic: POST /notify/telegram/toggle
     tocca solo config.json (nessun cambio a graph.json), quindi non arriva nessun
     reload SSE a farlo vedere. Il DOM si aggiorna qui con la risposta del server, che
     e' l'unica fonte di verita' sullo stato nuovo. Il markup manca del tutto quando
     Telegram non e' configurato su questa installazione (render_notif_telegram.py):
     qui non c'e' niente da disabilitare in quel caso, solo da saltare offline. */
  (function mutoTelegram() {
    var bottone = document.querySelector(".notif-muto");
    if (!bottone) return;
    if (!servito) {
      bottone.disabled = true;
      bottone.title = notificheData.azioneOffline || "";
      return;
    }
    var statoEl = bottone.querySelector(".notif-muto-stato");
    var azioneEl = bottone.querySelector(".notif-muto-azione");
    function applica(acceso) {
      bottone.dataset.muto = acceso ? "on" : "off";
      bottone.setAttribute("aria-pressed", String(acceso));
      statoEl.textContent = acceso ? bottone.dataset.statoOn : bottone.dataset.statoOff;
      azioneEl.textContent = acceso ? bottone.dataset.azioneOn : bottone.dataset.azioneOff;
    }
    bottone.addEventListener("click", function () {
      bottone.disabled = true;
      fetch("/notify/telegram/toggle", { method: "POST" })
        .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
        .then(function (esito) { applica(esito.enabled); bottone.disabled = false; })
        .catch(function () { bottone.disabled = false; });
    });
  })();

  /* ---------- pannello Notifiche: avviso browser per una Interazione nuova ----------
     L'SSE ricarica l'intera pagina a ogni cambio del grafo (vedi sopra): qui non
     sopravvive nessuno stato di sessione da confrontare, solo cio' che resta in
     localStorage attraverso il reload. Alla primissima visita (nessuna base salvata)
     non si avvisa di nulla: annuncerebbe come "nuove" tutte le card gia' aperte prima
     che questa pagina esistesse. E un avviso mentre la scheda e' gia' quella attiva e
     a fuoco duplicherebbe il rumore che il pannello mostra gia' da solo: si aggiorna
     comunque la base vista, ma il popup parte solo a scheda nascosta o senza fuoco. */
  var STORAGE_VISTE = "atlas-notificate";
  var quiete = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var notifToggle = document.querySelector(".notifiche-toggle");
  function idInterazioniAperte() {
    return Array.prototype.map.call(
      document.querySelectorAll(".notif-attenzione[data-interaction]"),
      function (li) { return li.dataset.interaction; });
  }
  (function avvisiLocali() {
    if (!("Notification" in window)) return;
    var correnti = idInterazioniAperte();
    var viste = null;
    try { viste = JSON.parse(localStorage.getItem(STORAGE_VISTE)); } catch (e) { /* niente da confrontare */ }
    function segnaViste() {
      try { localStorage.setItem(STORAGE_VISTE, JSON.stringify(correnti)); } catch (e) { /* vale solo per questa pagina */ }
    }
    if (!Array.isArray(viste)) { segnaViste(); return; }   // prima visita: solo la base
    var nuove = correnti.filter(function (id) { return viste.indexOf(id) === -1; });
    segnaViste();
    if (!nuove.length || Notification.permission === "denied") return;
    if (!document.hidden && document.hasFocus()) return;   // gia' a video: il pannello basta da solo
    function mostra() {
      nuove.forEach(function (id) {
        var card = document.querySelector('.notif-attenzione[data-interaction="' + id + '"]');
        if (!card) return;
        var testo = card.querySelector(".notif-testo");
        var n = new Notification(document.title, {
          body: testo ? testo.textContent : id,
          tag: "atlas-interazione-" + id,
        });
        n.onclick = function () {
          window.focus();
          document.documentElement.dataset.notifiche = "aperto";
          notifToggle.setAttribute("aria-expanded", "true");
          card.scrollIntoView({ behavior: quiete ? "auto" : "smooth", block: "center" });
          card.classList.add("notif-evidenzia");
          setTimeout(function () { card.classList.remove("notif-evidenzia"); }, 1600);
          n.close();
        };
      });
    }
    if (Notification.permission === "granted") return mostra();
    Notification.requestPermission().then(function (perm) { if (perm === "granted") mostra(); });
  })();
})();
