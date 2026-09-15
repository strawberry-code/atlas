"""Primo disegno del grafo atlas-memory: aree di memoria con sigillo.

Si esegue con:  atlas exec .atlas/scripts/024-primo-disegno.py

La fonte di ogni nodo e' .atlas/graphs/260915-atlas-memory/notes/design.md: il
disegno finale discusso il 2026-09-15, con le tre regole (locked/append/edit), il
sigillo nel grafo e i tre confronti a close. I nodi lo citano e non lo ripetono.
"""
from core import mutate

DESIGN = ".atlas/graphs/260915-atlas-memory/notes/design.md"
FONTE = (f"Leggi per intero {DESIGN} prima di toccare il codice: e' la fonte di questo "
         "nodo e di tutti gli altri. Se la domanda qui sotto e il documento si "
         "contraddicono vince la domanda, e la contraddizione va in nebbia con atlas fog.")


def run(g):
    mutate.add_branch(g, "M", "Modello", "#4f46e5")
    mutate.add_branch(g, "C", "Comandi", "#0f766e")
    mutate.add_branch(g, "S", "Script e diagnosi", "#b45309")
    mutate.add_branch(g, "D", "Documenti", "#7c3aed")
    mutate.add_branch(g, "T", "Prova", "#16a34a")
    mutate.add_branch(g, "Q", "Cancelli", "#dc2626")

    # ---- M · Modello -------------------------------------------------------------
    mutate.add_node(g, id="M01", branch="M", type="task", mode="AFK",
                    title="Modulo memory.py: registro, file, impronta, testa rigenerabile",
                    question=(
                        f"{FONTE}\n\n"
                        "Costruisci il modello delle aree di memoria in payload/core/memory.py, "
                        "solo stdlib, sotto le 200 righe (se sfori spezza in memory.py per lettura "
                        "e impronte e memory_ops.py per le operazioni). Deve dare: la lista delle "
                        "aree del grafo (data.get('memory', [])) e quelle visibili a un nodo dato "
                        "il suo ramo (branches null = tutte); il path del file per id "
                        "(Graph.memory_dir e Graph.memory_path in config.py, accanto a tickets_dir); "
                        "la lettura del corpo (testo dopo <!-- /atlas:auto -->, normalizzato come "
                        "dice il documento) e l'impronta sha1[:12] del corpo; la generazione della "
                        "testa fra i marker da un template payload/templates/memory.{it,en}.md "
                        "(entrambe le lingue, build.py rifiuta se ne manca una); la scrittura dello "
                        "stub di un'area senza file (testa + corpo vuoto) e la rigenerazione della "
                        "testa di un file esistente senza toccare il corpo, con lo stesso meccanismo "
                        "dei ticket in docs.py; la validazione di id (^[a-z][a-z0-9-]*$), regola e "
                        "rami contro il vocabolario, che va aggiunto in config.json come "
                        "vocab.policies = [locked, append, edit] con il default in config.py. Le "
                        "stringhe destinate a un lettore stanno in strings_engine.py o "
                        "strings_docs.py con accenti veri, in entrambe le lingue. Nessun comando "
                        "CLI in questo nodo. Fatto quando tests/test_memory.py copre: visibilita' "
                        "per ramo, impronta stabile a fronte di spazi finali e fine riga diversi, "
                        "stub e rigenerazione della testa che non tocca il corpo, id e regola "
                        "invalidi rifiutati con StateError e messaggio che nomina l'area."))

    mutate.add_node(g, id="M02", branch="M", type="task", mode="AFK",
                    title="Le note di mappa diventano l'area note: schema 2 e migrazione",
                    question=(
                        f"{FONTE}\n\n"
                        "Porta SCHEMA_VERSION a 2 in store.py e migra meta.notes nell'area 'note' "
                        "(policy append, branches null, titolo dalla chiave heading.note, scopo e "
                        "uso da catalogo). Un grafo a versione 1 si legge senza errore e senza "
                        "flag; alla prima scrittura del grafo la migrazione si persiste: il file "
                        "memory/note.md nasce con una riga '- <nota>' per ogni nota, sigillato, e "
                        "meta.notes sparisce. Prima di quella scrittura chi legge le aree vede "
                        "comunque le note (decidi tu il meccanismo, per esempio un corpo "
                        "transitorio che write_stubs consuma; documentalo in un commento). "
                        "Idempotente: un grafo a versione 2 non si tocca, e la migrazione "
                        "eseguita due volte non duplica righe. mutate.create_graph crea l'area "
                        "note vuota e sigillata, e con notes=[...] la riempie; atlas new quindi "
                        "la crea di default. mutate.note_add(g, riga) resta e appende all'area "
                        "note con la firma descritta nel documento, cosi' gli script esistenti e "
                        "la skill atlas-new-graph non si rompono. Fatto quando i test coprono: "
                        "lettura di un graph.json a versione 1 con note, persistenza della "
                        "migrazione con file e sigillo, idempotenza, create_graph con e senza "
                        "note, note_add su grafo nuovo e su grafo migrato; e quando tutti i grafi "
                        "in .atlas/graphs/ di questa repo si leggono con atlas status senza "
                        "errore (non scriverli: solo lettura)."),
                    blockedBy=["M01"])

    mutate.add_node(g, id="M03", branch="M", type="task", mode="AFK",
                    title="Documenti generati: testa delle aree e sezione Note della mappa",
                    question=(
                        f"{FONTE}\n\n"
                        "Collega le aree ai documenti che Atlas rigenera, in docs.py. write_stubs "
                        "crea anche i file delle aree mancanti (testa + corpo vuoto) e ne registra "
                        "il sigillo se l'area non ne ha; rewrite_heads riscrive la testa dei file "
                        "delle aree lasciando il corpo intatto; unalignable elenca anche le aree "
                        "il cui marker <!-- /atlas:auto --> e' sparito. La sezione Note di map.md "
                        "non elenca piu' le righe di meta.notes ma le aree, una riga ciascuna: "
                        "'- **id** · regola · scopo -> memory/id.md' (link relativo alla mappa); "
                        "aggiorna docs.LISTS o il meccanismo equivalente e il sottotitolo della "
                        "sezione nei template map.it.md e map.en.md, che deve dire che le aree si "
                        "leggono a ogni nodo e si scrivono secondo la loro regola. Fatto quando "
                        "i test coprono: stub creato e sigillato, testa riscritta con corpo "
                        "intatto, marker sparito segnalato, mappa con una riga per area in "
                        "entrambe le lingue; e quando atlas render --all sui grafi di questa repo "
                        "non produce errori."),
                    blockedBy=["M02"])

    # ---- C · Comandi (catena: cli.py, report.py e strings_cli.py sono condivisi) ----
    mutate.add_node(g, id="C01", branch="C", type="task", mode="AFK",
                    title="atlas memory: list, show, add, seal",
                    question=(
                        f"{FONTE}\n\n"
                        "Aggiungi il comando 'atlas memory' con quattro forme, in cli.py e "
                        "report.py (o in un modulo dedicato se report.py sfora), stringhe in "
                        "strings_cli.py in entrambe le lingue. 'atlas memory' elenca le aree: id, "
                        "regola, rami, righe del corpo, sigillo (quando, chi) e stato del file "
                        "(sigillato, non sigillato, mancante). 'atlas memory show <id>' stampa "
                        "testa, corpo e sigillo; la riga sui nodi chiusi con sigillo precedente "
                        "la aggiunge C03, qui basta che il comando non muoia se il campo "
                        "memorySeals non esiste. 'atlas memory add <id> \"riga\"' appende "
                        "'- YYYY-MM-DD <firma>: riga' sotto la transazione del grafo, muove il "
                        "sigillo con by=firma, rifiuta su locked ed edit e rifiuta se il file non "
                        "e' sigillato, con il messaggio che dice di sigillare prima; la firma e' "
                        "l'id dell'unico nodo rivendicato dall'identita' corrente, altrimenti "
                        "whoami, altrimenti l'identita' di processo. 'atlas memory seal <id>' "
                        "ricalcola l'impronta dal file, muove il sigillo con by=whoami o identita' "
                        "e stampa quante righe sono entrate e uscite rispetto al sigillo "
                        "precedente; e' permesso su ogni regola, la distinzione persona/agente "
                        "su locked la fa il contratto. Un id inesistente esce come diagnosi che "
                        "nomina l'area, mai come traceback. Fatto quando i test coprono le "
                        "quattro forme, i rifiuti di add, la firma nei tre casi e l'uscita di "
                        "seal; e quando atlas how-to mostra il comando nell'elenco."),
                    blockedBy=["M01"])

    mutate.add_node(g, id="C02", branch="C", type="task", mode="AFK",
                    title="La memoria nel brief, nel claim e nel briefing AFK",
                    question=(
                        f"{FONTE}\n\n"
                        "Fai arrivare la memoria a chi lavora il nodo. In report.show_brief, "
                        "dopo la domanda, una sezione 'Memoria del grafo' (chiave di catalogo, "
                        "entrambe le lingue) con ogni area visibile al ramo del nodo: riga di "
                        "testa '── id · titolo · regola [· rami]', riga di scopo, riga d'uso, poi "
                        "il corpo per intero rientrato; un'area con file non sigillato o mancante "
                        "porta l'avviso sulla riga di testa; senza aree la sezione non compare. "
                        "In claims.claim (che serve sia take sia claim) scrivi in "
                        "node['claim']['memory'] il dizionario {id: seal.digest} delle aree "
                        "visibili al nodo; model.fingerprint gia' esclude claim, verifica che "
                        "resti cosi'. In providers._prompt aggiungi la frase che ordina di "
                        "lanciare prima 'atlas brief <ID>' e leggere quella sezione prima di "
                        "qualsiasi altra cosa, senza duplicare il testo delle aree nel prompt. "
                        "Fatto quando i test coprono: brief con aree filtrate per ramo, brief "
                        "senza aree, avviso su file non sigillato, claim.memory scritto a take e "
                        "a claim, prompt AFK che contiene il comando; e quando 'atlas brief' su "
                        "un nodo di questo grafo (dopo aver creato un'area di prova in una copia "
                        "temporanea del grafo, non in quello vero) stampa la sezione."),
                    blockedBy=["C01"])

    mutate.add_node(g, id="C03", branch="C", type="task", mode="AFK",
                    title="close verifica i sigilli: tre confronti, tre messaggi",
                    question=(
                        f"{FONTE}\n\n"
                        "In claims.close, prima della chiusura e dopo il controllo dell'impronta "
                        "del nodo, per ogni area visibile al nodo esegui i tre confronti del "
                        "documento nell'ordine dato. File non sigillato: rifiuto senza --force, "
                        "con il messaggio specifico della regola (edit: sigilla se e' tuo; "
                        "append: usa memory add, se hai potato sigilla; locked: non tua da "
                        "scrivere, ripristina o chiedi a una persona). Sigillo diverso da quello "
                        "in claim.memory, o area nata dopo il take: rifiuto che dice di rileggere "
                        "con atlas memory show e decidere, scavalcabile con --force come "
                        "l'impronta del nodo. Area rimossa dopo il take: ignorata. A chiusura "
                        "riuscita scrivi sul nodo memorySeals = {id: seal.digest} e stampa una "
                        "riga per area che dice invariata o cambiata. Completa 'atlas memory "
                        "show <id>' con la riga 'N nodi chiusi con un sigillo precedente: ...' "
                        "calcolata da memorySeals dei nodi chiusi. Stringhe in strings_engine.py "
                        "e strings_cli.py, entrambe le lingue, con accenti veri. Fatto quando i "
                        "test coprono i tre confronti per ciascuna delle tre regole, l'area nata "
                        "dopo il take, l'area rimossa, --force sul secondo confronto e non sul "
                        "primo, memorySeals scritto, la riga di show; e quando close --force "
                        "senza rete (lock.remote) continua a comportarsi come oggi."),
                    blockedBy=["C02"])

    # ---- S · Script e diagnosi ---------------------------------------------------
    mutate.add_node(g, id="S01", branch="S", type="task", mode="AFK",
                    title="Mutazioni memory_add, memory_remove, memory_edit e le voci di how-to",
                    question=(
                        f"{FONTE}\n\n"
                        "In mutate.py aggiungi memory_add(g, id, title, purpose, usage, policy, "
                        "branches=None), memory_remove(g, id) e memory_edit(g, id, **fields), con "
                        "le regole del documento: id conforme e unico, regola nel vocabolario, "
                        "rami esistenti, memory_remove che lascia il file su disco, memory_edit "
                        "che non tocca il sigillo. L'area creata da uno script riceve il file e "
                        "il sigillo alla rigenerazione che atlas exec fa gia' (write_stubs di "
                        "M03): verifica che succeda davvero e che l'area sia leggibile subito "
                        "dopo exec. Per ogni funzione la voce howto.mutate.<nome> in "
                        "strings_howto.py, in entrambe le lingue; in howto.dove il path memory/ "
                        "accanto a tickets/. Aggiorna il commento di esempio nel template "
                        "migration.{it,en}.py.tmpl con una riga memory_add. Fatto quando "
                        "HowTo.test_ogni_mutazione_ha_la_sua_voce_tradotta passa, i test coprono "
                        "le tre mutazioni e i loro rifiuti, e uno script di prova eseguito con "
                        "atlas exec su una copia temporanea di un grafo produce l'area con file "
                        "e sigillo."),
                    blockedBy=["M03"])

    mutate.add_node(g, id="S02", branch="S", type="task", mode="AFK",
                    title="doctor legge la memoria senza mai morire",
                    question=(
                        f"{FONTE}\n\n"
                        "In doctor.py aggiungi i cinque avvisi del documento: area dichiarata "
                        "senza file; file in memory/ non dichiarato nel grafo; marker "
                        "<!-- /atlas:auto --> sparito (via docs.unalignable); file non sigillato "
                        "(impronta diversa dal sigillo), con la regola dell'area nel messaggio; "
                        "corpo oltre 120 righe, con l'invito a potare. Ogni avviso nomina l'area "
                        "e il rimedio. doctor non muore mai: un'area con id malformato, un "
                        "sigillo senza digest, un file illeggibile diventano avvisi. Stringhe nel "
                        "catalogo che doctor gia' usa, entrambe le lingue. Fatto quando i test "
                        "coprono i cinque avvisi e i tre casi degradati, e quando atlas doctor "
                        "su tutti i grafi di questa repo esce senza traceback."),
                    blockedBy=["C03", "M03"])

    # ---- D · Documenti -----------------------------------------------------------
    mutate.add_node(g, id="D01", branch="D", type="task", mode="AFK",
                    title="Contratto e README raccontano le aree di memoria",
                    question=(
                        f"{FONTE}\n\n"
                        "Scrivi la sezione sulle aree di memoria in "
                        "payload/templates/contract.it.md e contract.en.md: il termine e cosa "
                        "non e' (nebbia, ticket, destinazione, Decisioni prese della mappa), la "
                        "regola per crearne una (un terzo nodo di un altro ramo), le tre regole "
                        "di scrittura e chi muove il sigillo, i tre confronti a close con i loro "
                        "rimedi, i comandi, le note di mappa come area note, i due limiti "
                        "dichiarati (edit concorrente, il gesto del sigillo) e il divieto per "
                        "l'agente di sigillare un'area locked, scritto con la stessa forza del "
                        "divieto di rispondere a un nodo HITL. Aggiorna README.md e README.it.md "
                        "con il comando e i flag, nella stessa struttura di sezioni. Prosa "
                        "italiana senza i marker di testo generato (niente em dash, niente frasi "
                        "nominali); l'inglese e' una traduzione fedele, non un riassunto. Fatto "
                        "quando tests/test_readme.py passa, i due contratti hanno le stesse "
                        "sezioni, e atlas how-to stampa la sezione nuova in testa."),
                    blockedBy=["C03", "S01"])

    mutate.add_node(g, id="D02", branch="D", type="task", mode="AFK",
                    title="Le skill atlas-work e atlas-new-graph conoscono la memoria",
                    question=(
                        f"{FONTE}\n\n"
                        "In payload/skills/atlas-work/SKILL.it.md e SKILL.en.md: al passo 1 la "
                        "mappa non ha piu' le righe delle note ma l'elenco delle aree; al passo 2 "
                        "take stampa anche la sezione Memoria del grafo, che si legge per intero "
                        "prima di lavorare; al passo 4 come si scrive in un'area secondo la sua "
                        "regola (memory add, editor piu' seal, mai su locked); al passo 6 cosa "
                        "fare se close rifiuta per un sigillo. In atlas-new-graph SKILL.it.md e "
                        "SKILL.en.md: l'esempio di script mostra memory_add accanto a note_add, "
                        "e una riga spiega quando un'area merita di esistere. Le due lingue "
                        "restano in pari riga per riga nella struttura. Fatto quando i test sulle "
                        "skill (frontmatter e coppie di lingua) passano e la skill installata in "
                        ".atlas/skills di questa repo, che e' un symlink al payload, mostra il "
                        "testo nuovo."),
                    blockedBy=["C03", "S01"])

    # ---- T · Prova ---------------------------------------------------------------
    mutate.add_node(g, id="T01", branch="T", type="task", mode="AFK",
                    title="e2e del ciclo memoria in sandbox",
                    question=(
                        f"{FONTE}\n\n"
                        "Estendi tests/e2e.py con il ciclo completo su un progetto finto: atlas "
                        "new crea l'area note; uno script con memory_add crea un'area append e "
                        "una edit; memory add appende e muove il sigillo; take stampa la sezione "
                        "Memoria; una modifica al file edit senza seal fa rifiutare close, seal "
                        "la sblocca; una riga aggiunta da un'altra identita' dopo il take fa "
                        "rifiutare close finche' non si passa --force; memory show elenca il "
                        "nodo chiuso con sigillo precedente; un graph.json a versione 1 con "
                        "meta.notes copiato nel progetto finto si migra al primo exec. Non "
                        "rigenerare dist/atlas in questa repo: copia la repo in una cartella "
                        "temporanea, costruisci li' con python3 build.py e lancia l'e2e da li', "
                        "con l'uscita rediretta su file. Fatto quando l'e2e passa per intero "
                        "nella copia e il diff in questa repo tocca solo tests/e2e.py e, se "
                        "serve, tests/httpfixture.py."),
                    blockedBy=["C03", "S01"])

    # ---- Q · Cancelli ------------------------------------------------------------
    mutate.add_node(g, id="Q01", branch="Q", type="task", mode="AFK",
                    title="Cancello: suite, build, e2e e rilettura da revisore ostile",
                    question=(
                        "Sei il cancello, e sei l'unico nodo che rigenera dist/atlas. Lancia "
                        "python3 -m unittest discover -s tests con l'uscita su file, poi python3 "
                        "build.py, poi python3 tests/e2e.py, e riporta i numeri veri. Poi rileggi "
                        "tutto il diff del grafo come un revisore ostile: ogni file di "
                        "payload/core sotto le 200 righe; nessuna stringa italiana fuori dai "
                        "cataloghi; accenti veri nei cataloghi e forma ASCII nei commenti; "
                        "nessun import di terze parti; i tre messaggi di rifiuto di close "
                        "leggibili da un agente AFK che non puo' chiedere; how-to, contratto, "
                        "README e skill che dicono le stesse cose con gli stessi nomi di "
                        "comando; nessun traceback da doctor, status, brief, memory su un grafo "
                        "a cui hai tolto a mano il file di un'area o corrotto il sigillo. Ripara "
                        "quel che trovi, non elencarlo. Scrivi in notes/gate-1.md il giro fatto "
                        "e i difetti riparati. Fatto quando suite, build ed e2e sono verdi e il "
                        "documento di gate esiste."),
                    blockedBy=["S02", "D01", "D02", "T01"])

    mutate.add_node(g, id="Q02", branch="Q", type="task", mode="HITL",
                    title="Prova sul campo su questo grafo e release",
                    question=(
                        "Con l'utente: crea su questo stesso grafo, con uno script, un'area "
                        "'vincoli' locked (i vincoli di lavorazione del documento di disegno) e "
                        "un'area 'decisioni-trasversali' append; migra le note di mappa "
                        "esistenti; verifica che atlas brief Q02 stampi la sezione, che memory "
                        "add firmi con Q02, che una modifica a vincoli senza seal faccia "
                        "rifiutare close e che seal la sblocchi. Guardate insieme map.md e la "
                        "dashboard. Se qualcosa non torna, la correzione si fa qui prima della "
                        "release. Poi release 0.20.0 con release.py, tag e push solo dopo ok "
                        "esplicito dell'utente, e verifica dell'impronta dell'asset pubblicato. "
                        "Fatto quando la release e' pubblicata e verificata e questo grafo ha le "
                        "sue aree sigillate."),
                    blockedBy=["Q01"])

    mutate.note_add(g, f"La fonte del disegno e' {DESIGN}: ogni nodo lo legge per intero prima di "
                       "toccare il codice.")
    mutate.note_add(g, "Chi lavora un nodo non rigenera mai dist/atlas: lo fa solo Q01. Per provare "
                       "l'e2e prima, copia la repo in una cartella temporanea e costruisci li'.")
    mutate.note_add(g, "Due nodi prendibili insieme non condividono un sorgente: gli archi della "
                       "catena C e di S sono disegnati anche per questo. Prima di prendere un nodo "
                       "guarda cosa dichiarano in artifacts quelli gia' rivendicati.")
    mutate.note_add(g, "I nodi vanno lavorati con Sonnet o piu': su un grafo precedente cinque nodi "
                       "Haiku su sette hanno richiesto un secondo giro.")

    mutate.fog_add(g, "una terza vista 'Memoria' nel pannello di destra della dashboard, con le "
                      "aree e il loro sigillo")
    mutate.fog_add(g, "filtro delle aree per tipo di nodo oltre che per ramo, se un grafo reale "
                      "lo chiede")
    mutate.fog_add(g, "un lucchetto sull'area edit durante la modifica, se due AFK finiscono "
                      "davvero per pestarsi i piedi sul glossario")
    mutate.fog_add(g, "atlas memory add da Telegram, per appuntare una decisione dal telefono")
