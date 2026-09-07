"""Secondo giro: il parallelismo verificato a macchina, e i cancelli resi automatici.

L'analisi delle coppie lavorabili insieme ha trovato quattordici collisioni, tutte
dentro il ramo Canvas: ogni suo nodo tocca canvas.js o canvas.css, quindi il
ventaglio era finto. Il ramo diventa una catena sola, e il parallelismo resta
quello vero fra rami diversi. In piu' tutti i nodi diventano AFK tranne l'ultimo,
e un cancello che nessun umano guarda ha bisogno di criteri che una macchina possa
davvero verificare.
"""
from core import mutate


def run(g):
    # --- il ramo Canvas e' una catena: i suoi nodi si contendono gli stessi due file
    for nodo, blocker in (("C05", "C04"), ("C07", "C06"), ("C09", "C07")):
        mutate.link(g, nodo, blocker)
    mutate.unlink(g, "C09", "C04")

    # --- S10 deve stare prima del cancello, o resta aperto mentre V01 tocca gli stessi test
    mutate.link(g, "Q03", "S10")

    # --- G05: senza un umano davanti non si pubblica niente, si prepara e basta
    mutate.edit_node(
        g, "G05", mode="AFK",
        title="Grafite pronta da pubblicare",
        question=(
            "Grafite e' una repo a se': Atlas la consuma riscaricandola, non copiandone i sorgenti a "
            "mano. Porta a casa il giro dentro la repo: bump di versione in package.json (oggi "
            "1.1.0), README che spiega quando si usa la variante offline e quando quella con "
            "l'@import, commit con messaggio in italiano.\n\n"
            "Il push non si fa. E' una repo pubblica su GitHub e nessun push parte senza un ok "
            "esplicito, che qui non c'e' perche' questo nodo lavora senza nessuno davanti. Ferma il "
            "lavoro al commit locale e scrivi nella risposta che resta da pushare.\n\n"
            "E' fatto quando: la repo e' committata, la versione e' salita, il README dice a un "
            "consumatore offline quale foglio prendere, e il push resta da fare."))

    # --- i tre cancelli intermedi diventano automatici: criteri che una macchina verifica
    mutate.edit_node(
        g, "Q01", mode="AFK", type="task",
        title="GATE 1: le fondamenta reggono",
        artifacts=[".atlas/graphs/260906-grafite-dashboard/notes/gate-1.md"],
        question=(
            "Cancello. Da qui in poi tre rami costruiscono in parallelo su queste fondamenta, e un "
            "difetto che passa adesso va rifatto tre volte. Non e' un nodo di esecuzione: qui si "
            "guarda l'insieme, e non si scrive codice se non per rimediare a cio' che si trova.\n\n"
            "Il giro, in ordine: python3 -m unittest discover -s tests deve essere verde; python3 "
            "build.py deve passare; 'atlas render --all' deve rigenerare tutte le dashboard di "
            "questa repo; ognuna va aperta con un browser headless e guardata davvero.\n\n"
            "Poi la lista, voce per voce, con l'esito scritto: i fogli spezzati non hanno perso "
            "regole (confronta l'insieme delle dichiarazioni prima e dopo, non il numero di righe); "
            "Grafite e' entrata come dipendenza a monte e i suoi due fogli portano in testa la riga "
            "che dice da dove vengono; i token non hanno doppioni; i cinque colori di stato dei nodi "
            "sono ancora quelli di prima, valore per valore; il tema scuro non ha lasciato rovine "
            "(nessun sorgente lo nomina piu'); la pagina non contiene nessun http:// o https:// "
            "fuori dai link ai ticket; il peso di una dashboard e' scritto nero su bianco.\n\n"
            "Scrivi l'esito in notes/gate-1.md. Un difetto piccolo si ripara qui; uno che cambia il "
            "disegno non si ripara di nascosto: si registra con 'atlas ask' e il cancello resta "
            "aperto. E' fatto quando ogni voce ha il suo esito e nessuna e' rossa."))

    mutate.edit_node(
        g, "Q02", mode="AFK", type="task",
        blockedBy=["C06", "C07", "C12", "A06", "V03"],
        title="GATE 2: il canvas e' quello di Nodavia",
        artifacts=[".atlas/graphs/260906-grafite-dashboard/notes/gate-2.md"],
        question=(
            "Cancello sulla parte piu' importante del lavoro. Il termine di paragone non e' un "
            "ricordo: sono le foto di Nodavia raccolte in C00 e quelle di Atlas prodotte in V03, da "
            "mettere una accanto all'altra.\n\n"
            "Confronta coppia per coppia: apertura rinquadrata, hover, nodo selezionato con le "
            "palline, arco di ritorno, minimap, pulsantiera. Per ogni coppia scrivi che cosa "
            "differisce, e se la differenza e' voluta (i colori di stato dei nodi, per esempio, che "
            "in Atlas ci sono e in Nodavia no) oppure e' un pezzo mancante.\n\n"
            "Poi i gesti, che una foto non mostra: rileggi il contratto scritto in C01 e verifica "
            "riga per riga che il codice faccia quel che dice, in particolare lo zoom ancorato al "
            "puntatore, i limiti 0.15 e 2.5, il fitView con padding 0.3 e maxZoom 0.85, il passo "
            "della griglia, la soglia sotto la quale un trascinamento resta un clic.\n\n"
            "Infine il prezzo: che un grafo da cinquanta nodi non faccia arrancare la pagina, che "
            "con reduced-motion nulla si muova, che nessun file abbia sfondato le 200 righe, che i "
            "test siano verdi. Scrivi l'esito in notes/gate-2.md. Quel che manca si registra con "
            "'atlas ask' invece di essere aggiustato di fretta."))

    mutate.edit_node(
        g, "Q03", mode="AFK", type="task",
        title="GATE 3: lo schermo e' Grafite dal bordo al centro",
        artifacts=[".atlas/graphs/260906-grafite-dashboard/notes/gate-3.md"],
        question=(
            "Cancello sul resto dello schermo: il canvas lo giudica il gate 2, qui si guarda tutto "
            "cio' che gli sta attorno.\n\n"
            "Rileggi le sette leggi in docs/grafite.md della repo Grafite e passale una per una "
            "sulla dashboard vera, usando le foto di V03: monocromo col colore solo dove e' "
            "segnale, tre voci tipografiche coi ruoli fissi, numeri protagonisti e animati, "
            "whitespace al posto dei bordi, motion soft, micro-segnali vivi, restraint. Poi cerca i "
            "'tells' che la spec dichiara: il pallino che respira accanto al wordmark, le label in "
            "maiuscoletto con tracking largo, le righe che scivolano allo hover, i bottoni che si "
            "sollevano.\n\n"
            "Cerca anche il difetto opposto, che e' quello che si vede meno: una regola di Grafite "
            "ricopiata dentro Atlas invece di essere consumata dal design system. Grep sui fogli di "
            "Atlas per valori che dovrebbero essere token, e per colori scritti a mano che non siano "
            "i cinque stati dei nodi.\n\n"
            "Scrivi l'esito in notes/gate-3.md, una riga per legge e una per tell. E' fatto quando "
            "nessuna voce e' rossa e nessun valore che appartiene a Grafite vive dentro Atlas."))

    mutate.note_add(g, "Revisione 2 (parallelismo): il ramo Canvas era un ventaglio finto, quattordici "
                       "coppie dei suoi nodi si contendevano canvas.js o canvas.css; ora e' una catena "
                       "sola e C08 resta l'unico suo nodo parallelo. Q03 attende anche S10. Tutti i "
                       "nodi sono AFK tranne Q04.")
