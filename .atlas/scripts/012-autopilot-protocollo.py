"""Il protocollo di esito fra agente e Autopilot.

Si esegue con:  atlas exec .atlas/scripts/012-autopilot-protocollo.py

Oggi il pilota sa due cose sole: il nodo risulta chiuso nel grafo, oppure il
processo dell'agente e' morto. Tutto quel che sta in mezzo lo deduce, e deduce
male: un agente che si arrende esce pulito senza chiudere, il pilota lo classifica
'ambiguous-termination' e lo rilancia otto volte contro lo stesso muro; un agente
appeso senza produrre nulla tiene il nodo fino al tetto di novanta minuti.

Il vincolo che governa questo ramo: **Autopilot non e' un LLM**. Ogni cosa che un
agente dichiara dev'essere un valore codificato, in un posto fissato, leggibile da
un programma senza interpretare prosa. Un testo libero puo' accompagnare il valore,
mai sostituirlo.
"""
from core import mutate


def run(g):
    mutate.add_branch(g, "H", "Protocollo di esito", "#0891b2")

    mutate.add_node(g, id="H01", branch="H", type="task", mode="AFK", model="claude",
        title="Fissa il protocollo, prima di implementarlo",
        question="Definisci l'insieme chiuso degli esiti che un agente puo' dichiarare e dei segnali che puo' emettere mentre lavora, con i valori esatti (stringhe fissate, non prosa), il posto dove vengono scritti e chi li scrive. Almeno: lavoro finito, resa con motivo, serve una persona, e un passo di avanzamento. Il vincolo che governa tutto: chi legge e' un programma, non un modello, quindi niente da interpretare e nessun valore fuori elenco. Chiediti anche cosa succede se un agente dichiara due cose in contraddizione, o se muore fra la dichiarazione e l'uscita. Consegna il contratto scritto, senza codice.")

    mutate.add_node(g, id="H02", branch="H", type="task", mode="AFK", model="claude",
        title="L'agente segna dove e' arrivato",
        question="Implementa il segnale di avanzamento definito in H01: un comando che l'agente chiama mentre lavora per dichiarare il passo raggiunto, con il suo valore codificato e un testo breve facoltativo. Aggiorna il battito del lucchetto, cosi' chi guarda sa non solo che il nodo e' preso, ma da quanto non succede niente. Deve costare poco chiamarlo spesso e non deve mai far fallire il lavoro se fallisce lui.",
        blockedBy=["H01"])

    mutate.add_node(g, id="H03", branch="H", type="task", mode="AFK", model="claude",
        title="Il pilota si accorge di un agente fermo",
        question="Oggi il runner aspetta la fine del processo in un colpo solo, con un tetto fisso di novanta minuti (providers.TIMEOUT_TENTATIVO_SECONDI): un agente appeso tiene il nodo per tutto quel tempo. Fallo attendere a fette, e fra una fetta e l'altra guarda l'avanzamento dichiarato in H02: se non si muove niente per un periodo dichiarato, l'agente si uccide e il tentativo fallisce come gli altri, passando dal budget dei retry. Il tetto assoluto resta come ultima difesa per l'agente che non dichiara niente. Attenzione a non uccidere chi sta legittimamente pensando a lungo: il periodo di silenzio ammesso va scelto sui tempi veri, non a occhio (il run del 2026-09-03 ha nodi legittimi da 5 a 49 minuti).",
        blockedBy=["H02"])

    mutate.add_node(g, id="H04", branch="H", type="task", mode="AFK", model="claude",
        title="L'agente puo' arrendersi, e il pilota lo ascolta",
        question="Implementa l'esito di resa definito in H01: l'agente dichiara di non poter fare il lavoro e perche', con un motivo scelto da un elenco chiuso piu' un testo libero. Il pilota lo tratta come definitivo: niente ritentativi, il nodo torna disponibile con la resa registrata, e il run prosegue sul resto della frontiera. Oggi lo stesso caso finisce in 'ambiguous-termination', che sta fra i fallimenti ritentabili (retry.RETRYABLE_FAILURES) e brucia otto tentativi identici. La resa dev'essere distinguibile da un crash sia nel ledger sia in 'atlas run-status'.",
        blockedBy=["H01"])

    mutate.add_node(g, id="H05", branch="H", type="task", mode="AFK", model="claude",
        title="L'agente puo' chiedere una persona senza sprecare tentativi",
        question="Implementa l'esito 'serve una persona' definito in H01, appoggiandosi al meccanismo delle Interazioni che gia' esiste invece di costruirne un secondo. Un agente che incontra una decisione che non gli spetta la dichiara, il pilota apre l'Interazione e lascia il nodo in attesa senza contarlo come fallimento e senza rilanciare nessuno. Alla risposta il nodo torna lavorabile.",
        blockedBy=["H01"])

    mutate.add_node(g, id="H06", branch="H", type="task", mode="AFK", model="claude",
        title="Scrivi il protocollo dove l'agente lo legge",
        question="Un protocollo che gli agenti non conoscono non esiste. Porta gli esiti e il segnale di avanzamento nel briefing che il runner passa al processo figlio (payload/core/providers.py), nel contratto che ogni progetto riceve (payload/templates/contract.it.md e .en.md), in 'atlas how-to' e nella skill atlas-work, in entrambe le lingue. Verifica che il testo dica i valori esatti e non li parafrasi: chi li legge deve poterli copiare. Rigenera dist/atlas e il contratto di questo progetto.",
        blockedBy=["H02", "H03", "H04", "H05"])

    mutate.add_node(g, id="H07", branch="H", type="task", mode="AFK", model="claude",
        title="Prova il protocollo su un guasto vero",
        question="Verifica il ramo con una prova che riproduce i tre guasti visti sul campo il 2026-09-03: un agente che finisce il lavoro e muore prima di chiudere, uno che resta vivo senza produrre niente, e uno che si arrende. Ogni caso deve produrre un esito distinto e leggibile in 'atlas run-status' e nel ledger, e nessuno dei tre deve costare piu' di un tentativo quando non ha senso ritentare. Poi la suite intera e la prova end-to-end.",
        blockedBy=["H06"])
