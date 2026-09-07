"""Primo giro di revisione: i buchi di copertura trovati rileggendo i sorgenti.

Quattro cose che il disegno non nominava e che esistono davvero: le regole CSS
generate da render_owners.py, lo script che serve.py inietta nella pagina viva,
i tre breakpoint del layout, e le foto di riferimento di Nodavia senza le quali
un cancello automatico non ha un termine di paragone.
"""
from core import mutate

NODAVIA = "~/cristiano/10-projects/16-llm-apps/nodavia"


def run(g):
    # --- foto di riferimento: senza queste, un cancello automatico giudica a memoria
    mutate.add_node(
        g, id="C00", branch="C", type="task", mode="AFK", blockedBy=["Q01"],
        title="Le foto di riferimento di Nodavia",
        artifacts=[".atlas/graphs/260906-grafite-dashboard/notes/nodavia/"],
        question=(
            "I cancelli di questo grafo giudicano la somiglianza con Nodavia, e per farlo senza un "
            "umano davanti servono le foto di quel canvas, prese adesso e messe da parte.\n\n"
            f"Avvia Nodavia ({NODAVIA}, node_modules gia' installato: npm run dev dentro web/) e "
            "cattura con un browser headless il canvas di piu' grafi di server/graphs: vista "
            "iniziale rinquadrata, un nodo selezionato con le palline sugli archi, un grafo con un "
            "arco di ritorno, la minimap, la pulsantiera. Salva le immagini nelle note del grafo "
            "con un indice che dice cosa mostra ognuna.\n\n"
            "Il server di sviluppo e' un comando lungo: lanciato in background non va aspettato "
            "fermandosi, e va spento quando le foto ci sono. Se Nodavia non parte, non insistere "
            "oltre un tentativo ragionevole: annota il motivo e ripiega sui suoi fogli di stile, "
            "che restano il riferimento leggibile.\n\n"
            "E' fatto quando: le immagini esistono con il loro indice, oppure e' scritto perche' non "
            "esistono e cosa si usa al loro posto."))

    # --- la pagina viva: serve.py inietta uno <script> che la struttura nuova non deve rompere
    mutate.add_node(
        g, id="S10", branch="S", type="task", mode="AFK", blockedBy=["S04"],
        title="La pagina servita resta viva",
        artifacts=["payload/core/serve.py", "tests/test_serve.py"],
        question=(
            "'atlas serve' non rigenera solo la pagina: le inietta prima di </body> uno script che "
            "apre un EventSource su /events e la ricarica quando graph.json cambia (serve.py, "
            "_RICARICA). Con i moduli JavaScript concatenati quella iniezione va verificata, perche' "
            "e' una sostituzione testuale su una stringa che ora ha una forma diversa.\n\n"
            "Verifica anche il resto di cio' che distingue la pagina servita da quella aperta da "
            "disco: i bottoni del pannello Notifiche, vivi solo dove c'e' un server dietro, e la "
            "colonna dei lucchetti remoti quando lock.remote e' attivo.\n\n"
            "E' fatto quando: 'atlas serve' ricarica la pagina al cambio del grafo, i bottoni delle "
            "Interactions rispondono, e test_serve.py e' verde."))

    # --- le regole per persona nascono in render_owners.py, non nel foglio statico
    mutate.edit_node(
        g, "S08",
        artifacts=["payload/templates/legend.css", "payload/core/render.py",
                   "payload/core/render_owners.py"],
        question=(
            "La legenda flottante sulla mappa e' anche il filtro per stato e per persona. Vestila "
            "coi chip Grafite: pill piccola, raggio 6px, tracking largo, il quadratino di stato che "
            "resta l'unico colore.\n\n"
            "Attenzione a dove vivono le regole. Gli stati sono cinque e si conoscono da sempre, "
            "quindi stanno nel foglio; le persone no, e le loro regole CSS nascono a runtime in "
            "render_owners.py insieme al markup. Li' dentro c'e' anche una difesa da non smontare: "
            "nel selettore non finisce mai il nome della persona ma un indice numerico, perche' un "
            "nome arriva dalla riga di comando e non deve poter comporre il foglio di stile della "
            "pagina.\n\n"
            "Restano i due filtri distinti che si attenuano a vicenda senza confondersi, e il fatto "
            "che lo hover mostra e il clic fissa. E' fatto quando: i chip sono Grafite, i due filtri "
            "restano leggibili come due cose diverse, e nessun nome finisce dentro un selettore."))

    # --- la selezione del nodo e' il presupposto delle palline: va detto dove nasce
    mutate.edit_node(
        g, "C09",
        question=(
            "Rifai la card del nodo come quella di nodavia/web/src/editor/customNodes.tsx: carta "
            "bianca flottante, eyebrow in alto col tipo del nodo, id in Space Grotesk, pallino di "
            "stato a destra, corpo con il titolo, footer coi badge (modo, assegnatario, costo). "
            "Hover che solleva, selezione che si vede.\n\n"
            "La selezione nasce qui, e non e' un dettaglio estetico: e' il presupposto delle palline "
            "sugli archi (A05) e della navigazione da tastiera (C12). Un nodo alla volta e' "
            "selezionato, la classe sta sulla card, e chi la legge non deve sapere come ci e' "
            "finita. Il clic che apre la scheda del ticket seleziona anche.\n\n"
            "Qui si innesta il layout di C08 al posto della disposizione per livelli di "
            "render_svg.py. Restano intatte due cose di Atlas: i colori di stato dei nodi e la "
            "figura del ramo di theme.py, che serve a chi non distingue i colori.\n\n"
            "E' fatto quando: una card di Atlas e una di Nodavia messe a fianco appartengono "
            "visibilmente allo stesso sistema, i cinque stati restano distinguibili anche in scala "
            "di grigi, e la selezione e' leggibile dal DOM da chi verra' dopo."))

    # --- F07 nomina esattamente cosa resta a render.py, altrimenti due rami se lo contendono
    mutate.edit_node(
        g, "F07",
        question=(
            "Oggi render.py assembla anche il contenitore della mappa, il viewport e i comandi di "
            "zoom. Se resta li', il ramo Canvas e il ramo Superficie si contendono render.py per "
            "tutto il progetto.\n\n"
            "Sposta in un modulo nuovo payload/core/render_canvas.py: contenitore della mappa, "
            "viewport, comandi di zoom (i tre bottoni +, meno e rinquadra). Restano a render.py la "
            "topbar coi suoi due bottoni (tema e vista mappa/tabella), la colonna dei pannelli, la "
            "legenda, il suggerimento sotto la mappa e l'assemblaggio della pagina. render_svg.py "
            "continua a disegnare i nodi e viene chiamato da render_canvas.\n\n"
            "Il confine e' la regola di proprieta' dei file per tutto il resto del grafo, quindi "
            "scrivilo nel docstring del modulo nuovo. E' fatto quando: la pagina generata e' "
            "identica, render_canvas.py sta sotto le 200 righe, e render.py non nomina piu' nessuna "
            "classe CSS del canvas."))

    # --- V02 scriveva negli stessi file di prova di A01, A02 e C08: due nodi, un file solo
    mutate.edit_node(
        g, "V02",
        title="La geometria regge i grafi veri",
        artifacts=["tests/test_geometria_grafi_veri.py"],
        question=(
            "A01, A02 e C08 provano ognuno la propria geometria su casi costruiti a mano. Manca la "
            "prova che tiene insieme le due cose sui grafi che esistono davvero, ed e' un file "
            "diverso apposta: quelli sono gia' scritti da altri nodi, e due agenti sullo stesso file "
            "di prova si sovrascrivono a vicenda.\n\n"
            "Su ogni graph.json di .atlas/graphs/, che sono grafi veri da sedici a quarantotto nodi: "
            "nessun path contiene NaN, nessun nodo finisce fuori dal riquadro calcolato, nessuna "
            "coppia di card si sovrappone, ogni arco che risale e' davvero un ritorno e non un arco "
            "in avanti mal disposto. Il commento in testa a loopPath.ts dice perche' serve: un NaN "
            "non da' errore, fa sparire l'arco dal canvas.\n\n"
            "E' fatto quando: la prova gira con unittest della stdlib, senza browser e senza rete, e "
            "un arco che sparisce la fa fallire."))

    # --- le foto servono ai cancelli, quindi si fanno prima dei cancelli
    mutate.unlink(g, "V03", "Q02")
    mutate.unlink(g, "V03", "Q03")
    mutate.link(g, "V03", "C12")
    mutate.link(g, "V03", "A06")
    mutate.link(g, "V03", "C00")
    mutate.edit_node(
        g, "V03",
        title="Le foto della dashboard, a fianco di quelle di Nodavia",
        question=(
            "Una dashboard si verifica guardandola, e i cancelli automatici hanno bisogno di "
            "guardarla senza un umano davanti. Costruisci lo strumento e usalo: foto con un browser "
            "headless (lo stesso meccanismo di payload/core/view_capture.py, che cerca il primo "
            "browser installato e non scarica niente) su piu' grafi veri di .atlas/graphs/, "
            "affiancate a quelle di Nodavia raccolte in C00.\n\n"
            "Due cose imparate e da non riscoprire: con reduced-motion attivo le animazioni si "
            "congelano e la foto non dice niente su di loro, e sotto i 500px di finestra il layout "
            "collassa. Per la scheda e per la selezione servono clic sintetici.\n\n"
            "Servono le foto di: apertura rinquadrata, hover su un nodo, nodo selezionato con le "
            "palline, arco di ritorno, scheda aperta, vista tabellare, minimap e pulsantiera. E' "
            "fatto quando: lo strumento si rilancia con un comando solo, e le coppie di immagini "
            "sono pronte da mettere a confronto."))

    # --- il responsive tocca i fogli di due rami: si fa quando quei rami hanno finito
    mutate.add_node(
        g, id="V06", branch="V", type="task", mode="AFK", blockedBy=["Q02", "Q03"],
        title="Il layout su una finestra stretta",
        artifacts=["payload/templates/shell.css", "payload/templates/canvas.css",
                   "payload/templates/legend.css"],
        question=(
            "Il foglio di oggi ha tre punti di rottura: sotto 880px le tre colonne si impilano, "
            "sotto 720px i numeri di sintesi spariscono. Il canvas nuovo porta roba che prima non "
            "c'era, cioe' minimap, pulsantiera e griglia, e su una finestra stretta quella roba "
            "copre il grafo invece di aiutare.\n\n"
            "Questo nodo tocca fogli di due rami diversi, ed e' per questo che arriva dopo i due "
            "cancelli: prima ci sarebbero stati due agenti sullo stesso file.\n\n"
            "Decidi cosa sparisce e cosa resta a ogni misura, e provalo davvero ridimensionando. E' "
            "fatto quando: a 1440, 1024, 880 e 600px di larghezza la dashboard resta usabile, e "
            "niente di essenziale finisce coperto."))

    mutate.link(g, "Q04", "V06")

    mutate.note_add(g, "Revisione 1 (copertura): aggiunti C00 (foto di Nodavia), S10 (la pagina "
                       "servita), V06 (finestra stretta); V02 spostato su un file di prova suo; "
                       "V03 anticipato prima dei cancelli, che senza foto non avrebbero un termine "
                       "di paragone.")
