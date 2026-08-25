"""Primo disegno: l'evolutiva sulla sincronizzazione fra macchine.

Si esegue con:  atlas exec .atlas/scripts/001-primo-disegno.py

Lo scenario bersaglio sono due sessioni agente su due macchine diverse che prendono
nodi dello stesso grafo, con git come unico canale fra le due. L'ordine dei rami non
e' l'ordine in cui la domanda e' nata: il fondo condiviso viene prima del lucchetto
perche' senza fusione di graph.json due macchine litigano a ogni chiusura, e la
dashboard viene per ultima perche' e' una funzione pura del grafo e non aggiunge
vincoli a nessuno.
"""
from core import mutate


def run(g):
    mutate.set_meta(g, destination=(
        "Due agenti su due macchine lavorano lo stesso grafo senza pestarsi: le chiusure "
        "si fondono da sole, un nodo preso su una macchina risulta preso sull'altra, e la "
        "dashboard mostra chi tiene cosa mentre lo tiene."))

    # Il ramo di default nasce con create_graph e non c'e' una mutazione che lo rinomini
    # o lo tolga: si riusa invece di lasciarlo vuoto accanto agli altri, dove sarebbe
    # solo una voce in piu' nella legenda. Vedi la fog qui sotto.
    g.data["branches"]["A"] = {"label": "Fondo condiviso", "color": "#b45309"}
    mutate.add_branch(g, "L", "Lucchetto fra macchine", "#4f46e5")
    mutate.add_branch(g, "V", "Vista", "#0f766e")
    mutate.add_branch(g, "C", "Consegna", "#9f1239")

    # --- A: il file solo che due macchine si contendono ----------------------
    mutate.add_node(g, id="A01", branch="A", type="research", mode="AFK",
                    title="Come divergono davvero due copie del grafo",
                    question="Quando due macchine chiudono nodi diversi, quali conflitti "
                             "produce graph.json, quali sono ambigui per davvero e quali "
                             "lo sono solo perche' il file e' uno?")
    mutate.add_node(g, id="A02", branch="A", type="task", mode="AFK",
                    title="Fusione a tre vie per nodo",
                    question="Come si fondono due versioni di graph.json ragionando per id "
                             "di nodo invece che per riga, restando in sola stdlib?",
                    blockedBy=["A01"])
    mutate.add_node(g, id="A03", branch="A", type="task", mode="AFK",
                    title="Il driver arriva nei progetti ospiti",
                    question="Come fa un progetto installato a ritrovarsi il merge driver "
                             "registrato, senza che chi lo usa debba configurare git a mano?",
                    blockedBy=["A02"])
    mutate.add_node(g, id="A04", branch="A", type="task", mode="AFK",
                    title="Quel che non si fonde resta un conflitto dichiarato",
                    question="Quali casi la fusione automatica deve rifiutare invece di "
                             "risolvere, e come li lascia in mano a chi legge?",
                    blockedBy=["A02"])

    # --- L: la mutua esclusione, che e' il cuore del problema ----------------
    mutate.add_node(g, id="L01", branch="L", type="research", mode="AFK",
                    title="Le ref custom reggono su GitHub?",
                    question="GitHub accetta push su refs/atlas/*, e quanto costa in latenza "
                             "un ls-remote reale? Senza questa risposta il ramo non esiste.")
    mutate.add_node(g, id="L02", branch="L", type="grilling", mode="AFK",
                    title="Da liveness a lease",
                    question="Il claim oggi vale finche' vive un PID locale. Cosa cambia nel "
                             "modello quando quel PID sta su un'altra macchina, e quale "
                             "scadenza rende un lucchetto ancora un lucchetto?",
                    blockedBy=["L01"])
    mutate.add_node(g, id="L03", branch="L", type="prototype", mode="AFK",
                    title="Mutex su git refs, fuori dal motore",
                    question="Prendere, rubare uno scaduto, rilasciare, elencare: reggono come "
                             "primitive in uno script buttato via, prima di entrare in claims.py?",
                    blockedBy=["L01"])
    mutate.add_node(g, id="L04", branch="L", type="grilling", mode="AFK",
                    title="Dove abita il codice di rete",
                    question="payload/ non ammette rete e il lucchetto vive in claims.py. Si "
                             "dichiara la seconda eccezione dopo self_update, o il lucchetto "
                             "remoto passa da un confine nuovo?",
                    blockedBy=["L02", "L03"])
    mutate.add_node(g, id="L05", branch="L", type="task", mode="AFK",
                    title="Il lease entra in claims.py",
                    question="Come convivono lucchetto locale e lucchetto remoto senza due "
                             "verita' sullo stesso nodo?",
                    blockedBy=["L04"])
    mutate.add_node(g, id="L06", branch="L", type="task", mode="AFK",
                    title="Il battito si rinnova da solo",
                    question="Oggi l'heartbeat si aggiorna solo richiamando claim sullo stesso "
                             "nodo. Chi lo rinnova quando la sessione sta lavorando, e con che "
                             "passo rispetto alla scadenza del lease?",
                    blockedBy=["L05"])
    mutate.add_node(g, id="L07", branch="L", type="task", mode="AFK",
                    title="I bordi: finestra condivisa e assenza di rete",
                    question="_condiviso guarda le chiusure del grafo locale, che non sa cosa "
                             "ha chiuso l'altra macchina. E senza rete, cosa diventa il "
                             "lucchetto invece di fingere di funzionare?",
                    blockedBy=["L05"])

    # --- V: la domanda da cui e' partito tutto, che pero' dipende dal resto ---
    mutate.add_node(g, id="V01", branch="V", type="task", mode="AFK",
                    title="atlas serve: la dashboard smette di essere un file da riaprire",
                    question="Un server di sola stdlib che rigenera sull'mtime del grafo e "
                             "spinge al browser: quanto sta in piedi senza toccare il rendering?")
    mutate.add_node(g, id="V02", branch="V", type="task", mode="AFK",
                    title="I lucchetti delle altre macchine nella vista",
                    question="Con che passo si leggono i lucchetti remoti perche' la vista sia "
                             "viva senza martellare il remote a ogni secondo?",
                    blockedBy=["V01", "L05"])

    # --- C: quello che rende l'evolutiva consegnabile ------------------------
    mutate.add_node(g, id="C01", branch="C", type="task", mode="AFK",
                    title="Documenti in pari",
                    question="Cosa cambia nei due README, nel contratto e in how-to, adesso che "
                             "un claim puo' venire da un'altra macchina?",
                    blockedBy=["A03", "L06", "V02"])
    mutate.add_node(g, id="C02", branch="C", type="task", mode="AFK",
                    title="Prova su due cloni veri",
                    question="Due cloni, due identita', due agenti che prendono e chiudono "
                             "insieme: cosa deve succedere perche' la prova valga qualcosa e "
                             "non sia compiacente?",
                    blockedBy=["C01", "A04", "L07"])
    mutate.add_node(g, id="C03", branch="C", type="task", mode="HITL",
                    title="Collaudo umano e via libera",
                    question="Provata con le mani su due macchine vere, questa evolutiva si "
                             "rilascia o si tiene ferma? E se si rilascia, cosa resta scoperto?",
                    blockedBy=["C02"])

    mutate.fog_add(g, "manca una mutazione per rinominare o togliere un ramo: il ramo di "
                      "default creato da create_graph si puo' solo riscrivere a mano")
    mutate.fog_add(g, "sotto --dry-run due messaggi dell'install sono al passato "
                      "('contratto appeso', 'aggiunte N righe') accanto a 'scriverebbe'")
