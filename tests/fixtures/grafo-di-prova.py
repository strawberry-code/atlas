"""Grafo di prova: tre rami, una catena profonda, un nodo con molti blocker.

Serve alla verifica end-to-end. Si esegue con:
    atlas exec .atlas/scripts/001-grafo-di-prova.py
"""
from core import mutate


def run(g):
    mutate.add_branch(g, "F", "Fondamenta", "#4f46e5")
    mutate.add_branch(g, "D", "Dominio", "#0f766e")
    mutate.add_branch(g, "X", "Consegna", "#b7791f")

    mutate.set_meta(g, destination="Un progetto finto che serve solo a verificare che Atlas regga.")
    mutate.note_add(g, "Grafo di prova: nessun nodo qui produce codice vero.")

    mutate.add_node(g, id="F01", branch="F", type="grilling", mode="HITL",
                    title="Contratto operativo del progetto",
                    question="Con quale contratto lavora l'agente su questo repo, e quali gesti può fare da solo? È il nodo che decide come si decide.")
    mutate.add_node(g, id="F02", branch="F", type="research", mode="AFK",
                    title="Stato dell'arte degli harness a grafo",
                    question="Che cosa esiste già, e quali scelte hanno preso gli altri? Servono fonti lette adesso, con link e data.")
    mutate.add_node(g, id="F03", branch="F", type="task", mode="AFK",
                    title="Impalcatura del repo",
                    question="Cartelle, linting, test runner. Fatto quando un file nuovo trova da solo il suo posto.",
                    blockedBy=["F01"])

    mutate.add_node(g, id="D01", branch="D", type="grilling", mode="HITL",
                    title="Modello di dominio",
                    question="Quali sono le entità e i loro invarianti? Fatto quando il linguaggio è condiviso e scritto.",
                    blockedBy=["F01", "F02"])
    mutate.add_node(g, id="D02", branch="D", type="task", mode="AFK",
                    title="Tipi del dominio",
                    question="Traduce il modello in tipi, con i test che ne difendono gli invarianti.",
                    blockedBy=["D01", "F03"])
    mutate.add_node(g, id="D03", branch="D", type="task", mode="AFK",
                    title="Persistenza",
                    question="Dove vivono i dati e con quale schema. Fatto quando un salvataggio sopravvive a un riavvio.",
                    blockedBy=["D02"])
    mutate.add_node(g, id="D04", branch="D", type="prototype", mode="HITL",
                    title="Prototipo dell'interazione",
                    question="Un artefatto rozzo a cui reagire, per capire se il modello regge nell'uso reale.",
                    blockedBy=["D02"])
    mutate.add_node(g, id="D05", branch="D", type="task", mode="AFK",
                    title="Casi limite della persistenza",
                    question="Concorrenza, file corrotti, disco pieno. Fatto quando ogni caso ha un test che lo copre.",
                    blockedBy=["D03"])

    mutate.add_node(g, id="X01", branch="X", type="grilling", mode="HITL",
                    title="Come si distribuisce",
                    question="Quale canale, con quale cadenza, e chi firma gli artefatti.",
                    blockedBy=["F01"])
    mutate.add_node(g, id="X02", branch="X", type="task", mode="AFK",
                    title="Pipeline di build",
                    question="Che cosa produce la pipeline, e come si verifica che l'artefatto sia buono.",
                    blockedBy=["X01", "F03"])
    mutate.add_node(g, id="X03", branch="X", type="task", mode="AFK",
                    title="Pacchetto installabile",
                    question="Il formato di consegna e la sua prova di installazione su una macchina pulita.",
                    blockedBy=["X02", "D03"])
    mutate.add_node(g, id="X04", branch="X", type="task", mode="HITL",
                    title="Prova generale su macchina pulita",
                    question="Installazione vera, uso reale, aggiornamento a una versione successiva.",
                    blockedBy=["X03", "D04", "D05"])

    mutate.fog_add(g, "come si misura se il grafo sta aiutando davvero o sta solo aggiungendo cerimonia")
    mutate.fog_add(g, "che succede quando due persone lavorano lo stesso grafo su macchine diverse")
