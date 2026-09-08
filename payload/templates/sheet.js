/* Scheda del ticket laterale: markdown, rendering, interazione. */
(function () {
  "use strict";

  var DATA = JSON.parse(document.getElementById("atlas-data").textContent);
  var quiete = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var vp = document.querySelector(".viewport");

  /* ---------- markdown minimo: prima si nega l'HTML, poi si concede il markdown ---------- */
  function esc(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
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

  /* ---------- vista Nodo del pannello destro (S12) ----------
     Fino a S11 questa era una scheda modale: apriva un velo, si chiudeva col
     velo o con un clic fuori. Ora e' una delle due viste di '.notifiche'
     (l'altra e' quella delle Interazioni, notifiche.js), un pannello
     persistente che si comanda solo a mano - niente chiusura implicita.
     'pannello' e i due bottoni-tab sono chrome del contenitore, non del
     ticket, ma sheet.js li tocca comunque: il contratto fra moduli passa dal
     DOM (attributi, classi), mai da funzioni condivise, quindi non c'e' un
     "notifiche.js" da chiamare per dire "mostrami" - si scrive l'attributo e
     basta, notifiche.js legge lo stesso DOM se deve reagire (il suo
     selettore di tab, per esempio). */
  var sheet = document.querySelector(".sheet");
  var pannello = document.querySelector(".notifiche");
  var tabNotifiche = pannello.querySelector('.panel-tab[data-vista="notifiche"]');
  var tabNodo = pannello.querySelector('.panel-tab[data-vista="nodo"]');
  var toggle = pannello.querySelector(".notifiche-toggle");
  var chips = sheet.querySelector(".sheet-chips");
  var titolo = sheet.querySelector(".sheet-title");
  var scorrimento = sheet.querySelector(".sheet-scroll");   // il contenitore che scorre (S13): non e' piu' '.sheet-body'
  var domanda = sheet.querySelector(".sheet-question");
  var corpo = sheet.querySelector(".sheet-body");
  var artefatti = sheet.querySelector(".sheet-artifacts");
  var raw = sheet.querySelector(".sheet-raw");
  var ultimoFocus = null;
  var nodoPopolato = false;   // true dopo il primo popolaScheda() riuscito: guardia per il tab "Nodo"
  var CHIAVE_VISTA = "atlas-vista-pannello";
  var CHIAVE_NODO = "atlas-nodo-sheet";

  function chip(testo, classe, stile) {
    var s = document.createElement("span");
    s.className = "schip" + (classe ? " " + classe : "");
    if (stile) s.setAttribute("style", stile);
    s.innerHTML = testo;
    return s;
  }

  /* Mostra la vista Nodo, aggiorna il selettore e ricorda la scelta - ma non
     tocca l'apertura del pannello: quella la decide solo chi chiama (apri()
     la forza aperta perche' viene da un clic/Invio sul nodo, il ripristino a
     fine file no, perche' deve rispettare lo stato aperto/chiuso gia'
     ripristinato prima del primo paint da render.py). */
  function mostraVistaNodo() {
    pannello.dataset.vista = "nodo";
    tabNodo.setAttribute("aria-selected", "true");
    tabNotifiche.setAttribute("aria-selected", "false");
    try { localStorage.setItem(CHIAVE_VISTA, "nodo"); } catch (e) { /* vale solo per questa pagina */ }
  }

  function popolaScheda(id) {
    var n = DATA.nodes[id];
    if (!n) return false;
    var st = DATA.states[n.state] || { glyph: "", label: n.state };
    chips.textContent = "";
    chips.appendChild(chip(st.glyph + " " + esc(st.label), "state", "--sc:var(--st-" + n.state + ")"));
    chips.appendChild(chip(esc(n.type + " · " + n.mode)));
    chips.appendChild(chip('<svg class="bshape" viewBox="0 0 24 24" width="9" height="9" ' +
      'aria-hidden="true"><path d="' + n.branchShape + '" fill="' + n.branchColor +
      '"/></svg>' + esc(n.branchLabel)));
    var nomi = Array.isArray(n.owner) ? n.owner : (n.owner ? [n.owner] : []);
    nomi.forEach(function (nome, i) {
      chips.appendChild(chip(esc(i ? nome : sheet.dataset.ownerLabel + " " + nome), "who"));
    });
    if (n.model) chips.appendChild(chip(esc(n.model)));
    if (n.cost) chips.appendChild(chip(esc(n.cost)));
    titolo.innerHTML = '<span class="sid" data-copy="' + esc(id) + '" title="' + esc(sheet.dataset.copia) +
      '" data-copiato="' + esc(sheet.dataset.copiato) + '">' + esc(id) + "</span>" +
      '<span class="stt" data-copy="' + esc(n.title) + '" title="' + esc(sheet.dataset.copia) +
      '" data-copiato="' + esc(sheet.dataset.copiato) + '">' + esc(n.title) + "</span>";
    domanda.textContent = n.question;
    var md = (n.md || "").trim();
    corpo.innerHTML = md ? markdown(esc(md))
      : '<p class="sheet-empty">' + esc(sheet.dataset.empty) + "</p>";
    scorrimento.scrollTop = 0;
    var listaArtefatti = Array.isArray(n.artifacts) ? n.artifacts : [];
    artefatti.innerHTML = listaArtefatti.length
      ? '<li class="sheet-artifacts-label">' + esc(sheet.dataset.artefattiLabel) + "</li>"
        + listaArtefatti.map(function (a) { return "<li><code>" + esc(a) + "</code></li>"; }).join("")
      : "";
    raw.href = "tickets/" + id + ".md";
    nodoPopolato = true;
    mostraVistaNodo();
    try { localStorage.setItem(CHIAVE_NODO, id); } catch (e) { /* vale solo per questa pagina */ }
    return true;
  }

  /* Apertura vera, da un gesto dell'utente (clic su un nodo, o Invio da
     keyboard.js che simula lo stesso clic): popola la scheda e, solo se il
     pannello era chiuso, lo forza aperto - se era gia' aperto su un'altra
     vista o su un altro nodo, cambia solo cio' che mostra (nessuna riapertura
     inutile del bottone). */
  function apri(id) {
    if (!popolaScheda(id)) return;
    if (document.documentElement.dataset.notifiche === "chiuso") {
      document.documentElement.dataset.notifiche = "aperto";
      toggle.setAttribute("aria-expanded", "true");
      try { localStorage.setItem("atlas-notifiche", "aperto"); } catch (e) { /* vale solo per questa pagina */ }
    }
    ultimoFocus = document.activeElement;
    sheet.querySelector(".sheet-close").focus();
  }

  /* Chiude l'intero pannello (non solo la vista Nodo): e' l'equivalente da
     tastiera/da scheda del bottone di notifiche.js, mai un effetto
     collaterale di un clic altrove - quello non chiude piu' nulla (S12). */
  function chiudi() {
    if (document.documentElement.dataset.notifiche === "chiuso") return;
    document.documentElement.dataset.notifiche = "chiuso";
    toggle.setAttribute("aria-expanded", "false");
    try { localStorage.setItem("atlas-notifiche", "chiuso"); } catch (e) { /* vale solo per questa pagina */ }
    if (pannello.dataset.vista === "nodo" && ultimoFocus && ultimoFocus.focus) ultimoFocus.focus();
  }

  /* Selezione: un nodo alla volta, la classe sta sulla card della mappa
     (render_svg.py, '.n.sel'), non su chi ha generato il clic - un clic dalla
     tabella o dal pannello seleziona comunque la carta giusta. E' il
     presupposto delle palline sugli archi (A05), dell'evidenziazione persistente
     di archi/nodi (edges.css, render_edges.hover_css) e della navigazione da
     tastiera (C12): chi legge '.sel' non deve sapere come ci e' arrivata. */
  function deseleziona() {
    var precedente = document.querySelector(".map .n.sel");
    if (precedente) precedente.classList.remove("sel");
  }
  function seleziona(id) {
    deseleziona();
    var carta = document.getElementById("node-" + id);
    if (carta) carta.classList.add("sel");
  }

  document.addEventListener("click", function (e) {
    // 'trascina' la aggiungono canvas.js/drag.js a '.viewport' a inizio pan
    // (e ora anche a 'body', per la selezione di testo: C13, non tocca questo
    // controllo, che legge sempre e solo il viewport): un pan che finisce
    // sopra una card non deve aprirla, ne' deselezionare.
    if (vp.classList.contains("trascina")) return;
    var via = e.target.closest ? e.target.closest("[data-node]") : null;
    if (!via) {
      // un clic altrove toglie la selezione, tranne dentro al pannello
      // laterale: leggerne il contenuto non deve far sparire l'evidenziazione
      // sulla mappa che quel contenuto sta spiegando.
      if (!(e.target.closest && e.target.closest(".pannello"))) deseleziona();
      return;
    }
    e.preventDefault();
    var id = via.dataset.node || via.getAttribute("data-node");
    seleziona(id);
    apri(id);
  });
  sheet.querySelector(".sheet-close").addEventListener("click", chiudi);

  /* Selettore Notifiche/Nodo (S11 lo disegna, S12 lo cabla): tornare a
     Notifiche e' sempre disponibile; tornare a Nodo senza aver mai aperto un
     nodo lascerebbe la vista vuota, quindi il tab non fa nulla in quel caso -
     mostraVistaNodo() gia' e' innocuo a rieseguirlo se la vista e' gia' quella. */
  tabNotifiche.addEventListener("click", function () {
    pannello.dataset.vista = "notifiche";
    tabNotifiche.setAttribute("aria-selected", "true");
    tabNodo.setAttribute("aria-selected", "false");
    try { localStorage.setItem(CHIAVE_VISTA, "notifiche"); } catch (e) { /* vale solo per questa pagina */ }
  });
  tabNodo.addEventListener("click", function () {
    if (nodoPopolato) mostraVistaNodo();
  });

  /* Escape: da modale a pannello comandato a mano, resta comunque una
     scorciatoia di chiusura deliberata (non un dismiss accidentale come lo
     era il velo o il clic fuori, che qui non esistono piu') - simmetrica
     all'Invio di keyboard.js, che apre. keyboard.js sospende le frecce di pan
     mentre la vista Nodo e' quella mostrata: stessa ragione per cui restava
     sospeso mentre la scheda era modale, il fuoco resta dentro il pannello. */
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") chiudi();
  });

  /* Ripristino: la vista sopravvive al reload come gia' fa oggi lo stato
     aperto/chiuso (quello lo ripristina render.py prima del primo paint,
     perche' sposta colonne intere della griglia; questo cambia solo cosa si
     vede dentro una colonna che non cambia dimensione, quindi non serve
     anticiparlo prima del paint). Se l'ultimo nodo non esiste piu' in questo
     grafo (chiuso e archiviato altrove, o il grafo e' cambiato) popolaScheda()
     non fa nulla e la vista resta quella di partenza, Notifiche: meglio quella
     che un pannello Nodo vuoto senza nessun contenuto da mostrare. */
  (function ripristinaVista() {
    var vista = null, ultimoNodo = null;
    try {
      vista = localStorage.getItem(CHIAVE_VISTA);
      ultimoNodo = localStorage.getItem(CHIAVE_NODO);
    } catch (e) { /* niente da ripristinare: resta la vista di partenza nel markup */ }
    if (vista === "nodo" && ultimoNodo) popolaScheda(ultimoNodo);
  })();
})();
