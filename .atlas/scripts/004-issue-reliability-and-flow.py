"""Primo disegno: affidabilità e coordinamento di Atlas.

Si esegue con:  atlas exec .atlas/scripts/004-issue-reliability-and-flow.py

Lo script gira dentro una sola transazione: se qualcosa non torna, il grafo resta
com'era. Alla chiusura la forma viene validata (id unici, archi risolti, niente cicli).
"""
from core import mutate


def run(g):
    # I rami corrispondono alle issue. Tutti i nodi sono AFK e ciascuno ha un confine
    # verificabile adatto a una sessione di un agente Luna; END raccoglie ogni ramo.
    g.data["branches"]["A"] = {"label": "#28 Integrità degli artefatti", "color": "#b91c1c"}
    mutate.add_branch(g, "B", "#27 Deduzione degli artefatti", "#c2410c")
    mutate.add_branch(g, "C", "#26 Interfaccia --artefatti", "#a16207")
    mutate.add_branch(g, "D", "#25 Doctor robusto", "#4d7c0f")
    mutate.add_branch(g, "E", "#24 Lock remoto", "#0f766e")
    mutate.add_branch(g, "F", "#23 Domande non bloccanti", "#2563eb")
    mutate.add_branch(g, "G", "#22 Drift del grafo", "#7c3aed")
    mutate.add_branch(g, "Z", "Consegna", "#475569")

    # --- A: #28 -------------------------------------------------------------
    mutate.add_node(g, id="A01", branch="A", type="task", mode="AFK",
                    title="Doctor verifica presenza e tracciamento degli artefatti",
                    question="Estendi doctor perché segnali, senza fermarsi, ogni artefatto di un nodo chiuso che manca dal disco oppure non è tracciato da Git. Aggiungi test di regressione per entrambi i casi e conserva i controlli già esistenti sulle scritture postume.")
    mutate.add_node(g, id="A02", branch="A", type="task", mode="AFK",
                    title="Close avvisa sugli artefatti non tracciati",
                    question="Al momento della chiusura, avvisa quando gli artefatti registrati esistono ma Git non li traccia, così il difetto è rimediabile prima di un comando distruttivo. Copri il comportamento con test CLI e documenta la semantica del solo avviso.",
                    blockedBy=["A01"])

    # --- B: #27 -------------------------------------------------------------
    mutate.add_node(g, id="B01", branch="B", type="task", mode="AFK",
                    title="Close richiede una scelta quando la deduzione salta",
                    question="Quando la deduzione degli artefatti non è attendibile per lavoro parallelo, rendi obbligatoria una dichiarazione esplicita: artefatti passati con --artefatti oppure --artefatti senza argomenti per dichiarare intenzionalmente il vuoto. Mantieni compatibili i casi in cui la deduzione riesce e aggiungi test mirati.")
    mutate.add_node(g, id="B02", branch="B", type="task", mode="AFK",
                    title="Contratto e messaggi rendono visibile la mancata deduzione",
                    question="Rendi inequivocabili messaggi, how-to e contratto su quando Atlas non deduce gli artefatti e su come dichiararli. Verifica con test di output che una chiusura non possa più sembrare completa lasciando involontariamente il campo vuoto.",
                    blockedBy=["B01"])

    # --- C: #26 -------------------------------------------------------------
    mutate.add_node(g, id="C01", branch="C", type="task", mode="AFK",
                    title="Definisci una raccolta non ambigua per --artefatti",
                    question="Correggi close e amend perché raccolgano tutti i path passati, anche con il flag ripetuto, senza scartare silenziosamente le occorrenze precedenti. Fissa in test la grammatica supportata, un path per argomento, e conserva la possibilità di dichiarare una lista vuota intenzionale.")
    mutate.add_node(g, id="C02", branch="C", type="task", mode="AFK",
                    title="Rifiuta artefatti malformati prima di salvarli",
                    question="Rifiuta token di artefatto ambigui con spazi o virgole e segnala al chiamante come passare i path correttamente, senza spezzare silenziosamente nomi di file validi. Verifica anche l'esistenza dei path alla chiusura e copri con regressioni le quattro forme d'errore osservate, inclusa l'espansione di variabili in zsh.",
                    blockedBy=["C01"])

    # --- D: #25 -------------------------------------------------------------
    mutate.add_node(g, id="D01", branch="D", type="task", mode="AFK",
                    title="Doctor degrada gli OSError a diagnosi",
                    question="Tratta un OSError durante l'ispezione di un artefatto, incluso ENAMETOOLONG, come un avviso con id del nodo e path non valido invece di lasciare uscire un traceback. Aggiungi una regressione che confermi che doctor completa il resto della diagnosi.")

    # --- E: #24 -------------------------------------------------------------
    mutate.add_node(g, id="E01", branch="E", type="task", mode="AFK",
                    title="Lock remoto risolve il nome del remote nel repository del progetto",
                    question="Risolvi lock.remote dal nome configurato, per esempio origin, all'URL Git prima di creare il trasporto nel repository di servizio. Distingui configurazione non risolvibile da errore di rete, aggiorna il contratto e aggiungi test sia per nome sia per URL.")

    # --- F: #23 -------------------------------------------------------------
    mutate.add_node(g, id="F01", branch="F", type="task", mode="AFK",
                    title="Registra le domande con assunzione nel grafo",
                    question="Aggiungi al grafo un modello minimale e validato per domande, stato, nodo d'origine, assunzione, autore, timestamp e risposta. Implementa le mutazioni necessarie e rifiuta ask sui nodi HITL, così la funzione non aggira il contratto umano.")
    mutate.add_node(g, id="F02", branch="F", type="task", mode="AFK",
                    title="Espone ask, asks e answer nella CLI",
                    question="Implementa ask, asks e answer con messaggi coerenti, identità e persistenza transazionale. La lista deve rendere leggibili le domande aperte e answer deve chiudere una domanda senza modificare lo stato del nodo che l'ha generata.",
                    blockedBy=["F01"])
    mutate.add_node(g, id="F03", branch="F", type="task", mode="AFK",
                    title="Calcola l'impatto di una risposta divergente",
                    question="Quando la risposta umana diverge dall'assunzione, individua e stampa i nodi chiusi dopo la domanda che dipendono dal suo nodo, direttamente o transitivamente. Copri con test le risposte concordi, divergenti e l'assenza di nodi da riesaminare.",
                    blockedBy=["F02"])
    mutate.add_node(g, id="F04", branch="F", type="task", mode="AFK",
                    title="Rende le domande visibili e governate",
                    question="Aggiungi al dashboard e a doctor la visibilità delle domande aperte e invecchiate, poi allinea contratto, how-to e test integrati. Il risultato deve spiegare che ask traccia un'assunzione in un nodo AFK e non è un surrogato di una decisione HITL.",
                    blockedBy=["F03"])

    # --- G: #22 -------------------------------------------------------------
    mutate.add_node(g, id="G01", branch="G", type="task", mode="AFK",
                    title="Configura i segnali osservati per drift",
                    question="Definisci la configurazione minima per escludere file collettori dalla diagnosi e raccogli, con test, le coppie di nodi chiusi che condividono artefatti in un ordine temporale valido. Non escludere per estensione, perché documentazione e fogli di test possono essere deliverable reali.")
    mutate.add_node(g, id="G02", branch="G", type="task", mode="AFK",
                    title="Drift deduce soltanto archi mancanti plausibili",
                    question="Implementa l'analisi transitiva che segnala un arco mancante quando un nodo successivo tocca un artefatto di un nodo precedente senza già dipenderne. Non implementare la diagnosi degli archi spurii, bocciata dalla prova sul campo, e conserva l'evidenza che giustifica ogni segnalazione.",
                    blockedBy=["G01", "B02", "C02"])
    mutate.add_node(g, id="G03", branch="G", type="task", mode="AFK",
                    title="Espone atlas drift come diagnosi leggibile",
                    question="Integra atlas drift nella CLI, nella documentazione e nella suite usando il caso reale come regressione. Il comando deve proporre diagnosi senza mutare automaticamente il grafo e spiegare come un umano può trasformare un segnale in un arco dichiarato.",
                    blockedBy=["G02"])

    # --- Z: finale unico ----------------------------------------------------
    mutate.add_node(g, id="END", branch="Z", type="task", mode="AFK",
                    title="Verifica finale e chiusura delle issue",
                    question="Esegui la suite completa, i controlli doctor e le verifiche manuali minime dei nuovi flussi; completa la documentazione rimasta e confronta ogni requisito delle issue #22-#28 con il codice consegnato. Chiudi o aggiorna le issue solo quando l'evidenza della verifica è riportabile senza riserve.",
                    blockedBy=["A02", "B02", "C02", "D01", "E01", "F04", "G03"])

    mutate.note_add(g, "Tutti i nodi sono AFK e dimensionati per un solo agente Luna 5.6. I rami possono procedere in parallelo quando la frontiera lo consente; ogni ramo confluisce in END.")
