"""Primo disegno: Atlas Automata, orchestratore meccanico AFK.

Si esegue con:  atlas exec .atlas/scripts/006-atlas-automata.py

Il grafo pianifica l'implementazione completa della feature descritta nella
issue GitHub #29. L'esecuzione della feature riceverà il parallelismo come
parametro obbligatorio a ogni avvio; il grafo non lo impone e non lo salva.
"""
from core import mutate


def run(g):
    mutate.set_meta(g, destination=(
        "Atlas Automata sostituisce l'orchestratore LLM con un runner meccanico, "
        "configurabile per esecuzione, robusto al fallimento e pronto a usare "
        "Codex Luna, Claude, Gemini, Terra e futuri adapter."))

    g.data["branches"]["A"] = {"label": "Contratto e schema", "color": "#4f46e5"}
    mutate.add_branch(g, "B", "Runner e frontiera", "#0f766e")
    mutate.add_branch(g, "C", "Modelli e resilienza", "#c2410c")
    mutate.add_branch(g, "D", "Operatività AFK", "#7c3aed")
    mutate.add_branch(g, "E", "Verifica e consegna", "#475569")

    # --- A: contratti pubblici e compatibilità -----------------------------
    mutate.add_node(g, id="A01", branch="A", type="task", mode="AFK",
                    title="Contratto di Atlas Automata",
                    question=(
                        "Definisci il contratto pubblico di Atlas Automata e i criteri "
                        "di successo: runner senza LLM orchestratore, esecuzione AFK, "
                        "frontiera Atlas come sorgente di verità, parametro di parallelismo "
                        "obbligatorio per run e supporto a future estensioni. Documenta "
                        "anche cosa è fuori scope e come si riconosce una terminazione valida."))
    mutate.add_node(g, id="A02", branch="A", type="task", mode="AFK",
                    title="Campo modello opzionale nei nodi",
                    question=(
                        "Estendi lo schema dei nodi con un campo opzionale per il modello "
                        "richiesto dall'autore del grafo. Il valore deve restare vuoto quando "
                        "l'autore non lo specifica, senza introdurre un default scritto nei "
                        "nodi; aggiorna validazione, serializzazione, rendering e compatibilità "
                        "con i grafi esistenti."),
                    blockedBy=["A01"])

    # --- B: ciclo meccanico -------------------------------------------------
    mutate.add_node(g, id="B01", branch="B", type="task", mode="AFK",
                    title="Avvio con parallelismo esplicito",
                    question=(
                        "Progetta e implementa il comando o entry point di Automata che "
                        "richiede sempre il parallelismo per quella singola esecuzione. "
                        "Rifiuta valori mancanti, non positivi o non interi, conserva il "
                        "valore solo nel run e rendi esplicito che 1 significa seriale."),
                    blockedBy=["A01"])
    mutate.add_node(g, id="B02", branch="B", type="task", mode="AFK",
                    title="Runner guidato dalla frontiera Atlas",
                    question=(
                        "Implementa il ciclo meccanico che legge la frontiera Atlas, avvia "
                        "solo nodi eleggibili entro il limite richiesto, attende la chiusura "
                        "del nodo e rilegge lo stato prima di scegliere il successivo. Non "
                        "usare decisioni LLM per ordinamento, dipendenze o avanzamento."),
                    blockedBy=["A02", "B01"])
    mutate.add_node(g, id="B03", branch="B", type="task", mode="AFK",
                    title="Serialità e parallelismo limitato",
                    question=(
                        "Completa il controllo di concorrenza del runner: con parallelism=1 "
                        "deve esistere un solo agente attivo e nessun nodo deve partire prima "
                        "della chiusura del precedente; con valori maggiori il numero di agenti "
                        "attivi non deve superare il limite e ogni claim deve restare protetto."),
                    blockedBy=["B02"])
    mutate.add_node(g, id="B04", branch="B", type="task", mode="AFK",
                    title="Eventi di chiusura e aggiornamento della frontiera",
                    question=(
                        "Usa le funzionalità Atlas già disponibili per rilevare chiusure e "
                        "frontiera aggiornata senza polling cieco. Definisci il comportamento "
                        "quando un evento è duplicato, arriva in ritardo o manca, garantendo "
                        "resume idempotente e nessun doppio avvio dello stesso nodo."),
                    blockedBy=["B02"])

    # --- C: adapter, default, fallback e retry -----------------------------
    mutate.add_node(g, id="C01", branch="C", type="task", mode="AFK",
                    title="Registry degli adapter modello",
                    question=(
                        "Definisci un'interfaccia minima e future-extensible per lanciare un "
                        "agente AFK fuori sandbox con bypass dei permessi. Implementa il "
                        "registro degli adapter senza legare il runner a un provider specifico, "
                        "prevedendo almeno Codex Luna, Claude, Gemini e Code Terra come identità "
                        "configurabili."),
                    blockedBy=["A01", "A02"])
    mutate.add_node(g, id="C02", branch="C", type="task", mode="AFK",
                    title="Selezione del modello e default Luna",
                    question=(
                        "Collega il campo opzionale del nodo al registry: se è vuoto seleziona "
                        "Codex Luna, se è valorizzato risolvi il modello richiesto e rifiuta "
                        "configurazioni sconosciute con una diagnosi utile. Il comportamento "
                        "deve essere deterministico e osservabile nel log del run."),
                    blockedBy=["C01"])
    mutate.add_node(g, id="C03", branch="C", type="task", mode="AFK",
                    title="Fallback a Claude Sonnet",
                    question=(
                        "Implementa il fallback secondario predefinito da Codex Luna a Claude "
                        "Sonnet quando Luna è fuori uso o non disponibile. Distingui un provider "
                        "non disponibile da un errore del lavoro dell'agente, evita fallback "
                        "silenziosi su richieste esplicite e registra ogni transizione."),
                    blockedBy=["C02"])
    mutate.add_node(g, id="C04", branch="C", type="task", mode="AFK",
                    title="Retry progressivo e classificazione dei guasti",
                    question=(
                        "Implementa retry con backoff progressivo da minuti a ore e classificatori "
                        "per timeout, crash, rate limit, provider indisponibile, terminazione "
                        "ambigua e errore permanente. Il retry deve essere bounded, persistito, "
                        "riprendibile dopo riavvio e non deve duplicare un agente già attivo."),
                    blockedBy=["C03"])

    # --- D: operatività, sicurezza e diagnosi -------------------------------
    mutate.add_node(g, id="D01", branch="D", type="task", mode="AFK",
                    title="Lancio AFK fuori sandbox",
                    question=(
                        "Integra il lancio dei provider in modo che ogni agente Automata sia "
                        "AFK, eseguito fuori sandbox e con bypass dei permessi, senza dipendere "
                        "da prompt interattivi. Valida e documenta il contratto del processo "
                        "figlio, l'ambiente minimo e la propagazione sicura degli argomenti."),
                    blockedBy=["B02", "C02"])
    mutate.add_node(g, id="D02", branch="D", type="task", mode="AFK",
                    title="Stato, log e diagnostica del run",
                    question=(
                        "Rendi osservabili avvio, claim, provider scelto, tentativi, backoff, "
                        "fallback, chiusura, aggiornamento della frontiera e blocchi residui. "
                        "Aggiungi stato persistente e comandi di diagnosi che permettano di "
                        "capire perché un run è attivo, in attesa, fallito o completato."),
                    blockedBy=["B04", "C04", "D01"])
    mutate.add_node(g, id="D03", branch="D", type="task", mode="AFK",
                    title="Resume e idempotenza dopo interruzione",
                    question=(
                        "Implementa il riavvio di Automata da uno stato parziale: riconcilia agenti "
                        "terminati, claim scaduti, retry già registrati e nodi chiusi mentre il "
                        "runner era fermo. Dimostra che il resume non perde lavoro e non avvia "
                        "due volte un nodo ancora in corso."),
                    blockedBy=["B04", "C04", "D02"])

    # --- E: prove, documentazione e consegna -------------------------------
    mutate.add_node(g, id="E01", branch="E", type="task", mode="AFK",
                    title="Suite di test del runner meccanico",
                    question=(
                        "Aggiungi test unitari e end-to-end per parametro obbligatorio, serialità, "
                        "limite di parallelismo, frontier refresh, eventi duplicati o mancanti, "
                        "selezione modello, fallback, retry progressivo, timeout, crash, rate "
                        "limit, resume, idempotenza e terminazione ambigua. Usa adapter finti per "
                        "rendere i test deterministici."),
                    blockedBy=["B03", "B04", "C04", "D03"])
    mutate.add_node(g, id="E02", branch="E", type="task", mode="AFK",
                    title="CLI, contratto e documentazione future-proof",
                    question=(
                        "Aggiorna CLI, contratto, template e README per spiegare Atlas Automata, "
                        "il parametro di parallelismo per run, il campo modello vuoto per default, "
                        "Luna, Sonnet, adapter aggiuntivi, esecuzione AFK fuori sandbox e bypass "
                        "dei permessi. Documenta come aggiungere nuovi provider senza cambiare il "
                        "runner e come interpretare diagnosi e retry."),
                    blockedBy=["A02", "B01", "C03", "D02"])
    mutate.add_node(g, id="END", branch="E", type="task", mode="AFK",
                    title="Collaudo finale e chiusura dell'enhancement",
                    question=(
                        "Esegui la suite completa, la validazione Atlas, le verifiche CLI e almeno "
                        "un run controllato con parallelism=1. Confronta ogni requisito della issue "
                        "#29 con l'evidenza prodotta, verifica che non restino nodi aperti o rami "
                        "orfani e chiudi l'unica issue enhancement solo quando il comportamento "
                        "è documentato e riproducibile."),
                    blockedBy=["E01", "E02"])

    mutate.note_add(g, (
        "Issue GitHub unica: #29. Tutti i nodi sono AFK e destinati a un solo agente Luna "
        "per sessione. Il parallelismo non è una proprietà del grafo: Automata lo richiede "
        "esplicitamente a ogni avvio. Il campo modello dei nodi resta vuoto salvo richiesta "
        "dell'autore; il runner usa Codex Luna e ricade su Claude Sonnet se Luna non è disponibile. "
        "Ogni adapter deve eseguire fuori sandbox con bypass dei permessi. Il grafo è seriale per "
        "questa orchestrazione: non avviare più nodi contemporaneamente durante la sua esecuzione."))
