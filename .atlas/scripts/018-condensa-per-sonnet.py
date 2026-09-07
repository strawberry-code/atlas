"""Il grafo si condensa: i nodi erano dimensionati su un agente piccolo.

I 51 nodi nascevano da due vincoli che adesso non valgono piu'. Il primo era la
capacita' dell'agente: un nodo doveva stare in una sessione di un modello piccolo.
Il secondo era il parallelismo per file: la catena Canvas era spezzata in undici
passi non perche' il lavoro fosse undici cose, ma perche' due agenti non potevano
toccare canvas.js insieme. Con un modello capace il costo di undici giri di
contesto supera il beneficio, e un nodo torna a essere quello che deve essere: una
sessione di lavoro vera.

Restano intatti i quattro cancelli, la proprieta' dei file dichiarata in artifacts
e la regola che due nodi prendibili insieme non condividono un sorgente.
Quarantaquattro nodi aperti diventano ventisette.
"""
from core import mutate

NODAVIA = "~/cristiano/10-projects/16-llm-apps/nodavia/web/src"


def run(g):
    # ============================================================ ramo F: 5 -> 3
    mutate.edit_node(
        g, "F01", blockedBy=["G02"],
        title="Grafite entra nel payload, e la mappa esce da render.py",
        artifacts=["payload/templates/grafite.css", "payload/templates/grafite.fonts.css",
                   "payload/core/render_canvas.py", "payload/core/render.py"],
        question=(
            "Due lavori sullo stesso file, che conviene fare in un passaggio solo.\n\n"
            "**Grafite entra.** Porta dentro Atlas i due fogli prodotti nella repo Grafite "
            "(dist/grafite.offline.css e dist/grafite.fonts.inline.css) come risorse del payload, e "
            "falli concatenare da leggi_css_dashboard() in risorse.py prima di tutto il resto: prima "
            "i font, poi Grafite, poi i sette fogli di Atlas che ne consumano i token. I due file "
            "arrivano da la' e non si modificano qui: in testa a ognuno va una riga che dice da dove "
            "vengono e che si rigenerano nella loro repo, altrimenti al primo ritocco locale il "
            "design system smette di essere la fonte.\n\n"
            "**La mappa esce.** Oggi render.py assembla anche il contenitore della mappa, il "
            "viewport e i comandi di zoom. Se resta li', il ramo Canvas e il ramo Superficie si "
            "contendono render.py per tutto il resto del progetto. Sposta in un modulo nuovo "
            "payload/core/render_canvas.py: contenitore della mappa, viewport, comandi di zoom. "
            "Restano a render.py la topbar coi suoi bottoni, la colonna dei pannelli, la legenda, il "
            "suggerimento sotto la mappa e l'assemblaggio della pagina. render_svg.py continua a "
            "disegnare i nodi e viene chiamato da render_canvas. Quel confine e' la regola di "
            "proprieta' dei file per tutto il grafo: scrivilo nel docstring del modulo nuovo.\n\n"
            "E' fatto quando: la dashboard contiene i @font-face e i token Grafite, non chiede "
            "niente alla rete, la pagina generata e' per il resto identica, render_canvas.py sta "
            "sotto le 200 righe, e render.py non nomina piu' nessuna classe CSS del canvas."))

    mutate.edit_node(
        g, "F04", blockedBy=["F01"],
        title="Via il tema scuro, e i token si appoggiano a Grafite",
        artifacts=["payload/templates/tokens.css", "payload/core/render.py",
                   "payload/core/strings_cli.py", "payload/core/theme.py", "tests/test_motore.py"],
        question=(
            "**Il tema scuro esce di scena.** Grafite e' monotema chiaro per scelta dichiarata, ed e' "
            "la strada scelta anche qui. Togli il bottone in render.py con la sua icona sole/luna, il "
            "blocco @media (prefers-color-scheme: dark), la tavola :root[data-theme=dark], la memoria "
            "della preferenza in chrome.js, la stringa 'render.tema' e la classe di test "
            "TavolozzaScura in tests/test_motore.py. Toglilo davvero, non disattivarlo: una tavola "
            "scura che resta nel foglio senza piu' nessuno che la accenda e' codice morto che il "
            "prossimo lettore cerchera' di capire.\n\n"
            "**I token combaciano.** tokens.css ha una tavola sua (--ink, --muted, --faint, --border, "
            "--pane, --accent, --code-bg e i cinque blocchi --st-*). Grafite porta la propria (--ink, "
            "--bg, --bg-soft, --bg-softer, --muted, --faint, --line, piu' i semantici). I token Atlas "
            "diventano alias di quelli Grafite dove il significato coincide, e spariscono dove "
            "duplicano.\n\n"
            "Restano intatti i colori di stato dei nodi: --st-frontier, --st-claimed, --st-closed, "
            "--st-blocked, --st-out-of-scope con i loro -bg e -tx. Quella e' la semantica del grafo, "
            "non decorazione, ed e' la sola tinta che sopravvive al monocromo di Grafite. theme.py, "
            "che tiene glifi, figure dei rami e anello, va riletto per coerenza ma la sua semantica "
            "non cambia.\n\n"
            "E' fatto quando: nessun sorgente nomina piu' il tema scuro, nessun colore e' dichiarato "
            "due volte, i cinque stati hanno i colori di oggi, e cambiando --ink in Grafite cambia "
            "l'inchiostro di tutta la dashboard."))

    # ============================================================ ramo C: 13 -> 7
    mutate.edit_node(
        g, "C01",
        title="Il canvas di Nodavia: il contratto, e le foto di riferimento",
        artifacts=[".atlas/graphs/260906-grafite-dashboard/notes/nodavia/"],
        question=(
            "Prima di riscrivere, misura. E siccome i cancelli a valle giudicano la somiglianza con "
            "Nodavia senza nessun umano davanti, il termine di paragone non puo' essere un ricordo: "
            "servono le foto, prese adesso.\n\n"
            f"**Il contratto.** Leggi {NODAVIA}/editor/GraphCanvas.tsx e il sorgente di React Flow in "
            "nodavia/node_modules/@xyflow/react, e scrivi il contratto esatto di quel canvas: come si "
            "trasforma il viewport, come si pana, se lo zoom e' ancorato al puntatore o al centro, "
            "zoom minimo e massimo (0.15 e 2.5), parametri del fitView (padding .3, maxZoom .85, "
            "durata 280ms), passo e colore della griglia (22px, #e8e8e7), geometria e comportamento "
            "della minimap, cosa fanno i Controls, quali gesti hanno una scorciatoia da tastiera. "
            "Numeri veri presi dal codice: dove il valore e' un default di React Flow, scrivi da "
            "quale file viene.\n\n"
            "**Le foto.** Avvia Nodavia (node_modules gia' installato: npm run dev dentro web/) e "
            "cattura con un browser headless il canvas di piu' grafi di server/graphs: vista iniziale "
            "rinquadrata, un nodo selezionato con le palline sugli archi, un grafo con un arco di "
            "ritorno, la minimap, la pulsantiera. Salva le immagini nelle note del grafo con un "
            "indice che dice cosa mostra ognuna. Il server di sviluppo e' un comando lungo: lanciato "
            "in background non va aspettato fermandosi, e va spento quando le foto ci sono. Se "
            "Nodavia non parte, non insistere oltre un tentativo ragionevole: annota il motivo e "
            "ripiega sui suoi fogli di stile.\n\n"
            "E' fatto quando: il documento elenca ogni gesto con i suoi parametri e chi legge sa cosa "
            "costruire senza altre domande, e le immagini esistono con il loro indice (oppure e' "
            "scritto perche' non esistono e cosa si usa al loro posto)."))

    mutate.edit_node(
        g, "C02", blockedBy=["C01"],
        title="La superficie: transform, pan, zoom, griglia",
        artifacts=["payload/templates/canvas.js", "payload/templates/canvas.css",
                   "payload/core/render_canvas.py"],
        question=(
            "Sostituisci il viewport attuale con la superficie di React Flow, in vanilla.\n\n"
            "**L'impianto.** Un contenitore che ritaglia, dentro un pannello che porta un solo "
            "transform translate(x,y) scale(k), e dentro ancora il livello degli archi (SVG) e quello "
            "dei nodi. Tutte le coordinate del grafo restano in spazio-grafo, la trasformazione e' "
            "una sola e vive sul pannello. Servono le funzioni di conversione fra coordinate schermo "
            "e coordinate grafo, ed e' roba che si prova senza browser.\n\n"
            "**I gesti.** Trascinamento del pannello col puntatore, zoom a rotella ancorato al "
            "puntatore (il punto sotto il cursore non si muove), limiti 0.15 e 2.5, doppio clic che "
            "rinquadra. Un trascinamento che parte da un nodo o da un arco non pana la superficie. Il "
            "pan non seleziona testo, come gia' fa oggi la classe 'trascina', che canvas.js scrive e "
            "gli altri moduli leggono.\n\n"
            "**La griglia.** Puntini a passo 22px, colore preso dai token, che si spostano e si "
            "scalano col viewport: e' quello che da' la percezione fisica del movimento, e senza di "
            "lui la superficie sembra ferma anche mentre si muove. Si fa in CSS aggiornando "
            "background-size e background-position dal transform.\n\n"
            "E' fatto quando: i gesti si comportano come quelli di Nodavia messi a fianco, uno zoom "
            "seguito da un pan non accumula deriva, i puntini restano ancorati al grafo, e a zoom "
            "molto basso non diventano una nebbia grigia."))

    mutate.edit_node(
        g, "C05", blockedBy=["C02"],
        title="Rinquadratura, pulsantiera, minimap",
        artifacts=["payload/templates/canvas.js", "payload/templates/canvas.css",
                   "payload/core/render_canvas.py"],
        question=(
            "I tre comandi che rendono navigabile un grafo grande.\n\n"
            "**Il fitView.** Calcola il rettangolo che contiene tutti i nodi, sceglie la scala perche' "
            "ci stia con padding 0.3 senza superare 0.85, e ci arriva animando in 280ms con l'easing "
            "morbido di Grafite. Va chiamato all'apertura e da chiunque sposti i nodi d'ufficio: in "
            "Nodavia esiste FitOnKey proprio perche' dopo un cambio di disposizione il grafo scivola "
            "fuori centro e sembra peggiorato anche quando la disposizione e' migliore.\n\n"
            "**I Controls**, vestiti Grafite con le ricette di G04: zoom avanti, zoom indietro, "
            "rinquadra, e il lucchetto che blocca l'interazione. Sostituiscono i due bottoni di zoom "
            "di oggi. Ogni bottone ha la sua aria-label, perche' sono icone senza testo.\n\n"
            "**La minimap.** Riquadro con la sagoma di tutti i nodi, il rettangolo della vista "
            "corrente, maschera rgba(250,250,250,0.78), trascinabile e zoomabile. Con una differenza "
            "dichiarata rispetto a Nodavia, dove il colore del nodo dice il tipo: qui deve dire lo "
            "stato, con i colori --st-*. Su un grafo da cinquanta nodi la minimap e' l'unico posto da "
            "cui si vede a colpo d'occhio dove sono i nodi prendibili.\n\n"
            "E' fatto quando: aprendo un grafo grande si vede tutto e aprendone uno piccolo non si "
            "vede ingigantito, i comandi si raggiungono da tastiera, trascinare la minimap muove la "
            "vista, e l'animazione rispetta prefers-reduced-motion."))

    mutate.edit_node(g, "C09", blockedBy=["C05", "C08"])

    mutate.edit_node(
        g, "C10", blockedBy=["C09"],
        title="Le card si trascinano, e le posizioni restano",
        artifacts=["payload/templates/canvas.js", "payload/core/render_canvas.py"],
        question=(
            "**Il trascinamento.** Come in Nodavia: si afferra una card e la si sposta, gli archi la "
            "seguono in tempo reale. Il gesto parte dalla card e non pana la superficie, e funziona a "
            "qualunque zoom (lo spostamento in spazio-grafo e' quello dello schermo diviso k). Serve "
            "una soglia in pixel sotto la quale il gesto resta un clic, altrimenti aprire la scheda "
            "di un ticket diventa difficile.\n\n"
            "**La persistenza**, che e' la domanda vera. Dove si scrive quella posizione: graph.json "
            "e' il grafo condiviso fra macchine e si fonde con un merge driver, quindi le coordinate "
            "della finestra di qualcuno non ci appartengono. Decidi e implementa: posizioni per grafo "
            "e per macchina, fuori da graph.json (un file accanto, oppure lo storage locale del "
            "browser, che pero' non sopravvive a un cambio di macchina).\n\n"
            "E decidi cosa succede quando il grafo cambia sotto: un nodo nuovo che nessuno ha mai "
            "spostato prende la posizione calcolata, e un nodo sparito non deve lasciare spazzatura "
            "che cresce per sempre.\n\n"
            "E' fatto quando: si sposta una card e gli archi restano attaccati; si ricarica e la card "
            "e' li'; un clic secco apre ancora la scheda; si aggiunge un nodo al grafo e appare al "
            "posto giusto senza scompaginare gli altri; c'e' un modo di tornare al layout automatico."))

    mutate.edit_node(g, "C12", blockedBy=["C10"])

    # ============================================================ ramo A: 6 -> 3
    mutate.edit_node(
        g, "A01",
        title="Geometria degli archi: ortogonale, e la corsia dei ritorni",
        artifacts=["payload/core/edge_geometry.py", "tests/test_edge_geometry.py"],
        question=(
            "Geometria pura in un modulo nuovo, senza import da render_*: si scrive e si prova senza "
            "browser, ed e' l'unico modo di sapere che un arco non e' sparito.\n\n"
            "**Le tratte ortogonali.** Gli archi di oggi sono bezier verticali. Nodavia usa lo "
            "smoothstep di React Flow per la ragione scritta in GraphCanvas.tsx: con ventagli larghi "
            "le bezier collassano in una treccia illeggibile, mentre le tratte ortogonali si fondono "
            "in un bus pulito. Porta in Python getSmoothStepPath di @xyflow/react e roundedPath di "
            f"{NODAVIA}/editor/loopPath.ts, con lo stesso raccordo (CORNER = 10).\n\n"
            "**La corsia dei ritorni.** Porta anche loopPath: un arco che risale esce dal fondo della "
            "sorgente, scavalca le card su una corsia verticale tutta sua (LANE 135, meta' del passo "
            "fra due colonne, cosi' cade fra due colonne e mai dentro una card) e rientra dall'alto "
            "nel bersaglio. La quota di rientro cresce con la lunghezza del giro, cosi' piu' ritorni "
            "che convergono sullo stesso nodo non corrono tutti sulla stessa riga.\n\n"
            "In Atlas un arco che risale ha un significato preciso: col layout a rank di C08, un "
            "blockedBy verso un nodo di rango uguale o maggiore vuol dire che qualcosa nel grafo e' "
            "storto, ed e' il caso che 'atlas doctor' segnala. Decidi come si disegna: corsia "
            "laterale come Nodavia, e in piu' il tratto che lo distingue da un arco sano.\n\n"
            "Il commento in testa a loopPath.ts dice la cosa da non dimenticare: un NaN qui non da' "
            "errore, fa sparire l'arco. I punti coincidenti vanno scartati prima di raccordare. E' "
            "fatto quando: i test coprono arco dritto, gomito, punti coincidenti, raccordo piu' lungo "
            "del segmento e scelta del lato della corsia, e due nodi legati in entrambi i versi "
            "mostrano due archi distinti invece di uno sopra l'altro."))

    mutate.edit_node(
        g, "A03", blockedBy=["A01", "C08"],
        title="Porte di aggancio, tratto, marker e colori di stato",
        artifacts=["payload/core/render_edges.py", "payload/templates/edges.css"],
        question=(
            "L'arco disegnato sulla mappa, con la geometria nuova.\n\n"
            "**Le porte.** render_edges._slots distribuisce i punti di aggancio sul bordo di una card "
            "ordinandoli per la x del nodo collegato, cosi' due archi sullo stesso bordo non si "
            "sovrappongono. Quella logica resta buona e va rimessa in piedi sulla geometria "
            "ortogonale e sul layout a rank. Nodavia ha un solo handle per lato; Atlas distribuisce, "
            "e su un nodo che ne blocca sei e' meglio.\n\n"
            "**La veste.** Tratto sottile grigio Grafite, punta di freccia chiusa alla Nodavia "
            "(ArrowClosed, 18x18). Resta pero' la regola di Atlas che il grigio da solo "
            "cancellerebbe: ogni arco prende il colore dello stato del nodo da cui parte, cosi' le "
            "frecce entranti in un blocco dicono in che stato sono le sue dipendenze senza doverle "
            "cercare sulla mappa, e un blocco con tutte le frecce verdi e' un blocco pronto. Il "
            "bloccato tiene il grigio neutro, per non fare della mappa un cavo aggrovigliato. Le "
            "classi da-<stato> ci sono gia'.\n\n"
            "E' fatto quando: su un nodo con molti archi entranti nessuna coppia si sovrappone, i "
            "cerchietti cadono sul bordo e non dentro, i colori di stato sopravvivono al monocromo di "
            "Grafite, e la punta della freccia si vede a tutti gli zoom."))

    mutate.edit_node(
        g, "A05", blockedBy=["A03", "C09"],
        title="Le palline sugli archi, e la messa a fuoco",
        artifacts=["payload/templates/edges.js", "payload/templates/edges.css"],
        question=(
            f"**Le palline.** Il pezzo piu' bello di Nodavia, in {NODAVIA}/editor/pulse.tsx: "
            "selezionando un nodo, sugli archi che lo toccano scorrono delle palline che dicono in "
            "che verso passa il dato. Copialo davvero, non a occhio. Il numero di palline e la durata "
            "del giro si ricavano dalla lunghezza vera del path (getTotalLength): un arco corto con "
            "otto palline e' una collana, uno lungo con due e' vuoto. L'andatura non e' uniforme: "
            "ogni pallina e' un animateMotion con calcMode spline e keySplines '0.55 0 0.45 1', cosi' "
            "la velocita' dipende dalla posizione lungo l'arco e non dal tempo, che e' esattamente "
            "l'effetto. Lo sfasamento iniziale e' negativo, perche' al primo fotogramma le palline "
            "sono gia' distribuite lungo l'arco invece di partire tutte insieme. Con reduced-motion "
            "restano i punti fermi sull'arco, che sono comunque il segnale. In Atlas il nodo "
            "selezionato e' quello di cui e' aperta la scheda.\n\n"
            "**La messa a fuoco.** La dashboard ha un comportamento che Nodavia non ha e che va "
            "tenuto: passando il mouse su un nodo tutto il resto si spegne (opacity .3 sui nodi, .12 "
            "sugli archi) e resta acceso solo quel che riguarda quel nodo. Le regole per-nodo sono "
            "generate in render_edges.hover_css. Rimettilo in piedi sulla geometria nuova e fallo "
            "convivere con la selezione: hover e selezione sono due segnali diversi e non devono "
            "confondersi.\n\n"
            "E' fatto quando: l'effetto delle palline e' indistinguibile da quello di Nodavia messo a "
            "fianco, lo hover mette a fuoco un nodo e i suoi archi, il filtro di stato della legenda "
            "continua a funzionare, e i due non si annullano a vicenda."))

    # ============================================================ ramo S: 10 -> 5
    mutate.edit_node(
        g, "S01",
        title="Topbar e colonna dei pannelli",
        artifacts=["payload/templates/shell.css", "payload/core/render.py",
                   "payload/core/render_panels.py"],
        question=(
            "**La topbar** coi firmatari di Grafite: wordmark in display con tracking largo e il "
            "pallino nero che respira accanto, eyebrow in maiuscoletto, i tre numeri di sintesi in "
            "mono tabellare grandi, con il count-up all'apertura. Il count-up e' una delle sette "
            "leggi ('un dato che appare senza contare e' un'occasione persa') e il ricettario vanilla "
            "sta nella repo Grafite. Resta il codice dello slug cliccabile che si copia negli "
            "appunti, e il bottone che commuta mappa e tabella.\n\n"
            "**I pannelli** della colonna sinistra con le ricette dense di G03: titolo di sezione con "
            "eyebrow, righe che allo hover scivolano a destra e rivelano il badge nascosto, divisori "
            "hairline, niente gradienti di fondo. Resta il legame con la mappa: passare il mouse su "
            "un blocco o su una sua voce accende sulla mappa i nodi corrispondenti, cliccare fissa il "
            "filtro. Quelle regole vivono in CSS con :has() e vanno riportate sulla struttura "
            "nuova.\n\n"
            "E' fatto quando: aprendo la dashboard i numeri contano una volta e si fermano (e chi ha "
            "chiesto reduced-motion li vede gia' al valore finale), i pannelli sono Grafite, il "
            "legame col canvas funziona ancora, e il blocco di avviso sul grafo che non converge "
            "resta visibilmente un avviso."))

    mutate.edit_node(
        g, "S03", blockedBy=["S01"],
        title="Avanzamento, costo e pannello Notifiche",
        artifacts=["payload/templates/shell.css", "payload/templates/notifiche.css",
                   "payload/core/render_panels.py", "payload/core/render_notifiche.py"],
        question=(
            "**I numeri protagonisti.** L'anello dell'avanzamento e il numero-eroe del costo sono i "
            "due punti dove Grafite dice che i numeri contano: percentuale in mono grande con "
            "tracking negativo e count-up, anello che si riempie una volta sola all'apertura e si "
            "ferma, corona di tacche in tinta neutra. La regola scritta in testa al foglio di oggi "
            "resta valida: il movimento e' ammesso quando accompagna un valore che si legge "
            "all'apertura, non come ciclo perpetuo.\n\n"
            "**Le Notifiche.** Il pannello destro con le card delle Interactions: veste Grafite per "
            "le card, i badge di conteggio, i bottoni di azione, il pairing Telegram, il muto. I "
            "semantici di Grafite (--ok, --down, --warn) sono esattamente quel che serve qui, e vanno "
            "usati come segnale e non come decoro. Resta tutto il comportamento: pannello "
            "richiudibile, bottoni disabilitati quando la pagina e' aperta da file:// invece che da "
            "'atlas serve', evidenziazione della card collegata a un nodo.\n\n"
            "E' fatto quando: l'anello si riempie una volta e la percentuale conta insieme a lui, il "
            "costo si legge da lontano, le card sono Grafite con i tre stati distinguibili, e "
            "tests/test_render_notifiche.py passa."))

    mutate.edit_node(
        g, "S05",
        title="La scheda del ticket, e il suo markdown",
        artifacts=["payload/templates/sheet.css", "payload/core/render_sheet.py"],
        question=(
            "**La scheda** che si apre da destra: veste Grafite (ombra diffusa -24px 0 60px "
            "rgba(0,0,0,.10), entrata con l'easing morbido, chip di stato secondo le ricette nuove, "
            "titolo in display, meta in mono). Restano il comportamento e i dettagli che ci sono "
            "gia': il click-to-copy che conferma con una parola in ::after invece di sostituire il "
            "testo (cosi' la riga non si accorcia sotto il puntatore mentre la si legge), l'anello "
            "che gira sui nodi in lavorazione, la figura del ramo.\n\n"
            "**Il markdown.** Il corpo del ticket e' l'unico posto della dashboard dove si legge "
            "davvero un testo lungo, ed e' li' che la tipografia di Grafite conta di piu': Inter per "
            "il corpo a 13.5-14px con interlinea 1.5-1.65, titoli in Space Grotesk, ogni path, hash e "
            "numero in JetBrains Mono, blocchi di codice su fondo --bg-soft.\n\n"
            "E' fatto quando: la scheda sembra uscita dalla stessa mano del canvas, ogni interazione "
            "di oggi funziona ancora, un ticket lungo si legge senza fatica, e le liste con le "
            "caselle di spunta restano allineate."))

    mutate.edit_node(
        g, "S07", blockedBy=["S01"],
        title="Vista tabellare e legenda che filtra",
        artifacts=["payload/templates/table.css", "payload/templates/legend.css",
                   "payload/core/render_table.py", "payload/core/render_owners.py"],
        question=(
            "**La tabella** e' il posto dove Grafite ha piu' da dire: numeri in mono tabellare, "
            "intestazioni come eyebrow in maiuscoletto con tracking largo, righe che allo hover "
            "cambiano fondo e scivolano, divisori hairline invece di bordi. Restano l'ordinamento per "
            "colonna col suo aria-sort, il clic sulla riga che apre la scheda, e il troncamento a due "
            "righe dei titoli lunghi col title nativo che dice il resto.\n\n"
            "**La legenda** flottante sulla mappa e' anche il filtro per stato e per persona. Chip "
            "Grafite: pill piccola, raggio 6px, tracking largo, il quadratino di stato che resta "
            "l'unico colore. Attenzione a dove vivono le regole: gli stati sono cinque e si "
            "conoscono da sempre, quindi stanno nel foglio; le persone no, e le loro regole CSS "
            "nascono a runtime in render_owners.py insieme al markup. Li' dentro c'e' una difesa da "
            "non smontare: nel selettore finisce un indice numerico e mai il nome, perche' un nome "
            "arriva dalla riga di comando e non deve poter comporre il foglio di stile della "
            "pagina.\n\n"
            "E' fatto quando: la tabella si legge meglio di adesso e le colonne dei numeri sono "
            "incolonnate davvero, i due filtri restano leggibili come due cose diverse, nessun nome "
            "finisce dentro un selettore, e la legenda non copre il grafo su una finestra stretta."))

    mutate.edit_node(
        g, "S09", blockedBy=["S03", "S05"],
        title="La pagina alleggerita e quella servita",
        artifacts=["payload/core/render_lite.py", "payload/core/serve.py", "tests/test_serve.py",
                   "tests/test_render_lite.py"],
        question=(
            "Le due porte d'ingresso che non sono il file aperto da disco.\n\n"
            "**La pagina alleggerita.** render_lite.py produce la versione che finisce su Telegram: "
            "niente canvas, niente interazione, deve reggere una foto fatta da un browser headless e "
            "una lettura su schermo piccolo. Allineala a Grafite senza portarci dentro il peso: i "
            "token e la tipografia si', i font incorporati vanno pesati (su Telegram ogni KB si "
            "vede), e la scelta va motivata nel commento in testa al modulo. Nota che dopo F02 "
            "condivide con render.py la stessa funzione di concatenazione, quindi eredita "
            "automaticamente i fogli: verifica che sia ancora quel che vuoi per una pagina che deve "
            "restare leggera.\n\n"
            "**La pagina servita.** 'atlas serve' inietta prima di </body> uno script che apre un "
            "EventSource su /events e ricarica la pagina quando graph.json cambia (serve.py, "
            "_RICARICA). E' una sostituzione testuale, e con i moduli JavaScript concatenati va "
            "verificata. Verifica anche il resto di cio' che distingue la pagina servita da quella "
            "aperta da disco: i bottoni delle Interactions, vivi solo dove c'e' un server dietro, e "
            "la colonna dei lucchetti remoti quando lock.remote e' attivo.\n\n"
            "E' fatto quando: la pagina leggera appartiene visibilmente alla stessa famiglia senza "
            "essere ingrassata, 'atlas serve' ricarica al cambio del grafo, i bottoni rispondono, e i "
            "due file di test passano."))

    # ============================================================ ramo V: 6 -> 5
    mutate.edit_node(
        g, "V01", blockedBy=["Q02", "Q03"],
        title="I test tornano veri, e la pagina resta senza rete",
        artifacts=["tests/test_motore.py", "tests/test_autoconsistenza.py"],
        question=(
            "**I test esistenti.** Un restyling di questa portata rompe le asserzioni scritte sul "
            "markup vecchio. Le classi da guardare in tests/test_motore.py sono Artefatti, "
            "FrecceColorate, FigureDeiRami, Avanzamento. Ogni test va rimesso a dire la stessa cosa "
            "sulla struttura nuova, non cancellato perche' e' diventato rosso. Se un test presidiava "
            "qualcosa che non esiste piu', va tolto con la nota del perche' nel commit, non "
            "commentato.\n\n"
            "**L'autoconsistenza.** La promessa di Atlas e' un file che si apre da disco senza rete, "
            "e i font incorporati la mettono alla prova: da 200KB si passa a mezzo megabyte per "
            "dashboard, e ogni grafo ne ha una. Scrivi il test che lo presidia: nessun http:// o "
            "https:// nella pagina generata fuori dai link ai ticket, nessun @import remoto, e il "
            "peso sotto una soglia dichiarata. Se la soglia non regge, la strada e' incorporare solo "
            "il carattere display e lasciare gli altri due ai fallback di sistema, che era gia' una "
            "delle opzioni sul tavolo: la decisione va scritta, non presa in silenzio.\n\n"
            "E' fatto quando: la suite e' verde, nessun test e' sparito senza una ragione detta, il "
            "test nuovo fallisce se qualcuno reintroduce un @import di Google Fonts, e il peso di "
            "ogni dashboard di .atlas/graphs/ sta sotto la soglia."))

    # ============================================================ ricablaggi dei cancelli
    mutate.edit_node(g, "Q01", blockedBy=["F04", "F06", "G05"])
    mutate.edit_node(g, "Q02", blockedBy=["C05", "C12", "A05", "V03"])
    mutate.edit_node(g, "Q03", blockedBy=["S03", "S07", "S09"])
    mutate.edit_node(g, "V03", blockedBy=["C12", "A05", "C01"])
    mutate.edit_node(g, "V02", blockedBy=["A01", "C08"])
    mutate.edit_node(g, "Q04", blockedBy=["V01", "V02", "V03", "V04", "V06"])

    # ============================================================ i fusi spariscono
    morti = ("F07", "F05", "C00", "C03", "C04", "C06", "C07", "C11",
             "A02", "A04", "A06", "S02", "S04", "S06", "S08", "S10", "V05")
    # Sganciare prima, rimuovere poi: fra i morti ce ne sono che si bloccano a vicenda
    # (C03 blocca C04), e remove_node rifiuta finche' qualcuno dipende dal nodo.
    for morto in morti:
        mutate.edit_node(g, morto, blockedBy=[])
    for morto in morti:
        mutate.remove_node(g, morto)

    mutate.note_add(g, "Condensazione: i 51 nodi erano dimensionati su un agente piccolo, e la catena "
                       "Canvas era spezzata in undici passi solo perche' due agenti non potevano "
                       "toccare canvas.js insieme. Diciassette nodi fusi nei loro vicini di ramo; "
                       "restano i quattro cancelli e la regola che due nodi prendibili insieme non "
                       "condividono un sorgente.")
