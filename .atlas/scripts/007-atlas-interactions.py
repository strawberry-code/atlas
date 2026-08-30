"""Atlas interactions

Si esegue con:  atlas exec .atlas/scripts/007-atlas-interactions.py

Lo script gira dentro una sola transazione: se qualcosa non torna, il grafo resta
com'era. Alla chiusura la forma viene validata (id unici, archi risolti, niente cicli).
"""
from core import mutate


def run(g):
    mutate.set_meta(g,
        destination="Interazioni Atlas a basso attrito: pannello Notifiche, avvisi locali, email Himalaya e Telegram con relay OCI, risposta valida e ripresa Automata senza polling.",
        notes=["Issue #30. Tutti i nodi sono AFK e non specificano model: Automata usa Codex Luna di default.",
               "Il deploy Telegram richiede un bot, hostname e segreti OCI già approvati nel suo ambiente; il grafo li verifica ma non li crea né li espone."],
    )
    # Il grafo nuovo nasce sempre con A: qui gli diamo il nome del primo ramo.
    g.data["branches"]["A"].update(label="Interazioni e runner", color="#4f46e5")
    mutate.add_branch(g, "B", "Esperienza locale", "#0f766e")
    mutate.add_branch(g, "C", "Avvisi semplici", "#c2410c")
    mutate.add_branch(g, "D", "Relay e Telegram", "#7c3aed")
    mutate.add_branch(g, "E", "Verifica e consegna", "#475569")

    mutate.add_node(g, id="A01", branch="A", type="task", mode="AFK",
                    title="Verifica i prerequisiti del relay",
                    question="Verifica senza stampare segreti che l'ambiente di deploy contenga bot Telegram approvato, hostname HTTPS, credenziali OCI e riferimenti ai segreti. Se manca qualcosa, produci un errore diagnostico preciso senza selezionare risorse esistenti o inventare configurazioni.")
    mutate.add_node(g, id="A02", branch="A", type="task", mode="AFK",
                    title="Definisci il contratto UX e delle Interazioni",
                    question="Definisci i pochi eventi che interrompono l'utente, gli stati Interaction, le azioni consentite e i testi brevi delle card. Il percorso normale non deve mostrare configurazione, token, hostname o concetti di trasporto.")
    mutate.add_node(g, id="A03", branch="A", type="task", mode="AFK",
                    title="Implementa ledger e schema Interaction",
                    question="Implementa record persistenti, atomici e auditabili per un'Interazione, con contesto grafo/run/nodo, azioni ammesse, scadenza e idempotenza. Il ledger deve essere la fonte di verità, non il relay né la dashboard.",
                    blockedBy=["A02"])
    mutate.add_node(g, id="A04", branch="A", type="task", mode="AFK",
                    title="Implementa lifecycle e risposta validata",
                    question="Implementa apertura, risoluzione, annullamento e scadenza delle Interazioni come transazioni Atlas. Una risposta può applicare solo un'azione consentita, lascia audit completo e non può mutare il grafo da testo libero.",
                    blockedBy=["A03"])
    mutate.add_node(g, id="A05", branch="A", type="task", mode="AFK",
                    title="Collega Automata alle Interazioni",
                    question="Fai aprire a Automata le Interazioni per HITL, blocchi, retry esauriti, gate e END; al ricevimento di una risposta valida, risveglialo attraverso l'evento Atlas senza polling né un secondo scheduler.",
                    blockedBy=["A04"])

    mutate.add_node(g, id="B01", branch="B", type="task", mode="AFK",
                    title="Proietta le Interazioni nella dashboard",
                    question="Deriva dal ledger i dati minimi per la dashboard, senza ricostruire lo stato dai log. Esponi urgenza, età, stato, nodo, run e azioni consentite.",
                    blockedBy=["A03"])
    mutate.add_node(g, id="B02", branch="B", type="task", mode="AFK",
                    title="Costruisci il side panel Notifiche",
                    question="Aggiungi un pannello destro stiloso, compatto e richiudibile, con badge, attenzione richiesta, in attesa e risolte oggi. Ogni card deve spiegare in una frase cosa serve e offrire al massimo due azioni primarie.",
                    blockedBy=["A02", "B01"])
    mutate.add_node(g, id="B03", branch="B", type="task", mode="AFK",
                    title="Risolvi Interazioni dalla UI locale",
                    question="Collega le azioni del pannello al lifecycle atomico e alla ripresa di Automata. Mostra contesto, artefatti e log solo su richiesta; rendi impossibili doppio invio e azioni non ammesse.",
                    blockedBy=["A04", "B02"])

    mutate.add_node(g, id="C01", branch="C", type="task", mode="AFK",
                    title="Implementa il coordinatore notifiche",
                    question="Implementa un modulo interno che trasforma Interazioni in consegne, deduplica, registra gli esiti e applica retry bounded. I default devono essere silenziosi sui successi intermedi e rumorosi solo quando serve una persona, il run fallisce o arriva END.",
                    blockedBy=["A03"])
    mutate.add_node(g, id="C02", branch="C", type="task", mode="AFK",
                    title="Aggiungi avvisi browser e di sistema",
                    question="Invia avvisi locali senza setup quando il pannello ha una nuova Interazione rilevante. L'avviso deve riportare alla card giusta e non duplicare il rumore della dashboard.",
                    blockedBy=["B01", "C01"])
    mutate.add_node(g, id="C03", branch="C", type="task", mode="AFK",
                    title="Aggiungi avvisi Himalaya",
                    question="Invia alert ed escalation tramite un profilo Himalaya già configurato localmente. Non leggere mailbox, non interpretare risposte email e non scrivere credenziali in Atlas.",
                    blockedBy=["C01"])

    mutate.add_node(g, id="D01", branch="D", type="task", mode="AFK",
                    title="Definisci il protocollo client-relay",
                    question="Definisci un tunnel uscente autenticato dal client Atlas al relay OCI e capability opache, monouso, firmate e a scadenza. Il relay può trasportare azioni ma non conserva né autorizza lo stato del grafo.",
                    blockedBy=["A03", "A04"])
    mutate.add_node(g, id="D02", branch="D", type="task", mode="AFK",
                    title="Distribuisci Atlas Relay su OCI",
                    question="Implementa e distribuisci un servizio relay isolato dietro Caddy e systemd, con health check e rollback. Procedi soltanto dopo A01 e non toccare il bot WhenAGI o Claude Proxy esistenti.",
                    blockedBy=["A01", "D01"])
    mutate.add_node(g, id="D03", branch="D", type="task", mode="AFK",
                    title="Apri il tunnel Atlas verso il relay",
                    question="Implementa nel client Atlas la connessione uscente resiliente al relay, con riconnessione, identità di run e assenza di polling. Una disconnessione non deve inventare chiusure né perdere lo stato Atlas.",
                    blockedBy=["D01"])
    mutate.add_node(g, id="D04", branch="D", type="task", mode="AFK",
                    title="Implementa il bot Telegram con webhook",
                    question="Implementa l'adapter Telegram sul relay OCI: webhook HTTPS verificato, utenti non associati rifiutati e callback inline idempotenti. Mantieni il payload minimo e non loggare segreti o contenuto sensibile.",
                    blockedBy=["D02"])
    mutate.add_node(g, id="D05", branch="D", type="task", mode="AFK",
                    title="Crea il pairing Telegram one-tap",
                    question="Dal pannello Notifiche rendi possibile collegare Telegram con un solo bottone e un token di pairing monouso. L'utente non deve inserire token bot, chat ID, hostname o file di configurazione.",
                    blockedBy=["B02", "D03", "D04"])
    mutate.add_node(g, id="D06", branch="D", type="task", mode="AFK",
                    title="Inoltra le azioni Telegram ad Atlas",
                    question="Fai attraversare a un tap Telegram il relay e il tunnel fino al lifecycle locale Atlas. Valida capability, utente, scadenza e idempotenza, aggiorna il messaggio Telegram e lascia Automata riprendere solo dopo la transazione riuscita.",
                    blockedBy=["A04", "D03", "D04", "D05"])

    mutate.add_node(g, id="E01", branch="E", type="task", mode="AFK",
                    title="Esegui la verifica end-to-end",
                    question="Copri con test unitari, integrazione ed end-to-end il percorso Automata, Interazione, UI, avviso locale, Himalaya, Telegram, tap remoto, aggiornamento della frontiera e ripresa. Verifica anche duplicati, scadenze, restart e disconnessioni.",
                    blockedBy=["A05", "B03", "C02", "C03", "D06"])
    mutate.add_node(g, id="E02", branch="E", type="task", mode="AFK",
                    title="Scrivi Quick Start e diagnostica",
                    question="Documenta un percorso di due minuti per vedere il primo alert, collegare Telegram con un bottone e capire una consegna mancata. Mantieni i dettagli relay e sicurezza fuori dal percorso principale, ma disponibili nella diagnostica.",
                    blockedBy=["B03", "C02", "C03", "D05", "D06"])
    mutate.add_node(g, id="E03", branch="E", type="task", mode="AFK",
                    title="Completa hardening e release readiness",
                    question="Riesegui le suite complete, controlla sicurezza dei capability token, restart del relay, rollback, deduplica, documentazione e assenza di regressioni. Confronta la consegna con ogni requisito della issue #30.",
                    blockedBy=["E01", "E02"])
    mutate.add_node(g, id="END", branch="E", type="task", mode="AFK",
                    title="Chiudi Atlas Interactions",
                    question="Verifica che il pannello funzioni senza configurazione, Telegram si colleghi con un solo gesto, il relay OCI non sia fonte di verità e Automata arrivi a END dopo una risposta remota valida. Chiudi la issue #30 solo con evidenza riproducibile.",
                    blockedBy=["E03"])
