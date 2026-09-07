"""Due difetti visti dall'utente usando la dashboard vera.

Il primo e' un bug: il pan seleziona il testo appena il puntatore esce dalla mappa.
Il secondo e' un cambio di disegno chiesto dall'utente: la scheda del ticket smette
di essere una modale che appare e scompare da sola, e diventa la seconda vista del
pannello di destra, comandata a mano.
"""
from core import mutate


def run(g):
    mutate.add_node(
        g, id="C13", branch="C", type="task", mode="AFK", blockedBy=["V06"],
        title="Il pan non seleziona il testo",
        artifacts=["payload/templates/canvas.js", "payload/templates/canvas.css"],
        question=(
            "Difetto visto usando la dashboard: trascinando la mappa con la mano chiusa, se il "
            "puntatore passa sopra del testo (le etichette della legenda, la colonna dei pannelli) "
            "parte la selezione del testo, e restano righe evidenziate in giro.\n\n"
            "La causa e' che `user-select:none` vive su `.viewport.trascina` (canvas.css riga 16), "
            "cioe' solo dentro la mappa. Ma il pan usa `setPointerCapture`, quindi il puntatore "
            "continua a comandare il gesto anche quando esce dal viewport e passa sopra il resto "
            "della pagina, dove la selezione e' di nuovo permessa.\n\n"
            "Sposta la soppressione della selezione su tutto il documento per la durata del gesto "
            "(la classe sul body, non sul viewport), e togli la selezione gia' in corso quando il "
            "trascinamento comincia. Attenzione a non lasciarla incollata: se il gesto finisce fuori "
            "dalla finestra o il puntatore viene perso, la classe va tolta lo stesso, altrimenti la "
            "pagina resta non selezionabile per sempre. Verifica anche il caso del trascinamento "
            "della minimap, che ha lo stesso schema.\n\n"
            "La stessa classe la legge `sheet.js` per non aprire la scheda dopo un pan: se cambi "
            "dove vive, controlla chi la legge (grep su 'trascina') e tienili allineati.\n\n"
            "E' fatto quando: si pana attraversando legenda, pannelli e topbar senza che si "
            "evidenzi niente, e dopo il gesto il testo torna selezionabile normalmente."))

    mutate.add_node(
        g, id="S11", branch="S", type="task", mode="AFK", blockedBy=["V06"],
        title="Il pannello destro ospita due viste: Notifiche e Nodo",
        artifacts=["payload/core/render.py", "payload/core/render_sheet.py",
                   "payload/core/render_notifiche.py", "payload/templates/shell.css",
                   "payload/templates/sheet.css", "payload/templates/notifiche.css"],
        question=(
            "Cambio di disegno chiesto dall'utente. Oggi ci sono due cose separate: il pannello "
            "Notifiche, che e' la terza colonna della griglia (shell.css, `minmax(230px,296px)`, "
            "richiudibile a 46px), e la scheda del ticket, che e' una modale `position:fixed` larga "
            "480px con un velo sfocato sopra la pagina (sheet.css).\n\n"
            "Devono diventare **un pannello solo con due viste**: Notifiche e Dettaglio del nodo. "
            "Stesso contenitore, stessa larghezza, stessa apertura e chiusura; cambia solo quale "
            "delle due si sta guardando.\n\n"
            "Questo nodo fa la struttura e la veste: il contenitore, il selettore fra le due viste, "
            "la migrazione del contenuto della scheda dentro la colonna, e la sparizione del velo "
            "sfocato e di tutto cio' che faceva della scheda una modale. Il comportamento (quando si "
            "apre, cosa la chiude, il bottone) e' del nodo dopo, S12: qui basta che le due viste "
            "esistano e si vedano.\n\n"
            "Decidi tu la larghezza del pannello unico: oggi le due misure sono diverse (296 contro "
            "480) e il contenuto della scheda e' quello che ha piu' bisogno di spazio, perche' ci si "
            "legge un ticket lungo. Motiva la scelta nella Risposta.\n\n"
            "Cosa non perdere: tutto il contenuto della scheda (chip di stato, figura del ramo, "
            "anello dei nodi in lavorazione, click-to-copy che conferma in ::after, markdown con la "
            "tipografia Grafite, artefatti, link al ticket) e tutto quello delle Notifiche (card, "
            "azioni con la gerarchia primario/ghost appena introdotta, pairing Telegram, muto, "
            "badge di conteggio).\n\n"
            "E' fatto quando: il pannello mostra l'una o l'altra vista senza velo e senza modale, "
            "nessun contenuto delle due e' andato perso, e i fogli restano sotto le 200 righe."))

    mutate.add_node(
        g, id="S12", branch="S", type="task", mode="AFK", blockedBy=["S11"],
        title="Il pannello si comanda a mano, e non sparisce da solo",
        artifacts=["payload/templates/sheet.js", "payload/templates/notifiche.js",
                   "payload/templates/chrome.js"],
        question=(
            "Il comportamento del pannello unico, come lo ha chiesto l'utente.\n\n"
            "- **Un bottone lo apre e lo chiude**, e sta nella stessa area del pannello, dove oggi "
            "c'e' quello delle Notifiche.\n"
            "- **Cliccando un nodo**: se il pannello e' chiuso si apre sul Dettaglio di quel nodo; se "
            "e' gia' aperto passa a mostrare quel nodo.\n"
            "- **Cliccando altrove non si chiude piu' da solo.** Ne' il clic fuori, ne' il velo (che "
            "non esiste piu'), ne' niente altro: si chiude solo col bottone. Valuta se tenere Escape, "
            "che oggi chiude, e dillo nella Risposta.\n"
            "- Il pannello **ricorda** se era aperto e su quale vista, come gia' fa oggi lo stato "
            "richiuso delle Notifiche.\n\n"
            "Sparisce quindi tutta la logica di modale: `body.sheet-open` come stato globale, il "
            "listener sul velo, la chiusura al clic esterno. Attenzione a `sheet.js` riga 154, che "
            "legge la classe `trascina` per non aprire la scheda subito dopo un pan: quel presidio "
            "serve ancora, e il nodo C13 potrebbe averla spostata sul body. Controlla dove vive prima "
            "di fidarti.\n\n"
            "La navigazione da tastiera esiste gia' (keyboard.js): Invio apre il dettaglio del nodo a "
            "fuoco, Escape chiude. Tienila coerente con la decisione su Escape.\n\n"
            "E' fatto quando: il pannello si apre e si chiude solo quando lo chiede chi guarda, "
            "cliccare un nodo mostra il suo dettaglio senza far sparire niente, e nessun clic "
            "distratto fa scomparire quel che si stava leggendo."))

    mutate.link(g, "Q04", "C13")
    mutate.link(g, "Q04", "S12")

    mutate.note_add(g, "Due difetti visti dall'utente sulla dashboard vera, dopo i cancelli 2 e 3: la "
                       "selezione del testo durante il pan (C13) e la scheda del ticket che era una "
                       "modale e diventa la seconda vista del pannello di destra (S11, S12).")
