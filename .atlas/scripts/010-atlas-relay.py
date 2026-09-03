"""Relay notifiche, primo giro.

Si esegue con:  atlas exec .atlas/scripts/010-atlas-relay.py

Il perimetro, l'ordine e i rischi accettati stanno in docs/atlas-relay-design.md
§11, deciso il 2026-09-02 dopo due grilling. Ogni nodo cita la sezione che lo
governa: chi lo lavora legge quella, non il documento intero.
"""
from core import mutate

DOC = "docs/atlas-relay-design.md"


def run(g):
    mutate.set_meta(g,
        destination="Notifiche Telegram con decisione e sguardo. Servizio chiuso a invito, identita' per installazione e non per grafo, relay senza memoria del lavoro altrui. Perimetro e ordine in %s §11." % DOC,
        notes=[
            "Fonte di verita' del disegno: %s. Si leggono §4-bis (modello), §6-bis, §7-bis, §7-ter (decisioni) e §11 (primo incremento). NON si legge §4 ne' §6-ter: sono superate e tenute solo come traccia." % DOC,
            "Il codice di partenza esiste gia' in relay/ e payload/core/ (nodi D01-D08 del grafo 260830-atlas-interactions). §11/2 impone la riscrittura chirurgica del solo layer di identita': si tengono linea aperta, bottoni, ritorno del tap e aggiornamento del messaggio.",
            "Vincoli invariati di Atlas: sola stdlib, nessuna dipendenza di terze parti, file di payload/core sotto le 200 righe, ogni stringa a video da catalogo t() in italiano e inglese, accenti veri nei cataloghi e ASCII nei commenti del motore. Dopo ogni modifica a payload/ o atlascli/ si rigenera dist/atlas con python3 build.py.",
            "Vietato 'git stash' in qualunque forma: un lavoro e' gia' andato perso cosi'. Vietato fermarsi ad aspettare la notifica di un comando lanciato in background mentre si tiene un nodo rivendicato: o resta in foreground fino all'esito, o si lavora ad altro sullo stesso nodo.",
            "Tutti i nodi girano su Claude e non sul default Codex Luna: la quota Codex e' esaurita fino al 30 settembre 2026. F01 e' AFK come gli altri, ma il suo esito atteso e' una diagnosi dell'ambiente, non un deploy inventato.",
            "Il deploy reale (F01) richiede segreti che non stanno in questo repo. Si verifica l'ambiente, non si inventano risorse ne' si stampano segreti.",
        ],
    )
    g.data["branches"]["A"].update(label="Identita' e ingresso", color="#4f46e5")
    mutate.add_branch(g, "B", "Notifica e tap", "#0f766e")
    mutate.add_branch(g, "C", "Presidi", "#c2410c")
    mutate.add_branch(g, "D", "Sguardo", "#7c3aed")
    mutate.add_branch(g, "E", "Condiviso e versioni", "#a16207")
    mutate.add_branch(g, "F", "Consegna", "#475569")

    # --- A. il layer che cambia identita': dal progetto all'installazione
    mutate.add_node(g, id="A01", branch="A", type="task", mode="AFK", model="claude",
        title="Definisci l'identita' di installazione",
        question="Oggi il relay riconosce un bearer di progetto e associa una chat a un grafo. Il modello nuovo (§4-bis) dice che l'identita' e' dell'installazione di Atlas, creata al primo collegamento e mai mostrata a nessuno. Definisci come nasce quel segreto, dove vive sulla macchina fuori dal repo (decisione 8), come si presenta al relay a ogni richiesta e quale versione di protocollo dichiara, che servira' a E02. Nel graph.json versionato non finisce nulla: un repo pubblico non deve rivelare nemmeno che quel progetto usa un relay. Consegna il contratto scritto piu' il modulo client che lo implementa, con i test.")
    mutate.add_node(g, id="A02", branch="A", type="task", mode="AFK", model="claude",
        title="Riscrivi lo store del relay sulle installazioni",
        question="relay/pairing.py oggi tiene 'chat -> progetto' e 'progetto -> chat'. Portalo a 'chat -> installazione', che e' il modello di §4-bis: una installazione ha una chat, una chat puo' seguire piu' installazioni della stessa persona. Il relay non conserva nomi di progetti (grilling 3) e non conserva stato dei grafi (grilling 7). Mantieni la persistenza su disco che sopravvive a un restart e la monouso del codice di collegamento. Aggiorna i test esistenti invece di affiancarne di nuovi.",
        blockedBy=["A01"])
    mutate.add_node(g, id="A03", branch="A", type="task", mode="AFK", model="claude",
        title="Richiesta d'ingresso e approvazione, lato relay",
        question="§11/3: il servizio e' chiuso e si entra su approvazione. Chi si collega ottiene uno stato 'in attesa di via libera'; al gestore arriva un messaggio col nome Telegram del richiedente e approva o rifiuta con un tap. Definisci come il gestore si identifica al bot, che non puo' essere un valore indovinabile ne' un segreto scritto nel codice. Chi viene rifiutato lo sa (grilling 26). Nessuna stringa da maneggiare per nessuno dei due, come impone §0.",
        blockedBy=["A02"])
    mutate.add_node(g, id="A04", branch="A", type="task", mode="AFK", model="claude",
        title="Il collegamento visto da chi lo usa",
        question="Il lato client del gesto di §0: un bottone discreto e sempre presente nel pannello (grilling 27), che non interrompe chi lavora offline e non propone niente a chi non chiede. Premuto, mostra che si e' in attesa del via libera, poi l'esito, con parole umane e mai 'bearer', 'capability' o 'graphId'. Qui va detta anche la promessa nulla di grilling 33, cioe' che il servizio e' sperimentale e puo' finire quando il gestore vuole: sul bottone che lo attiva, non in una riga di documentazione (§7-ter, punti scoperti). Il pannello Notifiche esiste gia' da D05: si adatta, non si riscrive.",
        blockedBy=["A03"])
    mutate.add_node(g, id="A05", branch="A", type="task", mode="AFK", model="claude",
        title="Instrada per installazione, non per progetto",
        question="relay/tunnel.py oggi risolve 'sessioni_di(graph)' e spinge un tap a ogni runId connesso per quel progetto. Portalo al modello nuovo: un tap torna alla linea aperta dell'installazione che ha mandato la notifica, e a nessun'altra. Resta senza coda: se la linea non c'e' piu', il tap non si conserva (grilling 8) e chi ha premuto lo scopre subito (§7-bis/13). Nessun battito periodico: la linea morta si scopre al momento del tap, non prima.",
        blockedBy=["A02"])

    # --- B. la notifica e il ritorno del tap sul modello nuovo
    mutate.add_node(g, id="B01", branch="B", type="task", mode="AFK", model="claude",
        title="Manda la notifica col titolo umano",
        question="Il messaggio nomina il progetto con il titolo umano scritto da chi ha creato il grafo, mai con lo slug (§7-bis/14). Porta il minimo che serve a decidere: titolo del nodo e azioni ammesse, mai il ticket, mai i path (§5). La lingua e' quella del progetto (grilling 34). Se e' disponibile una sessione governabile da remoto, in fondo compare la riga col link, che serve alle decisioni che non sono un si' o un no (§7-bis/12).",
        blockedBy=["A05", "A04"])
    mutate.add_node(g, id="B02", branch="B", type="task", mode="AFK", model="claude",
        title="La levetta che zittisce un progetto",
        question="Ogni progetto nasce con le notifiche accese (§7-ter/1, che ribalta la decisione 30) e una levetta per progetto le spegne. Rischio accettato e dichiarato in §11/11: un progetto riservato esce finche' qualcuno non lo spegne a mano, quindi la levetta dev'essere visibile e raggiungibile in un gesto, non sepolta in un file di configurazione. Chi lavora offline non deve vederla comparire ne' sentirne parlare.",
        blockedBy=["B01"])
    mutate.add_node(g, id="B03", branch="B", type="task", mode="AFK", model="claude",
        title="Porta il ritorno del tap sul modello nuovo",
        question="Il codice dei tap esiste gia' (payload/core/telegram_actions.py, capability, relay/telegram_webhook.py) e per §11/2 si tiene. Adattalo all'instradamento per installazione di A05: il tap risolve l'Interazione nel grafo di chi ha lanciato il lavoro, il messaggio si aggiorna e perde i bottoni cosi' un secondo tap non genera un altro evento. I bottoni hanno potere pieno (grilling 19): conferma, rifiuta, riprova, ferma il lavoro. Resta il limite di 64 byte di callback_data.",
        blockedBy=["B01", "A05"])
    mutate.add_node(g, id="B04", branch="B", type="task", mode="AFK", model="claude",
        title="Rendi visibile la notifica non consegnata",
        question="§7-ter/3: oggi una notifica che non parte si perde in silenzio, e chi aspetta non ha modo di sapere perche' il telefono tace. Il nodo in attesa deve portare sulla dashboard la riga che dice che la notifica non e' partita. Nessun ritentativo e nessuna coda in piu' (grilling 22): cambia solo che il silenzio ha una spiegazione scritta dove la persona torna a guardare.",
        blockedBy=["B01"])

    # --- C. i presidi che proteggono il bot
    mutate.add_node(g, id="C01", branch="C", type="task", mode="AFK", model="claude",
        title="Freno automatico oltre soglia",
        question="§11/5: il rischio di questa fase non e' l'abuso umano, e' un Atlas che va in loop e fa limitare il bot da Telegram, lasciando senza notifiche tutti gli altri. Oltre un tetto orario per installazione il relay smette di servire quella linea e lo dice sia al gestore sia a chi e' stato fermato. La soglia si sceglie senza dati d'uso, quindi va tenuta molto alta e in un solo punto leggibile, per essere ritarata alla fine del primo giro. Chi viene fermato deve avere una via per rispondere (§7-ter, punti scoperti): senza appello il blocco automatico e' la sorpresa peggiore del sistema.",
        blockedBy=["A02"])
    mutate.add_node(g, id="C02", branch="C", type="task", mode="AFK", model="claude",
        title="Elenco dei computer collegati e distacco",
        question="§7-ter/5: un comando al bot elenca le installazioni collegate a quella chat con l'ultima volta che si sono fatte vive, e ne stacca una con un tap. Serve perche' chi cambia Mac o reinstalla oggi lascerebbe il vecchio collegamento appeso per sempre, e senza battito periodico il relay non puo' accorgersene da solo. Chi tace per mesi si dimentica da solo.",
        blockedBy=["A03"])

    # --- D. lo sguardo: chiedere invece di essere chiamati
    mutate.add_node(g, id="D01", branch="D", type="task", mode="AFK", model="claude",
        title="Comandi di stato, con la risposta a Mac spento",
        question="§11/6 vuole nel primo giro anche lo sguardo. Definisci l'elenco chiuso dei comandi, non uno di piu': a che punto e' il lavoro, cosa aspetta una persona, cos'e' andato storto. La risposta viene dal computer lungo la linea gia' aperta, perche' il relay non conserva stato di nessuno (grilling 7). La linea esiste solo mentre un lavoro gira (grilling 32), quindi fuori da quella finestra il bot deve dire chiaro che il computer non e' in linea, invece di tacere o di far aspettare (§7-ter/2).",
        blockedBy=["A05"])
    mutate.add_node(g, id="D02", branch="D", type="task", mode="AFK", model="claude",
        title="Vedere il progetto senza spedire i ticket",
        question="La dashboard incorpora il testo integrale di ogni ticket come JSON (payload/core/render_sheet.py), quindi mandarla al telefono manderebbe al server tutto il contenuto del lavoro, contro §5. §11/4: per il telefono si costruisce la stessa pagina senza i testi dentro, con grafo, titoli e stati, e per leggere un ticket si va al computer. Le due uscite di questa funzione, l'immagine scattata dal browser e la pagina allegata, condividono la stessa richiesta al client e vanno progettate insieme (§7-bis), non come due funzioni diverse.",
        blockedBy=["D01"])

    # --- E. il lavoro condiviso e il passare delle versioni
    mutate.add_node(g, id="E01", branch="E", type="task", mode="AFK", model="claude",
        title="Codice muto del progetto e avviso di aggiornare",
        question="§11/9: quando un altro chiude un pezzo di un progetto condiviso, il bot manda un avviso breve che qualcosa e' cambiato e che conviene aggiornare, senza dire che cosa. Per sapere chi avvisare serve un codice opaco che viaggia col repository, uguale su tutte le copie e muto per chi lo legge. Vincolo stretto, deciso il 2026-09-02: quel codice instrada soltanto questo avviso, e non autorizza a ricevere una decisione ne' a risolverla, che restano legate all'installazione. Il relay continua a non sapere come si chiama il progetto ne' cosa contiene. L'allineamento resta un gesto git: il relay non diventa la fonte di verita' del grafo. Attenzione al grafo 260825-sync-distribuita, che non deve raccontare una storia diversa sullo stesso grafo.",
        blockedBy=["B01"])
    mutate.add_node(g, id="E02", branch="E", type="task", mode="AFK", model="claude",
        title="Avvisa sul telefono prima di smettere di servire",
        question="§7-ter/6: il relay parla una sola lingua (grilling 23), quindi il giorno che cambia protocollo ogni Atlas non aggiornato smette di ricevere nello stesso istante. Usando la versione dichiarata in A01, l'avviso deve arrivare sul telefono prima che il servizio smetta, con l'indicazione di come aggiornare, perche' la dashboard e' il posto dove la persona in quel momento non sta guardando.",
        blockedBy=["A01"])

    # --- F. la consegna
    mutate.add_node(g, id="F01", branch="F", type="task", mode="AFK", model="claude",
        title="Metti in servizio il relay e provalo davvero",
        question="Porta il servizio sull'host OCI che gia' ospita gli altri servizi, senza toccarli, e verifica il giro completo con il bot vero: collegamento, approvazione, notifica, tap che risolve, comando di stato, vedere il progetto. Il polling verso Telegram (grilling 5) evita hostname pubblico, certificato e porte aperte, quindi la security list non si tocca. HITL perche' servono segreti e decisioni che stanno fuori dal repo: chiedi invece di inventare, e non stampare mai un segreto.",
        blockedBy=["A04", "B02", "B03", "B04", "C01", "C02", "D02", "E01", "E02"])
    mutate.add_node(g, id="END", branch="F", type="task", mode="AFK", model="claude",
        title="Chiudi il primo giro del relay",
        question="Verifica il metro di successo fissato in §11/12: il servizio serve se le decisioni si risolvono dal telefono invece di essere rimandate al computer. Controlla che chi lavora offline non veda comparire niente, che un progetto spento resti muto, che il contenuto dei ticket non sia mai passato dal server, e che i due punti scoperti di §7-ter siano stati davvero affrontati in A04 e C01. Aggiorna %s con quel che l'uso reale ha smentito." % DOC,
        blockedBy=["F01"])
