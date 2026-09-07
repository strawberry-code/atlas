"""Prima stesura: restyling Grafite della dashboard e canvas come Nodavia.

Ogni nodo dichiara in `artifacts` i file che possiede. E' quello il presidio del
parallelismo: due nodi prendibili nello stesso momento non condividono mai un file,
quindi due agenti possono lavorare insieme senza pestarsi i piedi.
"""
from core import mutate

GRAFITE = "~/cristiano/30-resources/33-design/grafite (repo strawberry-code/grafite-theme, v1.1.0)"
NODAVIA = "~/cristiano/10-projects/16-llm-apps/nodavia/web/src"


def run(g):
    mutate.add_branch(g, "G", "Grafite a monte", "#0a0a0a")
    mutate.add_branch(g, "F", "Fondamenta", "#4f46e5")
    mutate.add_branch(g, "C", "Canvas", "#0f766e")
    # 'A' esiste gia': 'atlas new' lo crea come percorso principale, e un grafo a rami
    # non ne ha uno. Si rinomina invece di aggiungerne un settimo che nessuno usa.
    g.data["branches"]["A"] = {"label": "Archi", "color": "#b45309"}
    mutate.add_branch(g, "S", "Superficie", "#7c3aed")
    mutate.add_branch(g, "V", "Consegna", "#16a34a")
    mutate.add_branch(g, "Q", "Cancelli", "#dc2626")

    # ---------------------------------------------------------------- ramo G
    # Vive in un'altra repo: qualunque suo nodo e' parallelizzabile con qualunque
    # nodo di Atlas, perche' non esiste un file che possano toccare entrambi.
    mutate.add_node(
        g, id="G01", branch="G", type="task", mode="AFK",
        title="Font Grafite in variante incorporabile",
        artifacts=["grafite:dist/grafite.fonts.inline.css", "grafite:tools/subset-fonts.mjs"],
        question=(
            f"Nella repo Grafite ({GRAFITE}) il foglio dist/grafite.css tira i tre caratteri da "
            "Google Fonts con un @import. La dashboard di Atlas e' un file solo che si apre da "
            "disco anche senza rete, quindi quell'@import li' non puo' arrivare.\n\n"
            "Produci in Grafite una variante incorporabile: subset latino di Inter (400/500/600), "
            "Space Grotesk (400/500/700) e JetBrains Mono (400/500), ciascuno come @font-face con "
            "src in data:font/woff2;base64. I woff2 di partenza stanno gia' nella copia di luglio in "
            "~/cristiano/10-projects/17-web-apps/grafite-design-system/fonts/. Lo script che genera "
            "il subset resta nella repo, perche' la variante dev'essere rigenerabile e non un blob "
            "committato una volta e mai piu' riproducibile.\n\n"
            "E' fatto quando: dist/grafite.fonts.inline.css esiste, non contiene nessun URL remoto, "
            "una pagina HTML di prova che linka solo quel foglio mostra i tre caratteri giusti, e il "
            "peso totale del foglio sta sotto i 400KB."))

    mutate.add_node(
        g, id="G03", branch="G", type="task", mode="AFK",
        title="Ricette Grafite per superfici dense",
        artifacts=["grafite:dist/grafite.css", "grafite:docs/grafite.md"],
        question=(
            f"Grafite ({GRAFITE}) nasce da dashboard arieggiate: padding 26px, card KPI, numeri a "
            "52px. La dashboard di Atlas e' densa, una sola schermata con tre colonne piene. "
            "Servono le ricette che oggi mancano, e vanno aggiunte in Grafite, non in Atlas.\n\n"
            "Aggiungi a dist/grafite.css il layer per le superfici dense: pannello laterale, riga di "
            "lista compatta che allo hover scivola a destra e rivela le azioni, chip di stato, badge "
            "di conteggio, titolo di sezione con eyebrow, scala tipografica ridotta coerente con i "
            "token. Niente valori sciolti: tutto passa dai token esistenti. Documenta le ricette "
            "nuove in docs/grafite.md, che e' la spec.\n\n"
            "E' fatto quando: le classi nuove compaiono in dist/grafite.css e nella styleguide, la "
            "regola 'un'applicazione non ridefinisce mai i token' resta vera, e docs/grafite.md "
            "descrive ogni ricetta aggiunta."))

    mutate.add_node(
        g, id="G04", branch="G", type="task", mode="AFK", blockedBy=["G03"],
        title="Ricette Grafite per il canvas di un grafo",
        artifacts=["grafite:dist/grafite.css", "grafite:docs/grafite.md"],
        question=(
            "Il canvas di Nodavia e' gia' vestito Grafite, ma quelle regole vivono nei suoi fogli "
            f"applicativi ({NODAVIA}/styles/editor.css) invece che nel design system. Vanno risalite "
            "a Grafite, cosi' Atlas le eredita invece di ricopiarle una seconda volta.\n\n"
            "Porta in dist/grafite.css: la card di nodo flottante (.rfnode e i suoi stati sel/off/"
            "beating), la griglia di sfondo a puntini, la pulsantiera dei comandi, la minimap "
            "monocroma, il tratto e il marker degli archi, le palline del pulse. Tutto "
            "layout-agnostico, come impone il README di Grafite: nessuna regola qui dentro decide "
            "dove sta una cosa nella pagina.\n\n"
            "E' fatto quando: le regole stanno in Grafite, Nodavia potrebbe consumarle al posto delle "
            "proprie senza cambiare aspetto, e docs/grafite.md le descrive."))

    mutate.add_node(
        g, id="G02", branch="G", type="task", mode="AFK", blockedBy=["G04"],
        title="Variante offline di grafite.css",
        artifacts=["grafite:dist/grafite.offline.css"],
        question=(
            "Deriva da dist/grafite.css la variante che Atlas puo' incorporare: stessa cosa senza "
            "l'@import di Google Fonts, con i token --sans/--display/--mono lasciati come punto di "
            "aggancio, esattamente come suggerisce il commento in testa al foglio.\n\n"
            "Va derivata, non riscritta a mano: una copia scollegata diverge alla prima modifica di "
            "grafite.css. Se serve un passo di generazione, mettilo nella repo accanto a quello dei "
            "font.\n\n"
            "E' fatto quando: dist/grafite.offline.css non contiene nessun URL remoto, e a parte "
            "l'@import e' identico a dist/grafite.css."))

    mutate.add_node(
        g, id="G05", branch="G", type="task", mode="HITL", blockedBy=["G01", "G02"],
        title="Grafite pubblicata e riscaricabile",
        artifacts=["grafite:package.json", "grafite:README.md"],
        question=(
            "Grafite e' una repo a se': Atlas la consuma riscaricandola, non copiandone i sorgenti a "
            "mano. Porta a casa il giro: bump di versione in package.json (oggi 1.1.0), README che "
            "spiega quando si usa la variante offline e quando quella con l'@import, commit con "
            "messaggio in italiano.\n\n"
            "Il push va chiesto: e' una repo pubblica su GitHub, e la regola di casa e' che nessun "
            "push parte senza un ok esplicito.\n\n"
            "E' fatto quando: la repo e' committata, la versione e' salita, e il README dice a un "
            "consumatore offline quale foglio prendere."))

    # ---------------------------------------------------------------- ramo F
    # Catena volutamente seriale: questi nodi si contendono render.py e i due
    # template monolitici. E' il prezzo di aprire il parallelismo per tutto il resto.
    mutate.add_node(
        g, id="F02", branch="F", type="task", mode="AFK",
        title="dashboard.css si spezza in fogli tematici",
        artifacts=["payload/templates/dashboard.css", "payload/templates/*.css", "payload/core/render.py"],
        question=(
            "payload/templates/dashboard.css e' un foglio unico da 650 righe, e finche' resta tale "
            "due agenti non possono lavorare la dashboard nello stesso momento. Spezzalo, senza "
            "cambiare una sola dichiarazione, in: tokens.css (il :root e le due tavole), shell.css "
            "(topbar, colonna dei pannelli, pannello notifiche, griglia di pagina), canvas.css "
            "(mappa, viewport, nodi, legenda, comandi di zoom), edges.css (archi, porte, marker, "
            "hover), sheet.css (scheda del ticket e markdown), table.css (vista tabellare).\n\n"
            "render.py li concatena nell'ordine dichiarato e li inietta inline come oggi. "
            "core/risorse.py li legge gia' per nome, quindi non va toccato.\n\n"
            "E' fatto quando: la dashboard generata prima e dopo e' identica byte per byte a meno "
            "dell'ordine delle regole, i test passano, e nessun foglio supera le 200 righe."))

    mutate.add_node(
        g, id="F03", branch="F", type="task", mode="AFK", blockedBy=["F02"],
        title="dashboard.js si spezza in moduli",
        artifacts=["payload/templates/dashboard.js", "payload/templates/*.js", "payload/core/render.py"],
        question=(
            "payload/templates/dashboard.js e' una IIFE sola da 710 righe che fa tema, vista "
            "mappa/tabella, notifiche, pairing Telegram, ordinamento della tabella, filtri di "
            "legenda, copia negli appunti, pan e zoom, scheda del ticket. Spezzala per argomento in "
            "canvas.js (viewport, pan, zoom, persistenza della vista) e chrome.js (tutto il resto), "
            "concatenati da render.py.\n\n"
            "Solo taglio, nessun cambio di comportamento. Attenzione ai nomi: oggi sono in una "
            "funzione sola e alcuni si ripetono fra blocchi diversi contando sullo scope di "
            "funzione, quindi ogni modulo va chiuso nella propria IIFE.\n\n"
            "E' fatto quando: la dashboard si comporta esattamente come prima, i test passano, e i "
            "moduli non si scambiano stato se non tramite il DOM."))

    mutate.add_node(
        g, id="F07", branch="F", type="task", mode="AFK", blockedBy=["F03"],
        title="Il markup della mappa esce da render.py",
        artifacts=["payload/core/render_canvas.py", "payload/core/render.py"],
        question=(
            "Oggi render.py assembla anche il contenitore della mappa, il viewport e i comandi di "
            "zoom. Se resta li', il ramo Canvas e il ramo Superficie si contendono render.py per "
            "tutto il progetto.\n\n"
            "Sposta in un modulo nuovo payload/core/render_canvas.py il markup della mappa: "
            "contenitore, viewport, comandi di zoom, suggerimento. Restano in render.py la topbar, "
            "la colonna dei pannelli, la legenda e l'assemblaggio della pagina. render_svg.py "
            "continua a disegnare i nodi e viene chiamato da render_canvas.\n\n"
            "E' fatto quando: la pagina generata e' identica, render_canvas.py sta sotto le 200 "
            "righe, e render.py non nomina piu' nessuna classe CSS del canvas."))

    mutate.add_node(
        g, id="F01", branch="F", type="task", mode="AFK", blockedBy=["G02", "F07"],
        title="Grafite entra nel payload",
        artifacts=["payload/templates/grafite.css", "payload/templates/grafite.fonts.css",
                   "payload/core/render.py"],
        question=(
            "Porta dentro Atlas i due fogli prodotti in Grafite (dist/grafite.offline.css e "
            "dist/grafite.fonts.inline.css) come risorse del payload, e falli concatenare da "
            "render.py in testa a tutto: prima i font, poi Grafite, poi i fogli di Atlas che "
            "consumano i suoi token.\n\n"
            "I due file arrivano dalla repo Grafite e non si modificano qui: in testa a ognuno va "
            "una riga che dice da dove vengono e che si rigenerano la', altrimenti al primo ritocco "
            "locale il design system smette di essere la fonte.\n\n"
            "E' fatto quando: la dashboard generata contiene i @font-face e i token Grafite, non "
            "chiede nessuna risorsa remota, e build.py continua a impacchettare (i due fogli sono "
            "neutri di lingua, quindi non gli serve la coppia .it./.en.)."))

    mutate.add_node(
        g, id="F04", branch="F", type="task", mode="AFK", blockedBy=["F01"],
        title="Il tema scuro esce di scena",
        artifacts=["payload/templates/tokens.css", "payload/core/render.py",
                   "payload/core/strings_cli.py", "tests/test_motore.py"],
        question=(
            "Grafite e' monotema chiaro per scelta dichiarata, ed e' la strada scelta anche per "
            "Atlas. Togli il tema scuro: il bottone in render.py con la sua icona sole/luna, il "
            "blocco @media (prefers-color-scheme: dark), la tavola :root[data-theme=dark], la "
            "memoria della preferenza nel JS, la stringa 'render.tema' e la classe di test "
            "TavolozzaScura in tests/test_motore.py.\n\n"
            "Toglilo davvero, non disattivarlo: una tavola scura che resta nel foglio senza piu' "
            "nessuno che la accenda e' codice morto che il prossimo lettore cerchera' di capire.\n\n"
            "E' fatto quando: nessun sorgente nomina piu' il tema scuro, la dashboard resta "
            "leggibile, e i test passano."))

    mutate.add_node(
        g, id="F05", branch="F", type="task", mode="AFK", blockedBy=["F04"],
        title="I token di Atlas si appoggiano a quelli di Grafite",
        artifacts=["payload/templates/tokens.css", "payload/core/theme.py"],
        question=(
            "tokens.css ha oggi una tavola sua (--ink, --muted, --faint, --border, --pane, --accent, "
            "--code-bg e i cinque blocchi --st-*). Grafite porta la sua (--ink, --bg, --bg-soft, "
            "--bg-softer, --muted, --faint, --line, piu' i semantici). Vanno fatte combaciare: i "
            "token Atlas diventano alias di quelli Grafite dove il significato coincide, e "
            "spariscono dove duplicano.\n\n"
            "Restano intatti i colori di stato dei nodi: --st-frontier, --st-claimed, --st-closed, "
            "--st-blocked, --st-out-of-scope con i loro -bg e -tx. Quella e' la semantica del grafo, "
            "non decorazione, ed e' la sola tinta che sopravvive al monocromo di Grafite. "
            "payload/core/theme.py, che tiene glifi, figure dei rami e anello, va riletto per "
            "coerenza ma la sua semantica non cambia.\n\n"
            "E' fatto quando: nessun colore e' dichiarato due volte, i cinque stati hanno i colori "
            "di oggi, e cambiando --ink in Grafite cambia l'inchiostro di tutta la dashboard."))

    mutate.add_node(
        g, id="F06", branch="F", type="task", mode="AFK", blockedBy=["F01"],
        title="La catena di build regge i template nuovi",
        artifacts=["build.py", "tests/test_build_template.py"],
        question=(
            "build.py copia payload/templates/ dentro il package e pretende che ogni template con "
            "marcatore .it. abbia il gemello .en.. I fogli nuovi sono neutri di lingua e non devono "
            "inciampare in quel controllo, ma nessuno oggi verifica che un foglio citato da render.py "
            "esista davvero nel pacchetto: un file dimenticato in staging si scopre solo aprendo la "
            "dashboard dell'eseguibile compilato.\n\n"
            "Aggiungi il test che, sul pacchetto costruito, ogni risorsa che render.py concatena sia "
            "leggibile via importlib.resources.\n\n"
            "E' fatto quando: python3 build.py passa, il test nuovo fallisce se si toglie un foglio "
            "dallo staging, e python3 -m unittest discover -s tests e' verde."))

    # ---------------------------------------------------------------- cancello 1
    mutate.add_node(
        g, id="Q01", branch="Q", type="grilling", mode="HITL",
        blockedBy=["F05", "F06", "G05"],
        title="GATE 1: le fondamenta reggono",
        question=(
            "Cancello da lavorare con un modello forte, non con un agente di esecuzione: qui si "
            "guarda l'insieme, non un file.\n\n"
            "Da qui in poi tre rami costruiscono in parallelo sopra queste fondamenta, e un difetto "
            "che passa adesso va rifatto tre volte. Verifica: i fogli spezzati non hanno perso "
            "regole per strada, Grafite e' entrata come dipendenza a monte e non come copia, i token "
            "combaciano senza doppioni, i colori di stato dei nodi sono quelli di prima, il tema "
            "scuro e' sparito senza lasciare rovine, la pagina non chiede niente alla rete, il peso "
            "del file generato e' accettabile.\n\n"
            "Guarda la dashboard vera, non solo il diff. E' fatto quando puoi dire che i tre rami "
            "possono partire senza rischiare di riscrivere la base."))

    # ---------------------------------------------------------------- ramo C
    mutate.add_node(
        g, id="C01", branch="C", type="research", mode="AFK", blockedBy=["Q01"],
        title="Il contratto di comportamento del canvas di Nodavia",
        artifacts=[".atlas/graphs/260906-grafite-dashboard/notes/canvas-nodavia.md"],
        question=(
            f"Prima di riscrivere, misura. Leggi {NODAVIA}/editor/GraphCanvas.tsx e il sorgente di "
            "React Flow che sta in nodavia/node_modules/@xyflow/react, e scrivi il contratto esatto "
            "di quel canvas: come si trasforma il viewport, come si pana, come si zooma (verso il "
            "puntatore o verso il centro), zoom minimo e massimo, parametri del fitView (padding "
            ".3, maxZoom .85, durata 280ms), passo e colore della griglia, geometria e "
            "comportamento della minimap, cosa fanno i Controls, quali gesti hanno una scorciatoia "
            "da tastiera.\n\n"
            "Serve un documento che un agente possa eseguire senza riaprire Nodavia. Numeri "
            "veri presi dal codice, non ricordi: dove il valore e' un default di React Flow, "
            "scrivi anche da quale file viene.\n\n"
            "E' fatto quando il documento elenca ogni gesto con i suoi parametri, e chi legge sa "
            "cosa costruire senza altre domande."))

    mutate.add_node(
        g, id="C08", branch="C", type="task", mode="AFK", blockedBy=["Q01"],
        title="Layout a rank longest-path, come Nodavia",
        artifacts=["payload/core/layout_rank.py", "tests/test_layout_rank.py"],
        question=(
            f"Porta in Python il layout di {NODAVIA}/editor/layout.ts, che e' geometria pura e si "
            "puo' scrivere e provare senza toccare niente altro. Rango longest-path calcolato sulle "
            "componenti fortemente connesse (Tarjan), non profondita' BFS: e' quello che rende vera "
            "l'invariante 'un arco che risale e' sempre un ritorno', da cui dipende tutto il ramo "
            "Archi. I nodi di un rango si distribuiscono in orizzontale centrati, e chi non e' "
            "raggiungibile dalla radice scende sotto tutto il resto.\n\n"
            "Il modulo va scritto nuovo (payload/core/layout_rank.py) e non deve ancora sostituire "
            "layout() in render_svg.py: qui si costruisce e si prova la geometria, l'innesto arriva "
            "dopo. Vale la regola del progetto: nessuna ricorsione, stack esplicito.\n\n"
            "E' fatto quando: il modulo sta sotto le 200 righe, i test coprono catena, ventaglio, "
            "ciclo e frammento staccato, e su un grafo reale di .atlas/graphs/ i ranghi sono quelli "
            "che ci si aspetta."))

    mutate.add_node(
        g, id="C02", branch="C", type="task", mode="AFK", blockedBy=["C01"],
        title="La superficie trasformabile",
        artifacts=["payload/templates/canvas.js", "payload/core/render_canvas.py"],
        question=(
            "Sostituisci il viewport attuale con la superficie di React Flow: un contenitore che "
            "ritaglia, dentro un pannello che porta un solo transform translate(x,y) scale(k), e "
            "dentro ancora il livello degli archi (SVG) e quello dei nodi. Tutte le coordinate del "
            "grafo restano in spazio-grafo, la trasformazione e' una sola e vive sul pannello.\n\n"
            "Oggi il pan e lo zoom agiscono su misure CSS del wrapper e lo zoom non segue il "
            "puntatore. Qui si mette in piedi solo l'impianto: stato del viewport (x, y, k), "
            "applicazione del transform, funzioni di conversione fra coordinate schermo e "
            "coordinate grafo.\n\n"
            "E' fatto quando: la mappa si vede come prima, il transform e' uno solo, e la "
            "conversione fra i due sistemi di coordinate ha una prova che la esercita."))

    mutate.add_node(
        g, id="C03", branch="C", type="task", mode="AFK", blockedBy=["C02"],
        title="Pan e zoom con i gesti di Nodavia",
        artifacts=["payload/templates/canvas.js"],
        question=(
            "Sopra la superficie, i gesti: trascinamento del pannello con il puntatore, zoom a "
            "rotella ancorato al puntatore (il punto sotto il cursore non si muove), limiti di zoom "
            "0.15 e 2.5 come in Nodavia, doppio clic che rinquadra.\n\n"
            "Attenzione al trascinamento che parte da un nodo o da un arco: quello non deve panare "
            "la superficie. E il pan non deve selezionare testo, come gia' fa oggi la classe "
            "'trascina'.\n\n"
            "E' fatto quando: i gesti si comportano come quelli di Nodavia messi a fianco, e uno "
            "zoom seguito da un pan non accumula deriva."))

    mutate.add_node(
        g, id="C04", branch="C", type="task", mode="AFK", blockedBy=["C03"],
        title="La griglia di sfondo a puntini",
        artifacts=["payload/templates/canvas.css", "payload/templates/canvas.js"],
        question=(
            "Il Background di React Flow: puntini a passo 22px, colore #e8e8e7, che si spostano e si "
            "scalano insieme al viewport. E' quello che da' la percezione fisica del pan e dello "
            "zoom, e senza di lui la superficie sembra ferma anche mentre si muove.\n\n"
            "Si fa in CSS con un background a gradiente ripetuto, aggiornando background-size e "
            "background-position dal transform. Il colore va preso dai token Grafite, non "
            "scritto a mano.\n\n"
            "E' fatto quando: i puntini restano ancorati al grafo mentre si pana e si zooma, e a "
            "zoom molto basso non diventano una nebbia grigia."))

    mutate.add_node(
        g, id="C05", branch="C", type="task", mode="AFK", blockedBy=["C03"],
        title="Rinquadratura animata",
        artifacts=["payload/templates/canvas.js"],
        question=(
            "Il fitView di Nodavia: calcola il rettangolo che contiene tutti i nodi, sceglie la "
            "scala perche' ci stia con padding 0.3 e senza superare 0.85, e ci arriva animando in "
            "280ms con l'easing morbido di Grafite. Va chiamato all'apertura della pagina e da "
            "chiunque sposti i nodi d'ufficio.\n\n"
            "Ricorda il motivo per cui in Nodavia esiste FitOnKey: dopo un cambio di disposizione il "
            "grafo scivola fuori centro e sembra peggiorato anche quando la disposizione e' migliore.\n\n"
            "E' fatto quando: aprendo un grafo grande si vede tutto, aprendone uno piccolo non si "
            "vede ingigantito, e l'animazione rispetta prefers-reduced-motion."))

    mutate.add_node(
        g, id="C06", branch="C", type="task", mode="AFK", blockedBy=["C05"],
        title="La pulsantiera dei comandi",
        artifacts=["payload/templates/canvas.css", "payload/core/render_canvas.py"],
        question=(
            "I Controls di React Flow, vestiti Grafite: zoom avanti, zoom indietro, rinquadra, e il "
            "lucchetto che blocca l'interazione. Sostituiscono i due bottoni di zoom di oggi, che "
            "stanno in basso a destra.\n\n"
            "Stile dalle ricette Grafite prodotte in G04: bottoni che si sollevano di 1px allo "
            "hover e si comprimono al clic. Ogni bottone ha la sua aria-label, perche' sono icone "
            "senza testo.\n\n"
            "E' fatto quando: i quattro comandi funzionano, si raggiungono da tastiera, e "
            "somigliano a quelli di Nodavia messi a fianco."))

    mutate.add_node(
        g, id="C07", branch="C", type="task", mode="AFK", blockedBy=["C05"],
        title="La minimap",
        artifacts=["payload/templates/canvas.js", "payload/core/render_canvas.py"],
        question=(
            "La MiniMap di Nodavia: riquadro in basso a destra con la sagoma di tutti i nodi in "
            "monocromo, il rettangolo della vista corrente, maschera rgba(250,250,250,0.78), "
            "trascinabile e zoomabile.\n\n"
            "Con una differenza dichiarata: in Nodavia il colore del nodo dice il tipo, qui deve "
            "dire lo stato, con i colori --st-* di Atlas. Su un grafo da cinquanta nodi la minimap "
            "e' l'unico posto da cui si vede a colpo d'occhio dove sono i nodi prendibili.\n\n"
            "E' fatto quando: la minimap riflette il grafo, trascinarla muove la vista, e il "
            "rettangolo della vista resta coerente durante lo zoom."))

    mutate.add_node(
        g, id="C09", branch="C", type="task", mode="AFK", blockedBy=["C04", "C08"],
        title="Le card dei nodi in stile Grafite",
        artifacts=["payload/core/render_svg.py", "payload/templates/canvas.css"],
        question=(
            f"Rifai la card del nodo come quella di {NODAVIA}/editor/customNodes.tsx: carta bianca "
            "flottante, eyebrow in alto col tipo del nodo, id in Space Grotesk, pallino di stato a "
            "destra, corpo con il titolo, footer coi badge (modo, assegnatario, costo). Hover che "
            "solleva, selezione che si vede.\n\n"
            "Qui si innesta anche il layout di C08 al posto della disposizione per livelli di "
            "render_svg.py. Restano intatte due cose di Atlas: i colori di stato dei nodi e la "
            "figura del ramo di theme.py, che serve a chi non distingue i colori.\n\n"
            "E' fatto quando: una card di Atlas e una di Nodavia messe a fianco appartengono "
            "visibilmente allo stesso sistema, e i cinque stati restano distinguibili anche in scala "
            "di grigi."))

    mutate.add_node(
        g, id="C10", branch="C", type="task", mode="AFK", blockedBy=["C09"],
        title="Le card si trascinano",
        artifacts=["payload/templates/canvas.js"],
        question=(
            "Come in Nodavia: si afferra una card e la si sposta, gli archi la seguono in tempo "
            "reale. Il trascinamento parte dalla card e non deve panare la superficie, e deve "
            "funzionare a qualunque zoom (lo spostamento in spazio-grafo e' quello dello schermo "
            "diviso k).\n\n"
            "Qui si sposta soltanto: dove finisce quando si ricarica la pagina lo decide il nodo "
            "dopo. Un clic senza spostamento deve restare un clic e aprire la scheda del ticket, "
            "quindi serve una soglia in pixel sotto la quale il gesto non e' un trascinamento.\n\n"
            "E' fatto quando: si sposta una card e gli archi restano attaccati, e un clic secco "
            "apre ancora la scheda."))

    mutate.add_node(
        g, id="C11", branch="C", type="task", mode="AFK", blockedBy=["C10"],
        title="Le posizioni sopravvivono alla ricarica",
        artifacts=["payload/templates/canvas.js", "payload/core/render_canvas.py"],
        question=(
            "Una card spostata deve restare dove l'hanno messa. Dove si scrive quella posizione e' "
            "la domanda vera: graph.json e' il grafo condiviso fra macchine e si fonde con un merge "
            "driver, quindi le coordinate della finestra di qualcuno non ci appartengono.\n\n"
            "Decidi e implementa: posizioni per grafo e per macchina, fuori da graph.json (un file "
            "accanto, oppure lo storage locale del browser, che pero' non sopravvive a un cambio di "
            "macchina). E decidi cosa succede quando il grafo cambia sotto: un nodo nuovo che nessuno "
            "ha mai spostato prende la posizione calcolata, e un nodo sparito non deve lasciare "
            "spazzatura che cresce per sempre.\n\n"
            "E' fatto quando: si sposta, si ricarica, e la card e' li'; si aggiunge un nodo al grafo "
            "e appare al posto giusto senza scompaginare gli altri; c'e' un modo di tornare al "
            "layout automatico."))

    mutate.add_node(
        g, id="C12", branch="C", type="task", mode="AFK", blockedBy=["C11"],
        title="Il canvas da tastiera, e fermo per chi lo chiede",
        artifacts=["payload/templates/canvas.js", "payload/templates/canvas.css"],
        question=(
            "Il canvas non deve essere raggiungibile solo col mouse: frecce per panare, piu' e meno "
            "per lo zoom, tab che scorre i nodi in ordine di rango con un anello di focus visibile, "
            "invio che apre la scheda del ticket, escape che la chiude.\n\n"
            "E prefers-reduced-motion va onorato su tutto il canvas: niente rinquadratura animata, "
            "niente palline in movimento, niente respiri. Il foglio di oggi ha gia' quella regola in "
            "fondo, e va tenuta vera anche per il codice nuovo che anima da JavaScript, dove un "
            "@media non arriva.\n\n"
            "E' fatto quando: si naviga il grafo senza mouse, e con reduced-motion attivo nessun "
            "pixel si muove da solo."))

    # ---------------------------------------------------------------- ramo A
    mutate.add_node(
        g, id="A01", branch="A", type="task", mode="AFK", blockedBy=["Q01"],
        title="Geometria degli archi ortogonali",
        artifacts=["payload/core/edge_geometry.py", "tests/test_edge_geometry.py"],
        question=(
            "Gli archi di oggi sono bezier verticali. Nodavia usa lo smoothstep di React Flow, cioe' "
            "tratte ortogonali con angoli raccordati, per la ragione scritta in GraphCanvas.tsx: con "
            "ventagli larghi le bezier collassano in una treccia illeggibile, mentre le tratte "
            "ortogonali si fondono in un bus pulito.\n\n"
            f"Porta in Python la geometria: getSmoothStepPath di @xyflow/react e roundedPath di "
            f"{NODAVIA}/editor/loopPath.ts, con lo stesso raccordo (CORNER = 10). Modulo nuovo, "
            "geometria pura, nessun import da render_*.\n\n"
            "Il commento in testa a loopPath.ts dice la cosa da non dimenticare: un NaN qui non da' "
            "errore, fa sparire l'arco. I punti coincidenti vanno scartati prima di raccordare. E' "
            "fatto quando: i test coprono l'arco dritto, quello a gomito, i punti coincidenti e il "
            "raccordo piu' lungo del segmento."))

    mutate.add_node(
        g, id="A02", branch="A", type="task", mode="AFK", blockedBy=["A01"],
        title="Gli archi che risalgono prendono una corsia laterale",
        artifacts=["payload/core/edge_geometry.py", "tests/test_edge_geometry.py"],
        question=(
            f"Porta loopPath da {NODAVIA}/editor/loopPath.ts: un arco che risale esce dal fondo "
            "della sorgente, scavalca le card su una corsia verticale tutta sua (LANE 135, meta' del "
            "passo fra due colonne, cosi' cade fra due colonne e mai dentro una card) e rientra "
            "dall'alto nel bersaglio. La quota di rientro cresce con la lunghezza del giro, cosi' "
            "piu' ritorni che convergono sullo stesso nodo non corrono tutti sulla stessa riga.\n\n"
            "In Atlas un arco che risale ha un significato preciso: con il layout a rank di C08, "
            "blockedBy verso un nodo di rango uguale o maggiore vuol dire che qualcosa nel grafo e' "
            "storto, ed e' esattamente il caso che 'atlas doctor' segnala. Decidi come si disegna: "
            "corsia laterale come Nodavia, e in piu' il tratto che lo distingue da un arco sano.\n\n"
            "E' fatto quando: due nodi legati in entrambi i versi mostrano due archi distinti e non "
            "uno sopra l'altro, e i test coprono la scelta del lato della corsia."))

    mutate.add_node(
        g, id="A03", branch="A", type="task", mode="AFK", blockedBy=["A02", "C08"],
        title="Le porte di aggancio sulla nuova geometria",
        artifacts=["payload/core/render_edges.py"],
        question=(
            "render_edges._slots distribuisce oggi i punti di aggancio sul bordo di una card "
            "ordinandoli per la x del nodo collegato, cosi' due archi sullo stesso bordo non si "
            "sovrappongono. Quella logica resta buona, ma va rimessa in piedi sulla geometria "
            "ortogonale e sul layout a rank.\n\n"
            "Nodavia ha un solo handle per lato; Atlas distribuisce, e su un nodo che ne blocca sei "
            "e' meglio. Tieni la distribuzione, cambia solo il modo in cui il path parte e arriva.\n\n"
            "E' fatto quando: su un nodo con molti archi entranti nessuna coppia si sovrappone, e i "
            "cerchietti di aggancio cadono sul bordo della card, non dentro."))

    mutate.add_node(
        g, id="A04", branch="A", type="task", mode="AFK", blockedBy=["A03"],
        title="Tratto, marker e colori di stato degli archi",
        artifacts=["payload/templates/edges.css", "payload/core/render_edges.py"],
        question=(
            "Veste dell'arco: tratto sottile grigio Grafite, punta di freccia chiusa alla Nodavia "
            "(ArrowClosed, 18x18, #737373).\n\n"
            "Resta pero' la regola di Atlas che il grigio da solo cancellerebbe: ogni arco prende il "
            "colore dello stato del nodo da cui parte, cosi' le frecce entranti in un blocco dicono "
            "in che stato sono le sue dipendenze senza doverle cercare sulla mappa, e un blocco con "
            "tutte le frecce verdi e' un blocco pronto. Il bloccato tiene il grigio neutro, per non "
            "fare della mappa un cavo aggrovigliato. Le classi da-<stato> ci sono gia'.\n\n"
            "E' fatto quando: i colori di stato sopravvivono al monocromo di Grafite, la punta della "
            "freccia si vede a tutti gli zoom, e la mappa non sembra un arcobaleno."))

    mutate.add_node(
        g, id="A05", branch="A", type="task", mode="AFK", blockedBy=["A04", "C09"],
        title="Le palline che scorrono sugli archi",
        artifacts=["payload/templates/edges.js", "payload/templates/edges.css"],
        question=(
            f"Il pezzo piu' bello di Nodavia, in {NODAVIA}/editor/pulse.tsx: selezionando un nodo, "
            "sugli archi che lo toccano scorrono delle palline che dicono in che verso passa il "
            "dato.\n\n"
            "Copialo davvero, non a occhio. Il numero di palline e la durata del giro si ricavano "
            "dalla lunghezza vera del path (getTotalLength): un arco corto con otto palline e' una "
            "collana, uno lungo con due e' vuoto. L'andatura non e' uniforme: ogni pallina e' un "
            "animateMotion con calcMode spline e keySplines '0.55 0 0.45 1', cosi' la velocita' "
            "dipende dalla posizione lungo l'arco e non dal tempo, che e' esattamente l'effetto. Lo "
            "sfasamento iniziale e' negativo, perche' al primo fotogramma le palline sono gia' "
            "distribuite lungo l'arco invece di partire tutte insieme. Con reduced-motion restano i "
            "punti fermi sull'arco, che sono comunque il segnale.\n\n"
            "In Atlas il nodo selezionato e' quello di cui e' aperta la scheda. E' fatto quando: "
            "l'effetto e' indistinguibile da quello di Nodavia messo a fianco."))

    mutate.add_node(
        g, id="A06", branch="A", type="task", mode="AFK", blockedBy=["A05"],
        title="Messa a fuoco degli archi allo hover",
        artifacts=["payload/templates/edges.css"],
        question=(
            "La dashboard ha oggi un comportamento che Nodavia non ha e che va tenuto: passando il "
            "mouse su un nodo tutto il resto si spegne (opacity .3 sui nodi, .12 sugli archi) e "
            "resta acceso solo quel che riguarda quel nodo. Le regole per-nodo sono generate in "
            "render_edges.hover_css.\n\n"
            "Rimettilo in piedi sulla geometria nuova, e falla convivere con la selezione: hover e "
            "selezione sono due segnali diversi e non devono confondersi.\n\n"
            "E' fatto quando: lo hover mette a fuoco un nodo e i suoi archi, il filtro di stato "
            "della legenda continua a funzionare, e i due non si annullano a vicenda."))

    # ---------------------------------------------------------------- ramo S
    mutate.add_node(
        g, id="S05", branch="S", type="task", mode="AFK", blockedBy=["Q01"],
        title="La scheda del ticket in stile Grafite",
        artifacts=["payload/templates/sheet.css", "payload/core/render_sheet.py"],
        question=(
            "La scheda che si apre da destra: veste Grafite (ombra diffusa -24px 0 60px rgba(0,0,0,"
            ".10), entrata con l'easing morbido, chip di stato secondo le ricette nuove, titolo in "
            "display, meta in mono).\n\n"
            "Restano il comportamento e i dettagli che ci sono gia': il click-to-copy che conferma "
            "con una parola in ::after invece di sostituire il testo, l'anello che gira sui nodi in "
            "lavorazione, la figura del ramo.\n\n"
            "E' fatto quando: la scheda sembra uscita dalla stessa mano del canvas, e ogni "
            "interazione di oggi funziona ancora."))

    mutate.add_node(
        g, id="S07", branch="S", type="task", mode="AFK", blockedBy=["Q01"],
        title="La vista tabellare",
        artifacts=["payload/templates/table.css", "payload/core/render_table.py"],
        question=(
            "La tabella e' il posto dove Grafite ha piu' da dire: numeri in mono tabellare, "
            "intestazioni come eyebrow in maiuscoletto con tracking largo, righe che allo hover "
            "cambiano fondo e scivolano, divisori hairline invece di bordi.\n\n"
            "Restano l'ordinamento per colonna con il suo aria-sort, il click sulla riga che apre la "
            "scheda, e il troncamento a due righe dei titoli lunghi con il title nativo che dice il "
            "resto.\n\n"
            "E' fatto quando: la tabella si legge meglio di adesso, l'ordinamento funziona, e le "
            "colonne dei numeri sono incolonnate davvero."))

    mutate.add_node(
        g, id="S01", branch="S", type="task", mode="AFK", blockedBy=["Q01"],
        title="La topbar",
        artifacts=["payload/templates/shell.css", "payload/core/render.py"],
        question=(
            "L'intestazione con i firmatari di Grafite: wordmark in display con tracking largo e il "
            "pallino nero che respira accanto, eyebrow in maiuscoletto, i tre numeri di sintesi in "
            "mono tabellare grandi, con il count-up all'apertura.\n\n"
            "Il count-up e' una delle sette leggi di Grafite ('un dato che appare senza contare e' "
            "un'occasione persa'), e il ricettario vanilla sta nella repo Grafite. Resta il codice "
            "dello slug cliccabile che si copia negli appunti.\n\n"
            "E' fatto quando: aprendo la dashboard i numeri contano una volta e si fermano, e chi "
            "ha chiesto reduced-motion li vede gia' al valore finale."))

    mutate.add_node(
        g, id="S02", branch="S", type="task", mode="AFK", blockedBy=["S01"],
        title="La colonna dei pannelli",
        artifacts=["payload/templates/shell.css", "payload/core/render_panels.py"],
        question=(
            "I blocchi della colonna sinistra con le ricette dense prodotte in G03: titolo di "
            "sezione con eyebrow, righe di lista che allo hover scivolano a destra e rivelano il "
            "badge nascosto, divisori hairline, niente gradienti di fondo.\n\n"
            "Resta il legame con la mappa: passare il mouse su un blocco o su una sua voce accende "
            "sulla mappa i nodi corrispondenti, cliccare fissa il filtro. Quelle regole vivono in "
            "CSS con :has() e vanno riportate sulla struttura nuova.\n\n"
            "E' fatto quando: i pannelli sono Grafite, il legame col canvas funziona ancora, e il "
            "blocco di avviso sul grafo che non converge resta visibilmente un avviso."))

    mutate.add_node(
        g, id="S03", branch="S", type="task", mode="AFK", blockedBy=["S02"],
        title="Avanzamento e costo",
        artifacts=["payload/templates/shell.css", "payload/core/render_panels.py"],
        question=(
            "L'anello dell'avanzamento e il numero-eroe del costo sono i due punti dove Grafite dice "
            "'i numeri sono protagonisti'. Rivestili: percentuale in mono grande con tracking "
            "negativo e count-up, anello che si riempie una volta sola all'apertura e si ferma, "
            "corona di tacche in tinta neutra.\n\n"
            "La regola scritta in testa al foglio di oggi resta valida: il movimento e' ammesso "
            "quando accompagna un valore che si legge all'apertura, non come ciclo perpetuo.\n\n"
            "E' fatto quando: l'anello si riempie una volta, la percentuale conta insieme a lui, e "
            "il costo si legge da lontano."))

    mutate.add_node(
        g, id="S04", branch="S", type="task", mode="AFK", blockedBy=["S03"],
        title="Il pannello Notifiche",
        artifacts=["payload/templates/shell.css", "payload/core/render_notifiche.py"],
        question=(
            "Il pannello destro con le card delle Interactions: veste Grafite per le card, i badge "
            "di conteggio, i bottoni di azione, il pairing Telegram, il muto. I semantici di Grafite "
            "(--ok, --down, --warn) sono esattamente quello che serve qui, e vanno usati come "
            "segnale e non come decoro.\n\n"
            "Resta tutto il comportamento: pannello richiudibile, bottoni disabilitati quando la "
            "pagina e' aperta da file:// invece che da 'atlas serve', evidenziazione della card "
            "collegata a un nodo.\n\n"
            "E' fatto quando: le card sono Grafite, i tre stati si distinguono, e i test di "
            "test_render_notifiche.py passano."))

    mutate.add_node(
        g, id="S08", branch="S", type="task", mode="AFK", blockedBy=["S02"],
        title="La legenda che filtra",
        artifacts=["payload/templates/legend.css", "payload/core/render.py"],
        question=(
            "La legenda flottante sulla mappa e' anche il filtro per stato e per persona. Vestila "
            "coi chip Grafite: pill piccola, raggio 6px, tracking largo, il quadratino di stato che "
            "resta l'unico colore.\n\n"
            "Restano i due filtri distinti (stato e persona) che si attenuano a vicenda senza "
            "confondersi, e il fatto che lo hover mostra e il clic fissa.\n\n"
            "E' fatto quando: i chip sono Grafite, i due filtri restano leggibili come due cose "
            "diverse, e la legenda non copre il grafo su una finestra stretta."))

    mutate.add_node(
        g, id="S06", branch="S", type="task", mode="AFK", blockedBy=["S05"],
        title="Il markdown della scheda",
        artifacts=["payload/templates/sheet.css"],
        question=(
            "Il corpo del ticket e' l'unico posto della dashboard dove si legge davvero un testo "
            "lungo, ed e' li' che la tipografia di Grafite conta di piu': Inter per il corpo a 13.5-"
            "14px con interlinea 1.5-1.65, titoli in Space Grotesk, ogni path, hash e numero in "
            "JetBrains Mono, blocchi di codice su fondo --bg-soft.\n\n"
            "E' fatto quando: un ticket lungo si legge senza fatica, la gerarchia dei titoli si vede "
            "senza contare i pixel, e le liste con le caselle di spunta restano allineate."))

    mutate.add_node(
        g, id="S09", branch="S", type="task", mode="AFK", blockedBy=["S06"],
        title="La pagina alleggerita resta di famiglia",
        artifacts=["payload/core/render_lite.py"],
        question=(
            "render_lite.py produce la versione leggera che finisce su Telegram: niente canvas, "
            "niente interazione, deve reggere una foto fatta da un browser headless e una lettura su "
            "schermo piccolo.\n\n"
            "Allineala a Grafite senza portarci dentro il peso: i token e la tipografia si', i font "
            "incorporati vanno pesati (su Telegram ogni KB si vede), e la scelta va motivata nel "
            "commento in testa al modulo.\n\n"
            "E' fatto quando: la pagina leggera appartiene visibilmente alla stessa famiglia, i test "
            "di test_render_lite.py passano, e il peso non cresce oltre il ragionevole."))

    # ---------------------------------------------------------------- cancelli 2 e 3
    mutate.add_node(
        g, id="Q02", branch="Q", type="grilling", mode="HITL",
        blockedBy=["C06", "C07", "C12", "A06"],
        title="GATE 2: il canvas e' quello di Nodavia",
        question=(
            "Cancello da lavorare con un modello forte. Qui si giudica la parte che l'utente ha "
            "chiamato la piu' importante di tutto il lavoro.\n\n"
            "Apri Nodavia e Atlas una accanto all'altra e prova gli stessi gesti sugli stessi grafi: "
            "pan, zoom alla rotella, rinquadratura, minimap, trascinamento di una card, selezione di "
            "un nodo con le palline sugli archi. Chi conosce Nodavia deve ritrovare la stessa "
            "interfaccia, non una che le somiglia.\n\n"
            "Guarda anche cosa e' costato: che i colori di stato dei nodi siano ancora quelli, che "
            "un grafo da cinquanta nodi non faccia arrancare la pagina, che con reduced-motion tutto "
            "resti fermo, che nessun file abbia sfondato le 200 righe. E' fatto quando puoi dire, "
            "con le due finestre aperte, che sono la stessa cosa."))

    mutate.add_node(
        g, id="Q03", branch="Q", type="grilling", mode="HITL",
        blockedBy=["S04", "S07", "S08", "S09"],
        title="GATE 3: lo schermo e' Grafite dal bordo al centro",
        question=(
            "Cancello da lavorare con un modello forte. Il canvas lo giudica il gate 2, qui si "
            "giudica tutto il resto dello schermo.\n\n"
            "Rileggi le sette leggi in docs/grafite.md e passale sulla dashboard vera una per una: "
            "monocromo con il colore solo dove e' segnale, tre voci tipografiche coi ruoli fissi, "
            "numeri protagonisti e animati, whitespace al posto dei bordi, motion soft, micro-"
            "segnali vivi, restraint. Cerca i 'tells' dichiarati: il pallino che respira, le label "
            "in maiuscoletto con tracking largo, le righe che scivolano allo hover.\n\n"
            "E cerca il difetto opposto: dove il colore e' rimasto decorazione, dove una regola di "
            "Grafite e' stata ricopiata in Atlas invece di essere consumata dal design system. E' "
            "fatto quando lo schermo intero appartiene a una mano sola."))

    # ---------------------------------------------------------------- ramo V
    mutate.add_node(
        g, id="V02", branch="V", type="task", mode="AFK", blockedBy=["A02", "C08"],
        title="La geometria si prova senza aprire il browser",
        artifacts=["tests/test_edge_geometry.py", "tests/test_layout_rank.py"],
        question=(
            "Layout e geometria degli archi sono funzioni pure, e vanno provate come tali: e' "
            "l'unico modo di sapere che un arco non e' sparito. Il commento in testa a loopPath.ts "
            "lo dice: un NaN non da' errore, fa sparire l'arco dal canvas.\n\n"
            "Copri: ranghi su catena, ventaglio, ciclo e frammento staccato; path dritto, a gomito, "
            "coi punti coincidenti; corsia dei ritorni a destra e a sinistra; nessun NaN in nessun "
            "path generato dai grafi veri che stanno in .atlas/graphs/.\n\n"
            "E' fatto quando: i test girano con unittest della stdlib, senza browser e senza rete, e "
            "un arco che sparisce fa fallire una prova."))

    mutate.add_node(
        g, id="V01", branch="V", type="task", mode="AFK", blockedBy=["Q02", "Q03"],
        title="I test esistenti tornano veri",
        artifacts=["tests/test_motore.py", "tests/test_serve.py", "tests/test_render_lite.py",
                   "tests/test_render_notifiche.py"],
        question=(
            "Un restyling di questa portata rompe le asserzioni scritte sul markup vecchio. Le "
            "classi da guardare in tests/test_motore.py sono Artefatti, FrecceColorate, "
            "FigureDeiRami, Avanzamento; poi test_serve.py, test_render_lite.py, "
            "test_render_notifiche.py.\n\n"
            "Ogni test va rimesso a dire la stessa cosa sulla struttura nuova, non cancellato "
            "perche' e' diventato rosso. Se un test presidiava qualcosa che non esiste piu' (il tema "
            "scuro), va tolto con la nota del perche' nel commit, non commentato.\n\n"
            "E' fatto quando: python3 -m unittest discover -s tests e' verde, e nessun test e' "
            "sparito senza una ragione detta."))

    mutate.add_node(
        g, id="V03", branch="V", type="task", mode="AFK", blockedBy=["Q02", "Q03"],
        title="La prova visiva a fianco di Nodavia",
        artifacts=["tests/screenshot_dashboard.py"],
        question=(
            "Una dashboard si verifica guardandola. Fai le foto con un browser headless (lo stesso "
            "meccanismo di payload/core/view_capture.py, che cerca il primo browser installato e non "
            "scarica niente) su piu' grafi veri di .atlas/graphs/, e mettile a fianco di quelle di "
            "Nodavia.\n\n"
            "Due cose imparate e da non riscoprire: con reduced-motion attivo le animazioni si "
            "congelano e la foto e' inutile per giudicarle, e sotto i 500px di finestra il layout "
            "collassa e la foto non dice niente. Per la scheda serve un clic sintetico.\n\n"
            "E' fatto quando: ci sono foto di apertura, hover, selezione con le palline, scheda "
            "aperta e vista tabellare, e chi le guarda con quelle di Nodavia accanto non sa dire "
            "quale sistema abbia disegnato quale."))

    mutate.add_node(
        g, id="V04", branch="V", type="task", mode="AFK", blockedBy=["V01"],
        title="Documentazione e contratto in pari",
        artifacts=["README.md", "README.it.md", "payload/templates/contract.it.md",
                   "payload/templates/contract.en.md", "CLAUDE.md"],
        question=(
            "Il CLAUDE.md del progetto impone due allineamenti che nessun comando fa da solo. I due "
            "README, inglese e italiano, restano in pari col CLI e fra loro, e li presidia "
            "tests/test_readme.py. Il contratto (contract.it.md e contract.en.md) riflette ogni "
            "cambio nel modo di lavorare, e quello non lo presidia nessun test.\n\n"
            "Qui cambia la dashboard, quindi cambia quel che un agente vede quando la apre: gesti "
            "nuovi, tema scuro sparito, posizioni delle card. Aggiorna anche il CLAUDE.md di Atlas, "
            "dove la struttura dei template e' descritta come due file soli.\n\n"
            "E' fatto quando: test_readme.py passa, le due lingue dicono le stesse cose, e nessun "
            "documento descrive ancora la dashboard di prima."))

    mutate.add_node(
        g, id="V05", branch="V", type="task", mode="AFK", blockedBy=["V01"],
        title="Nessuna risorsa remota, peso sotto controllo",
        artifacts=["tests/test_autoconsistenza.py"],
        question=(
            "La promessa di Atlas e' un file che si apre da disco senza rete. I font incorporati la "
            "mettono alla prova: da 200KB si passa a mezzo megabyte per dashboard, e ogni grafo ne "
            "ha una.\n\n"
            "Scrivi il test che lo presidia davvero: nessun http:// o https:// nella pagina "
            "generata fuori dai link ai ticket, nessun @import remoto, e il peso sotto una soglia "
            "dichiarata. Se la soglia non regge, la strada e' incorporare solo il carattere display "
            "e lasciare gli altri due ai fallback di sistema, che era gia' una delle opzioni sul "
            "tavolo. La decisione va scritta, non presa in silenzio.\n\n"
            "E' fatto quando: il test fallisce se qualcuno reintroduce un @import di Google Fonts, e "
            "il peso di ogni dashboard di .atlas/graphs/ sta sotto la soglia."))

    # ---------------------------------------------------------------- cancello finale
    mutate.add_node(
        g, id="Q04", branch="Q", type="grilling", mode="HITL",
        blockedBy=["V02", "V03", "V04", "V05"],
        title="GATE 4: la destinazione e' raggiunta",
        question=(
            "Cancello finale, da lavorare con un modello forte. Qui si verifica la destinazione "
            "dichiarata, non i singoli nodi.\n\n"
            "Il giro completo: python3 -m unittest discover -s tests verde, python3 build.py seguito "
            "da python3 tests/e2e.py verde, 'atlas render --all' su tutti i grafi di questa repo, "
            "ognuno aperto e guardato. La dashboard servita da 'atlas serve' si comporta come quella "
            "aperta da file, con i bottoni delle Interactions vivi solo dove c'e' il server. Nessuna "
            "regressione su Windows nei rami che il codice sceglie con sys.platform.\n\n"
            "Poi le domande che restano: cosa e' rimasto indietro rispetto a Nodavia e perche', cosa "
            "abbiamo aggiunto che Nodavia non ha, cosa e' peggiorato rispetto alla dashboard di "
            "prima. E' fatto quando il lavoro si puo' rilasciare, e quel che manca e' scritto invece "
            "che ricordato."))

    # ---------------------------------------------------------------- note e nebbia
    mutate.note_add(g, "Parallelismo: ogni nodo dichiara in 'artifacts' i file che possiede. "
                       "Prima di prendere un nodo si guarda cosa dichiarano i nodi gia' rivendicati: "
                       "due nodi che condividono un file non si lavorano insieme, anche se la "
                       "frontiera li mostra entrambi prendibili.")
    mutate.note_add(g, "I quattro nodi Q sono cancelli da lavorare con un modello forte, non con un "
                       "agente di esecuzione: guardano l'insieme e la dashboard vera, non un diff.")
    mutate.note_add(g, "Grafite e' una dipendenza a monte, non una copia: qualunque componente "
                       "grafica manchi si aggiunge nella repo grafite-theme e si riscarica da li'. "
                       "Un ritocco fatto dentro Atlas e' un difetto, non una scorciatoia.")
    mutate.note_add(g, "Fonti da tenere aperte: " + GRAFITE + " per lo stile, " + NODAVIA +
                       " per il canvas (GraphCanvas.tsx, customNodes.tsx, FlowStepEdge.tsx, "
                       "LoopEdge.tsx, loopPath.ts, pulse.tsx, layout.ts, styles/editor.css).")

    mutate.fog_add(g, "se un giorno Nodavia e Atlas diventano una piattaforma sola, quanto di questo "
                      "canvas diventa codice condiviso e chi lo possiede")
    mutate.fog_add(g, "se le posizioni delle card debbano viaggiare fra macchine come il grafo, "
                      "oppure restare locali per sempre")
    mutate.fog_add(g, "se la dashboard debba diventare interattiva sul grafo (prendere e chiudere "
                      "un nodo dal canvas, come Nodavia fa col suo editor) o restare una vista")
