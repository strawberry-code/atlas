/* Comportamento della dashboard Atlas. Risorsa neutra di lingua, incorporata
   inline da render.py: ogni stringa visibile arriva dal markup o dal JSON
   #atlas-data, mai da qui. Vietata la sequenza di chiusura script nei letterali. */
(function () {
  "use strict";

  var DATA = JSON.parse(document.getElementById("atlas-data").textContent);
  var quiete = matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- tema: il toggle vince sul sistema, e resta ---------- */
  var toggle = document.querySelector(".theme");
  toggle.addEventListener("click", function () {
    var scuroOra = document.documentElement.dataset.theme === "dark" ||
      (!document.documentElement.dataset.theme &&
        matchMedia("(prefers-color-scheme: dark)").matches);
    var scelto = scuroOra ? "light" : "dark";
    document.documentElement.dataset.theme = scelto;
    try { localStorage.setItem("atlas-theme", scelto); } catch (e) { /* file:// senza storage: il tema vale per la pagina */ }
  });

  /* ---------- vista: mappa o tabella, stesso principio del tema ---------- */
  var vista = document.querySelector(".viewmode");
  vista.addEventListener("click", function () {
    var tabellaOra = document.documentElement.dataset.view === "table";
    var scelto = tabellaOra ? "map" : "table";
    document.documentElement.dataset.view = scelto;
    try { localStorage.setItem("atlas-view", scelto); } catch (e) { /* vale solo per questa pagina */ }
  });

  /* ---------- tabella: ordinamento per colonna ----------
     Ogni cella porta gia' il suo valore di confronto in data-v (vedi
     render_table.py): qui si ordina e basta, senza interpretare testo di
     dominio. Un confronto numerico solo quando l'intera stringa e' un numero,
     altrimenti un confronto naturale a blocchi, cosi' 'F2' precede 'F10' invece
     di seguirlo come farebbe un confronto lessicografico puro. */
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
    // Nomi non generici apposta: 'corpo' e 'tabella' sono gia' presi piu' sotto
    // per la scheda del ticket, e 'var' in questa IIFE e' di funzione, non di
    // blocco: un nome ripetuto avrebbe silenziosamente sovrascritto l'altro,
    // lasciando questo tbody orfano al primo clic su un'intestazione.
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

  /* ---------- count-up del numero di avanzamento, in coppia con l'anello ----------
     Chi ha chiesto quiete vede subito il valore finale, che il markup porta gia'. */
  var pct = document.querySelector(".pct");
  if (pct && !quiete) {
    var finale = parseInt(pct.dataset.count, 10) || 0;
    var t0 = null;
    var passo = function (ts) {
      if (t0 === null) t0 = ts;
      var q = Math.min((ts - t0) / 1100, 1);
      q = 1 - Math.pow(1 - q, 3);
      pct.textContent = Math.round(finale * q) + "%";
      if (q < 1) requestAnimationFrame(passo);
    };
    requestAnimationFrame(passo);
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
      return;
    }
    document.body.dataset.filter = stato;
    var chip = document.querySelector('.legend .chip[data-state="' + stato + '"]');
    if (chip) chip.classList.add("on");
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
    // Immediate, non solo stopPropagation: nella tabella l'id da copiare sta
    // dentro la riga che apre la scheda (entrambi ascoltano su document), e
    // stopPropagation da solo non basta a fermare un ascoltatore successivo
    // sullo stesso nodo, solo la risalita verso gli antenati.
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
     nodi portano data-owner, e senza ancoraggio aprire un ticket accenderebbe
     pure il filtro della persona a cui quel nodo e' assegnato. */
  document.addEventListener("click", function (e) {
    var presa = e.target.closest && e.target.closest(".legend .chip[data-owner], .side li[data-owner]");
    if (!presa) return;
    var chi = presa.dataset.owner;
    var attivo = document.body.dataset.owner === chi;
    document.querySelectorAll("[data-owner].on").forEach(function (x) { x.classList.remove("on"); });
    if (attivo) {
      delete document.body.dataset.owner;
      return;
    }
    document.body.dataset.owner = chi;
    document.querySelectorAll(".legend .chip[data-owner='" + chi + "'], .side li[data-owner='" + chi + "']")
      .forEach(function (x) { x.classList.add("on"); });
  });

  /* ---------- markdown minimo: prima si nega l'HTML, poi si concede il markdown ---------- */
  function esc(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  /* Un ticket lo scrive un agente, che a sua volta legge fonti che non controlliamo:
     'javascript:' dietro un link dall'aria innocua eseguirebbe al primo clic. Passano
     solo gli schemi che servono davvero a un ticket, piu' i percorsi relativi. */
  var SCHEMA_SICURO = /^(https?:|mailto:|#|[.]{0,2}\/|[\w.-]+[.](md|txt|png|jpe?g|svg|pdf)([#?]|$))/i;
  function inline(s) {
    return s
      .replace(/`([^`]+)`/g, function (_, c) { return "<code>" + c + "</code>"; })
      .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
      .replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, "$1<i>$2</i>")
      .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, function (intero, testo, href) {
        if (!SCHEMA_SICURO.test(href)) return testo + " (" + href + ")";
        return '<a href="' + href + '" target="_blank" rel="noopener noreferrer">' + testo + "</a>";
      });
  }
  function markdown(src) {
    src = src.replace(/&lt;!--[\s\S]*?--&gt;/g, "");   // commenti HTML: appunti, non contenuto
    var righe = src.split("\n"), html = [], para = [], dentro = null;
    function chiudiPara() {
      if (para.length) { html.push("<p>" + inline(para.join(" ")) + "</p>"); para = []; }
    }
    for (var i = 0; i < righe.length; i++) {
      var r = righe[i];
      if (dentro === "pre") {
        if (/^```/.test(r)) { html.push("</code></pre>"); dentro = null; }
        else html.push(r);
        continue;
      }
      if (/^```/.test(r)) { chiudiPara(); html.push('<pre><code>'); dentro = "pre"; continue; }
      var m;
      if ((m = r.match(/^(#{1,4})\s+(.*)/))) {
        chiudiPara();
        var h = m[1].length;
        html.push("<h" + h + ">" + inline(m[2]) + "</h" + h + ">");
      } else if (/^(---|\*\*\*|___)\s*$/.test(r)) {
        chiudiPara(); html.push("<hr>");
      } else if ((m = r.match(/^&gt;\s?(.*)/))) {
        chiudiPara();
        var cit = [m[1]];
        while (i + 1 < righe.length && (m = righe[i + 1].match(/^&gt;\s?(.*)/))) { cit.push(m[1]); i++; }
        html.push("<blockquote><p>" + inline(cit.join(" ")) + "</p></blockquote>");
      } else if ((m = r.match(/^\s*(?:[-*+]|\d+[.)])\s+(.*)/))) {
        chiudiPara();
        var ordinata = /^\s*\d/.test(r), voci = [];
        var vocale = function (t) {
          var box = t.match(/^\[([ xX])\]\s+(.*)/);
          if (box) {
            return '<li><input type="checkbox" disabled' +
              (box[1] === " " ? "" : " checked") + ">" + inline(box[2]) + "</li>";
          }
          return "<li>" + inline(t) + "</li>";
        };
        voci.push(vocale(m[1]));
        while (i + 1 < righe.length && (m = righe[i + 1].match(/^\s*(?:[-*+]|\d+[.)])\s+(.*)/))) {
          voci.push(vocale(m[1])); i++;
        }
        html.push((ordinata ? "<ol>" : "<ul>") + voci.join("") + (ordinata ? "</ol>" : "</ul>"));
      } else if (/^\s*$/.test(r)) {
        chiudiPara();
      } else {
        para.push(r.trim());
      }
    }
    chiudiPara();
    if (dentro === "pre") html.push("</code></pre>");    // fence mai chiusa: si chiude qui
    return html.join("\n");
  }

  /* ---------- la mappa: pan col mouse, zoom con pulsanti e ctrl+rotella ---------- */
  var vp = document.querySelector(".viewport");
  var svg = vp.querySelector("svg");
  var baseW = parseFloat(svg.getAttribute("width")) || 600;
  var baseH = parseFloat(svg.getAttribute("height")) || 200;
  var zoomLevel = 1;    // scala disegnata in questo istante
  var zoomVoluto = 1;   // scala verso cui si sta andando
  var ancoraX = 0, ancoraY = 0;   // punto del viewport che deve restare fermo
  var rafZoom = 0;
  var trascinato = false;

  function limita(z) { return Math.min(2.5, Math.max(0.25, z)); }

  function applicaZoom(z, cx, cy) {
    var k = z / zoomLevel;
    var sx = (vp.scrollLeft + cx) * k - cx;
    var sy = (vp.scrollTop + cy) * k - cy;
    zoomLevel = z;
    svg.style.width = baseW * z + "px";
    svg.style.height = baseH * z + "px";
    vp.scrollLeft = sx;
    vp.scrollTop = sy;
  }
  /* Lo zoom non salta al valore nuovo: si avvicina, e la strada che copre
     dipende dal tempo passato, non dal numero di frame. Legarla al frame
     renderebbe la corsa doppia su uno schermo a 120 Hz rispetto a uno a 60.
     Cosi' una raffica di eventi della rotella, che un trackpad produce a
     decine per un solo movimento del dito, diventa una corsa continua invece
     di una scalinata. */
  var zoomTs = 0;
  function passoZoom(ts) {
    var dt = zoomTs ? Math.min(ts - zoomTs, 100) : 16;   // una scheda tornata in primo piano
    zoomTs = ts;
    var nuovo = zoomLevel + (zoomVoluto - zoomLevel) * (1 - Math.exp(-dt / 70));
    if (Math.abs(zoomVoluto - nuovo) < .002) nuovo = zoomVoluto;   // o non arriva mai
    applicaZoom(nuovo, ancoraX, ancoraY);
    if (nuovo === zoomVoluto) { rafZoom = 0; zoomTs = 0; return; }
    rafZoom = requestAnimationFrame(passoZoom);
  }
  function verso(z, cx, cy) {
    zoomVoluto = limita(z);
    ancoraX = cx;
    ancoraY = cy;
    if (quiete) return applicaZoom(zoomVoluto, cx, cy);   // chi ha chiesto quiete arriva subito
    if (!rafZoom) rafZoom = requestAnimationFrame(passoZoom);
  }
  function adatta() {
    if (rafZoom) { cancelAnimationFrame(rafZoom); rafZoom = 0; zoomTs = 0; }
    zoomVoluto = limita(Math.min((vp.clientWidth - 52) / baseW, (vp.clientHeight - 130) / baseH, 1));
    applicaZoom(zoomVoluto, 0, 0);   // inquadrare tutto e' un salto voluto, non una corsa
    vp.scrollLeft = 0;
    vp.scrollTop = 0;
  }
  document.querySelectorAll(".zoom button").forEach(function (b) {
    b.addEventListener("click", function () {
      if (b.dataset.zoom === "fit") return adatta();
      var k = b.dataset.zoom === "in" ? 1.25 : 0.8;
      verso(zoomVoluto * k, vp.clientWidth / 2, vp.clientHeight / 2);
    });
  });
  vp.addEventListener("wheel", function (e) {
    if (!e.ctrlKey && !e.metaKey) return;       // la rotella nuda scorre e basta
    e.preventDefault();
    /* deltaY arriva in pixel dal trackpad e in righe dal mouse a scatti: senza
       normalizzarlo, e senza legare la scala a quanto vale, lo stesso gesto
       ingrandisce di una frazione su un dispositivo e di cinque volte sull'altro. */
    var d = e.deltaMode === 1 ? e.deltaY * 16
      : e.deltaMode === 2 ? e.deltaY * vp.clientHeight : e.deltaY;
    d = Math.max(-120, Math.min(120, d));       // un colpo secco non teletrasporta
    var r = vp.getBoundingClientRect();
    verso(zoomVoluto * Math.exp(-d * .0022), e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });
  vp.addEventListener("pointerdown", function (e) {
    if (e.pointerType !== "mouse" || e.button !== 0) return;   // il tocco scorre gia' da solo
    var px = e.clientX, py = e.clientY, sx = vp.scrollLeft, sy = vp.scrollTop;
    trascinato = false;
    function muovi(ev) {
      if (Math.abs(ev.clientX - px) + Math.abs(ev.clientY - py) > 4) trascinato = true;
      if (trascinato) {
        vp.classList.add("trascina");
        vp.scrollLeft = sx - (ev.clientX - px);
        vp.scrollTop = sy - (ev.clientY - py);
      }
    }
    function fine() {
      vp.classList.remove("trascina");
      vp.removeEventListener("pointermove", muovi);
      vp.removeEventListener("pointerup", fine);
    }
    vp.addEventListener("pointermove", muovi);
    vp.addEventListener("pointerup", fine);
  });
  if (baseW > vp.clientWidth || baseH > vp.clientHeight) adatta();

  /* ---------- side sheet del ticket ---------- */
  var sheet = document.querySelector(".sheet");
  var chips = sheet.querySelector(".sheet-chips");
  var titolo = sheet.querySelector(".sheet-title");
  var domanda = sheet.querySelector(".sheet-question");
  var corpo = sheet.querySelector(".sheet-body");
  var raw = sheet.querySelector(".sheet-raw");
  var ultimoFocus = null;

  function chip(testo, classe, stile) {
    var s = document.createElement("span");
    s.className = "schip" + (classe ? " " + classe : "");
    if (stile) s.setAttribute("style", stile);
    s.innerHTML = testo;
    return s;
  }

  function apri(id) {
    var n = DATA.nodes[id];
    if (!n) return;
    var st = DATA.states[n.state] || { glyph: "", label: n.state };
    chips.textContent = "";
    chips.appendChild(chip(st.glyph + " " + esc(st.label), "state", "--sc:var(--st-" + n.state + ")"));
    chips.appendChild(chip(esc(n.type + " · " + n.mode)));
    chips.appendChild(chip('<svg class="bshape" viewBox="0 0 24 24" width="9" height="9" ' +
      'aria-hidden="true"><path d="' + n.branchShape + '" fill="' + n.branchColor +
      '"/></svg>' + esc(n.branchLabel)));
    if (n.owner) chips.appendChild(chip(esc(sheet.dataset.ownerLabel + " " + n.owner), "who"));
    if (n.cost) chips.appendChild(chip(esc(n.cost)));
    titolo.innerHTML = '<span class="sid" data-copy="' + esc(id) + '" title="' + esc(sheet.dataset.copia) +
      '" data-copiato="' + esc(sheet.dataset.copiato) + '">' + esc(id) + "</span>" +
      '<span class="stt" data-copy="' + esc(n.title) + '" title="' + esc(sheet.dataset.copia) +
      '" data-copiato="' + esc(sheet.dataset.copiato) + '">' + esc(n.title) + "</span>";
    domanda.textContent = n.question;
    var md = (n.md || "").trim();
    corpo.innerHTML = md ? markdown(esc(md))
      : '<p class="sheet-empty">' + esc(sheet.dataset.empty) + "</p>";
    corpo.scrollTop = 0;
    raw.href = "tickets/" + id + ".md";
    ultimoFocus = document.activeElement;
    document.body.classList.add("sheet-open");
    sheet.querySelector(".sheet-close").focus();
  }

  function chiudi() {
    if (!document.body.classList.contains("sheet-open")) return;
    document.body.classList.remove("sheet-open");
    if (ultimoFocus && ultimoFocus.focus) ultimoFocus.focus();
  }

  document.addEventListener("click", function (e) {
    var via = e.target.closest ? e.target.closest("[data-node]") : null;
    if (!via) return;
    e.preventDefault();                     // niente navigazione: il ticket si apre qui
    if (trascinato) { trascinato = false; return; }   // era un pan, non un click
    apri(via.dataset.node || via.getAttribute("data-node"));
  });
  sheet.querySelector(".sheet-close").addEventListener("click", chiudi);
  document.querySelector(".scrim").addEventListener("click", chiudi);
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") chiudi();
  });
})();
