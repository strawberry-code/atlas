"""Messaggi di cli.py: help di argparse, e quel che stampano i comandi.

Parte del catalogo del motore: vedi strings.py per il meccanismo di lookup,
strings_engine.py, strings_docs.py e strings_howto.py per il resto del catalogo.
"""
from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    # --- argparse: descrizione e help ---
    "parser.description": {"it": "Harness di task a grafo con runner Automata.",
                            "en": "Graph-based task harness with the Automata runner."},
    "opt.graph": {"it": "slug del grafo, se non è quello attivo",
                  "en": "graph slug, if not the active one"},
    "parser.slug_al_posto_del_comando": {
        "it": "\n'{slug}' è un grafo di questo progetto, non un comando.\n"
              "Il grafo si indica con -g: 'atlas render -g {slug}',\n"
              "oppure si rende attivo una volta sola: 'atlas use {slug}'.",
        "en": "\n'{slug}' is a graph of this project, not a command.\n"
              "Pick the graph with -g: 'atlas render -g {slug}',\n"
              "or make it the active one once: 'atlas use {slug}'."},
    "help.status": {"it": "frontiera, lucchetti, avanzamento", "en": "frontier, locks, progress"},
    "help.next": {"it": "la frontiera ordinata per impatto", "en": "the frontier ranked by impact"},
    "help.graphs": {"it": "i grafi di questo progetto", "en": "the graphs in this project"},
    "help.use": {"it": "rende attivo un grafo", "en": "makes a graph active"},
    "help.show": {"it": "scheda di un nodo", "en": "a node's card"},
    "help.brief": {"it": "il pacchetto di contesto per lavorare un nodo",
                   "en": "the context package to work a node"},
    "help.claim": {"it": "rivendica un nodo per questa sessione", "en": "claims a node for this session"},
    "help.take": {"it": "rivendica un nodo e ne stampa subito il contesto",
                  "en": "claims a node and prints its context right away"},
    "help.release": {"it": "restituisce un nodo alla frontiera", "en": "returns a node to the frontier"},
    "help.close": {"it": "chiude un nodo con la sua sintesi", "en": "closes a node with its summary"},
    "help.amend": {"it": "corregge artefatti, costo o sintesi di un nodo già chiuso",
                   "en": "fixes artifacts, cost or summary of an already closed node"},
    "help.ask": {"it": "registra una domanda non bloccante", "en": "records a non-blocking question"},
    "help.asks": {"it": "mostra le domande aperte", "en": "shows open questions"},
    "help.answer": {"it": "risponde a una domanda registrata", "en": "answers a recorded question"},
    "help.identity": {"it": "identità che tiene il lucchetto, vince su ATLAS_IDENTITY",
                      "en": "identity holding the lock, overrides ATLAS_IDENTITY"},
    "help.render_all": {"it": "rigenera tutti i grafi del progetto, non solo quello attivo",
                        "en": "regenerates every graph in the project, not just the active one"},
    "render.tutti": {"it": "  grafi rigenerati: {n}", "en": "  graphs regenerated: {n}"},
    "help.fog": {"it": "appunta ciò che è emerso e non ha ancora un nodo",
                 "en": "notes down what came up and has no node yet"},
    "help.assign": {"it": "assegna nodi a una o più persone",
                    "en": "assigns nodes to one or more people"},
    "help.unassign": {"it": "toglie gli assegnatari dai nodi",
                      "en": "removes the assignees from nodes"},
    "help.assign_nome": {"it": "nome della persona, o più nomi separati da virgola",
                         "en": "the person's name, or several names separated by commas"},
    "help.assign_add": {"it": "aggiunge le persone a quelle che il nodo ha già",
                        "en": "adds the people to the ones the node already has"},
    "help.assign_remove": {"it": "toglie solo le persone indicate, lasciando le altre",
                           "en": "removes only the given people, leaving the others"},
    "help.assign_nodi": {"it": "uno o più id di nodo", "en": "one or more node ids"},
    "help.assign_branch": {"it": "estende ai nodi che il ramo ha adesso",
                           "en": "extends to the nodes the branch has now"},
    "help.assign_me": {"it": "assegna a chi dice 'atlas whoami'",
                       "en": "assigns to whoever 'atlas whoami' says"},
    "help.whoami": {"it": "chi lavora da questa copia del progetto",
                    "en": "who works from this copy of the project"},
    "help.whoami_nome": {"it": "il nome da ricordare, vuoto per leggerlo",
                         "en": "the name to remember, empty to read it"},
    "help.whoami_clear": {"it": "dimentica il nome", "en": "forgets the name"},
    "help.render": {"it": "rigenera ticket, mappa e dashboard",
                    "en": "regenerates tickets, map and dashboard"},
    "help.serve": {"it": "serve la dashboard su un server locale, viva",
                   "en": "serves the dashboard on a local server, live"},
    "help.run": {"it": "avvia un run Automata con parallelismo esplicito",
                 "en": "starts an Automata run with explicit parallelism"},
    "help.run_status": {"it": "diagnosi dello stato persistente dell'ultimo run",
                         "en": "diagnoses the persistent state of the last run"},
    "help.run_log": {"it": "cronologia persistente degli eventi dell'ultimo run",
                      "en": "persistent event log of the last run"},
    "help.run_parallelism": {"it": "limite obbligatorio per questo run (1 = seriale; >1 = parallelo limitato)",
                              "en": "required for this run (1 = serial; >1 = bounded parallelism)"},
    "report.run_nessuno": {"it": "  nessun run Automata persistito",
                            "en": "  no persisted Automata run"},
    "report.run_titolo": {"it": "  run {id} · stato={status} · parallelism={parallelism}",
                           "en": "  run {id} · status={status} · parallelism={parallelism}"},
    "report.run_riga": {"it": "  run Automata: stato={status} · id={id}",
                         "en": "  Automata run: status={status} · id={id}"},
    "report.run_motivo": {"it": "    motivo: {reason}", "en": "    reason: {reason}"},
    "report.run_prossimo": {"it": "    prossimo tentativo: {at}",
                             "en": "    next attempt: {at}"},
    "report.run_frontiera": {"it": "    frontiera persistita: {ids}",
                              "en": "    persisted frontier: {ids}"},
    "report.run_blocco": {"it": "    blocco residuo: {node} attende {blockers}",
                           "en": "    residual blocker: {node} waits for {blockers}"},
    "report.run_log_titolo": {"it": "  eventi run {id} ({n})", "en": "  run events {id} ({n})"},
    "help.serve_port": {"it": "porta del server (0 = fissa per questo grafo, ricade su una libera se occupata)",
                        "en": "server port (0 = fixed for this graph, falls back to a free one if taken)"},
    "help.serve_no_open": {"it": "non aprire il browser all'avvio",
                           "en": "do not open the browser on startup"},
    "help.merge_graph": {"it": "fonde tre versioni di graph.json per id di nodo (driver per git)",
                         "en": "merges three graph.json versions by node id (git driver)"},
    "help.merge_base": {"it": "l'antenato comune, %%O", "en": "the common ancestor, %%O"},
    "help.merge_ours": {"it": "la nostra versione, che viene riscritta, %%A",
                        "en": "our version, which gets rewritten, %%A"},
    "help.merge_theirs": {"it": "la versione dell'altro ramo, %%B",
                          "en": "the other branch's version, %%B"},
    "help.conflicts": {"it": "i conflitti di merge irrisolti del grafo attivo",
                       "en": "the active graph's unresolved merge conflicts"},
    "help.conflicts_resolve": {"it": "dichiara risolti i conflitti e toglie il campo dal grafo",
                               "en": "declares conflicts resolved and removes the field from the graph"},
    "help.new": {"it": "crea un grafo nuovo", "en": "creates a new graph"},
    "help.new_slug": {"it": "nome tecnico del grafo, in kebab-case (la data di creazione "
                            "viene anteposta in automatico: YYMMDD-nome)",
                      "en": "technical name of the graph, kebab-case (the creation date "
                            "is prefixed automatically: YYMMDD-name)"},
    "default.destination": {"it": "Da scrivere: dove si arriva quando questo grafo è finito.",
                             "en": "To be written: where this graph leads when it's done."},
    "help.new_script": {"it": "crea uno script di mutazione numerato",
                        "en": "creates a numbered mutation script"},
    "help.exec": {"it": "esegue uno o più script di mutazione",
                  "en": "runs one or more mutation scripts"},
    "help.renumber": {"it": "rinumera gli script di mutazione",
                      "en": "renumbers the mutation scripts"},
    "help.renumber_file": {"it": "gli script da spostare in coda, nell'ordine indicato",
                           "en": "the scripts to move to the end, in the given order"},
    "help.renumber_dry": {"it": "mostra le rinomine senza farle",
                          "en": "shows the renames without doing them"},
    "help.validate": {"it": "verifica la forma dei grafi", "en": "checks the graphs' shape"},
    "help.doctor": {"it": "stato dell'installazione", "en": "installation status"},
    "help.how_to": {"it": "tutto quel che serve per lavorare qui, in un comando solo",
                    "en": "everything needed to work here, in a single command"},

    # --- refresh/commit ---
    "refresh.ticket_creati": {"it": "  {n} ticket creati in {dir}", "en": "  {n} tickets created in {dir}"},
    "refresh.ticket_riallineati": {"it": "  {n} ticket riallineati al grafo",
                                   "en": "  {n} tickets realigned to the graph"},
    "commit.fatto": {"it": "  commit: {messaggio}", "en": "  commit: {messaggio}"},

    # --- cmd_new ---
    "new.creato": {"it": "  grafo '{slug}' creato in {dir} e reso attivo.",
                   "en": "  graph '{slug}' created in {dir} and made active."},
    "new.suggerimento": {"it": "  Ora popolalo con uno script: 'atlas new-script primo-disegno'.",
                         "en": "  Now populate it with a script: 'atlas new-script first-draft'."},

    # --- cmd_exec ---
    "exec.script_assente": {"it": "{script} non esiste", "en": "{script} does not exist"},
    "exec.senza_run": {"it": "{nome} non definisce run(g)", "en": "{nome} does not define run(g)"},
    "exec.morto": {"it": "{nome} è morto durante l'esecuzione: {tipo}: {errore}\n"
                         "  Il grafo non è stato toccato.",
                   "en": "{nome} died while running: {tipo}: {errore}\n"
                         "  The graph was not touched."},
    "exec.applicato": {"it": "  {nome} applicato a '{slug}' · {n} nodi",
                       "en": "  {nome} applied to '{slug}' · {n} nodes"},

    # --- cmd_renumber ---
    "renumber.riga": {"it": "  {da} → {a}", "en": "  {da} → {a}"},
    "renumber.fatto": {"it": "  {n} script rinumerati", "en": "  {n} scripts renumbered"},
    "renumber.niente": {"it": "  la numerazione è già lineare: niente da fare",
                        "en": "  the numbering is already linear: nothing to do"},
    "renumber.non_numerato": {"it": "«{nome}» non è uno script numerato di .atlas/scripts/",
                              "en": "'{nome}' is not a numbered script in .atlas/scripts/"},

    # --- cmd_validate ---
    "validate.ok": {"it": "  {slug}: forma valida", "en": "  {slug}: valid shape"},

    # --- cmd_doctor ---
    "doctor.radice": {"it": "  radice   {root}", "en": "  root     {root}"},
    "doctor.progetto": {"it": "  progetto {progetto} · {root}", "en": "  project  {progetto} · {root}"},
    "doctor.versione": {"it": "  versione {versione}", "en": "  version  {versione}"},
    "doctor.grafi": {"it": "  grafi    {grafi}", "en": "  graphs   {grafi}"},
    "doctor.nessuno": {"it": "nessuno", "en": "none"},
    "doctor.skill": {"it": "  skill    {stato}", "en": "  skills   {stato}"},
    "doctor.skill_ok": {"it": "tutte collegate", "en": "all linked"},
    "doctor.skill_mancanti": {"it": "mancano {elenco}", "en": "missing {elenco}"},
    "doctor.skill_sorgente_assente": {"it": "{dir} non esiste: reinstalla con 'atlas install'",
                                     "en": "{dir} is missing: reinstall with 'atlas install'"},
    "doctor.hook": {"it": "  hook     {stato}", "en": "  hook     {stato}"},
    "doctor.hook_ok": {"it": "registrato", "en": "registered"},
    "doctor.hook_assente": {"it": "assente", "en": "absent"},
    "doctor.git": {"it": "  git      {presente} · commit alla chiusura: {commit}\n",
                   "en": "  git      {presente} · commit on close: {commit}\n"},
    "doctor.grafo_titolo": {"it": "  {slug}:", "en": "  {slug}:"},
    "doctor.non_converge": {"it": "terminali che non confluiscono nel finale {end}: {elenco}. Un grafo "
                                   "di solito converge in un nodo end unico: agganciali con uno script "
                                   "di mutazione, o mettili fuori scopo.",
                            "en": "terminal nodes that don't flow into the final {end}: {elenco}. A graph "
                                  "usually converges into a single end node: link them with a mutation "
                                  "script, or drop them out of scope."},
    "doctor.lucchetto_fermo": {"it": "{id} è rivendicato ma {stato}", "en": "{id} is claimed but {stato}"},
    "doctor.dashboard_stantia": {"it": "la dashboard è più vecchia dell'ultima modifica al grafo: esegui 'atlas render'",
                                 "en": "the dashboard is older than the last change to the graph: run 'atlas render'"},
    "doctor.ticket_scollegato": {"it": "in questi ticket manca il confine {mark} fra la parte generata e "
                                        "il testo scritto a mano: {elenco}. La loro testa non si riallinea "
                                        "più al grafo, e va rimessa a mano o ricreata cancellando il file.",
                                 "en": "these tickets have lost the {mark} boundary between the generated part "
                                       "and the hand-written text: {elenco}. Their head no longer realigns to "
                                       "the graph, and must be fixed by hand or recreated by deleting the file."},
    "doctor.autoverifica": {"it": "{id}, rivendicato da {chi}, verifica nodi che {chi} stessa ha chiuso: {elenco}",
                            "en": "{id}, claimed by {chi}, verifies nodes that {chi} closed themself: {elenco}"},
    "doctor.ambito_toccato": {"it": "{id} è chiuso ma questi artifacts sono stati modificati dopo: {elenco}. "
                                     "Verifica che non sia una scrittura fuori scopo.",
                              "en": "{id} is closed but these artifacts were modified afterwards: {elenco}. "
                                    "Check it isn't an out-of-scope write."},
    "doctor.artefatti_mancanti": {"it": "{id} è chiuso ma questi artifacts mancano dal disco: {elenco}. "
                                          "Ripristinali o correggi la contabilità.",
                                  "en": "{id} is closed but these artifacts are missing from disk: {elenco}. "
                                        "Restore them or fix the bookkeeping."},
    "doctor.artefatti_non_tracciati": {"it": "{id} è chiuso ma questi artifacts non sono tracciati da Git: {elenco}. "
                                               "Aggiungili o correggi la contabilità.",
                                       "en": "{id} is closed but these artifacts are not tracked by Git: {elenco}. "
                                             "Add them or fix the bookkeeping."},
    "doctor.artefatto_non_ispezionabile": {"it": "avviso: non riesco a ispezionare l'artifact di {id}, path non valido "
                                                   "{path} ({errore}). Continuo gli altri controlli.",
                                             "en": "warning: cannot inspect {id}'s artifact, invalid path {path} "
                                                   "({errore}). Continuing with the other checks."},
    "doctor.conflitto": {"it": "conflitto di merge irrisolto su {nodo}: {campo} ({tipo})",
                         "en": "unresolved merge conflict on {nodo}: {campo} ({tipo})"},
    "doctor.conflitti_rimedio": {"it": "conflitti irrisolti: correggi graph.json a mano e poi "
                                       "dichiarali risolti con 'atlas conflicts --resolve'",
                                "en": "unresolved conflicts: fix graph.json by hand, then "
                                      "declare them resolved with 'atlas conflicts --resolve'"},
    "si": {"it": "sì", "en": "yes"},
    "no": {"it": "no", "en": "no"},

    # --- cmd_conflicts ---
    "conflicts.nessuno": {"it": "  nessun conflitto irrisolto", "en": "  no unresolved conflicts"},
    "conflicts.intestazione": {"it": "  conflitti irrisolti di '{slug}':",
                               "en": "  unresolved conflicts of '{slug}':"},
    "conflicts.riga": {"it": "    {nodo}: {campo} ({tipo})", "en": "    {nodo}: {campo} ({tipo})"},
    "conflicts.rimedio": {"it": "  Correggi graph.json a mano scegliendo la parte giusta, poi "
                                "'atlas conflicts --resolve'.",
                          "en": "  Fix graph.json by hand picking the right side, then "
                                "'atlas conflicts --resolve'."},
    "conflicts.risolta_riga": {"it": "  dichiarato risolto: {nodo}: {campo} ({tipo})",
                               "en": "  declared resolved: {nodo}: {campo} ({tipo})"},
    "conflicts.risolti": {"it": "  conflitti dichiarati risolti: il campo è stato tolto da graph.json",
                          "en": "  conflicts declared resolved: the field was removed from graph.json"},

    # --- dispatch ---
    "use.attivo": {"it": "  grafo attivo: {slug}", "en": "  active graph: {slug}"},
    "close.fatto": {"it": "  {id} chiuso · riga aggiunta in map.md", "en": "  {id} closed · line added to map.md"},
    "amend.fatto": {"it": "  {id} corretto · campi riscritti a mano: {campi}",
                    "en": "  {id} amended · fields rewritten by hand: {campi}"},
    "close.artefatti_dedotti": {"it": "  artefatti dedotti da git ({n}): {elenco}",
                                "en": "  artifacts deduced from git ({n}): {elenco}"},
    "ask.fatto": {"it": "  {id} registrata per {origin} · autore {author}",
                  "en": "  {id} recorded for {origin} · author {author}"},
    "answer.fatto": {"it": "  {id} chiusa · domanda di {author}",
                     "en": "  {id} answered · question by {author}"},
    "answer.divergente": {"it": "  risposta divergente: riesamina i nodi chiusi dopo la domanda:",
                           "en": "  divergent answer: review nodes closed after the question:"},
    "answer.riesame_riga": {"it": "    {id}  {title}", "en": "    {id}  {title}"},
    "asks.nessuna": {"it": "  nessuna domanda aperta", "en": "  no open questions"},
    "asks.titolo": {"it": "  domande aperte:", "en": "  open questions:"},
    "asks.riga": {"it": "    {id} · origine {origin} · autore {author}",
                  "en": "    {id} · origin {origin} · author {author}"},
    "asks.assunzione": {"it": "      assunzione: {assumption}",
                        "en": "      assumption: {assumption}"},
    "help.drift": {"it": "diagnosi degli archi mancanti senza mutare il grafo",
                    "en": "diagnoses missing edges without mutating the graph"},
    # Il canale con cui l'attrito di chi usa Atlas torna a chi lo scrive. Stampato
    # dove un agente ha appena guardato indietro al proprio giro (close) e dove sta
    # gia' diagnosticando un guasto (doctor).
    "attrito.issue": {"it": "\n  Attrito con Atlas in questo giro? Aprine una issue:\n"
                            "  https://github.com/strawberry-code/atlas/issues",
                      "en": "\n  Friction with Atlas this round? Open an issue:\n"
                            "  https://github.com/strawberry-code/atlas/issues"},
    "claim.fatto": {"it": "  {id} rivendicato · ticket in {path}", "en": "  {id} claimed · ticket at {path}"},
    "release.fatto": {"it": "  {id} tornato alla frontiera", "en": "  {id} back on the frontier"},
    "fog.fatto": {"it": "  appuntato nella nebbia", "en": "  noted in the fog"},
    "fog.per": {"it": "per {id}: {riga}", "en": "for {id}: {riga}"},
    "fog.prefisso_ripetuto": {"it": "  il prefisso per {id} era già nel testo: scritto una volta sola",
                              "en": "  the prefix for {id} was already in the text: written only once"},
    "fog.riga_mancante": {"it": "una voce di nebbia richiede del testo: 'atlas fog \"...\"'",
                          "en": "a fog entry needs some text: 'atlas fog \"...\"'"},
    "assign.fatto": {"it": "  assegnati a {nome}: {elenco}",
                     "en": "  assigned to {nome}: {elenco}"},
    "assign.gia_cosi": {"it": "  erano già tutti di {nome}: niente da cambiare",
                        "en": "  they were all {nome}'s already: nothing to change"},
    "assign.tolti": {"it": "  {nome} tolto da: {elenco}",
                     "en": "  {nome} removed from: {elenco}"},
    "assign.gia_fuori": {"it": "  nessuno di questi era di {nome}",
                         "en": "  none of these belonged to {nome}"},
    "unassign.fatto": {"it": "  tornati senza assegnatario: {elenco}",
                       "en": "  left with no assignee: {elenco}"},
    "unassign.gia_liberi": {"it": "  nessuno di questi era assegnato",
                            "en": "  none of these was assigned"},
    "assign.senza_nome": {"it": "manca la persona: 'atlas assign <nome> <ID>', "
                                "oppure '--me' se hai scritto 'atlas whoami <nome>'",
                          "en": "the person is missing: 'atlas assign <name> <ID>', "
                                "or '--me' if you've run 'atlas whoami <name>'"},
    "assign.senza_whoami": {"it": "--me non sa chi sei: scrivi prima 'atlas whoami <nome>'",
                            "en": "--me doesn't know who you are: run 'atlas whoami <name>' first"},
    "whoami.sono": {"it": "  {nome}", "en": "  {nome}"},
    "whoami.nessuno": {"it": "  nessun nome qui: 'atlas whoami <nome>' per dirlo",
                       "en": "  no name here: 'atlas whoami <name>' to set one"},
    "whoami.scritto": {"it": "  sei {nome} · scritto in {path}, non versionato",
                       "en": "  you are {nome} · written to {path}, not versioned"},
    "whoami.dimenticato": {"it": "  nome dimenticato", "en": "  name forgotten"},

    # --- serve.py ---
    "serve.avviato": {"it": "  dashboard su {url} (grafo {slug}); Ctrl-C per fermare",
                      "en": "  dashboard at {url} (graph {slug}); Ctrl-C to stop"},
    "serve.grafo_mancante": {"it": "il grafo non si legge ancora",
                             "en": "the graph is not readable yet"},
    "serve.porta_occupata": {"it": "  porta {porta} occupata, ne uso una libera (il tema del browser potrebbe non sopravvivere al prossimo riavvio)",
                             "en": "  port {porta} in use, picking a free one instead (the browser's theme may not survive the next restart)"},

    # --- hooks/session_end.py ---
    "hook.rivendicato": {"it": "Atlas: {elenco} resta rivendicato. "
                               "Alla prossima sessione chiudilo con 'atlas close', oppure rilascialo.",
                         "en": "Atlas: {elenco} is still claimed. "
                               "Next session, close it with 'atlas close', or release it."},
}
