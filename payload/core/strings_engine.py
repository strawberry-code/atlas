"""Messaggi d'errore del motore: claims.py, mutate.py, config.py.

Parte del catalogo del motore: vedi strings.py per il meccanismo di lookup,
strings_cli.py e strings_docs.py per il resto del catalogo.
"""
from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "automata.parallelism_invalid": {
        "it": "parallelism deve essere un intero positivo",
        "en": "parallelism must be a positive integer"},
    "automata.serial": {"it": "seriale", "en": "serial"},
    "automata.limited": {"it": "parallelo limitato", "en": "limited parallelism"},
    "automata.configured": {
        "it": "  run Automata avviato: parallelism={parallelism} · {mode} · model vuoto = Codex Luna, fallback Claude Sonnet",
        "en": "  Automata run started: parallelism={parallelism} · {mode} · empty model = Codex Luna, Claude Sonnet fallback"},
    "automata.active_claims": {
        "it": "run non terminabile: nodi ancora in lavorazione: {ids}",
        "en": "run cannot terminate: nodes still in progress: {ids}"},
    "automata.blocked": {
        "it": "run bloccato: nessun nodo eleggibile, restano aperti: {ids}",
        "en": "run blocked: no eligible node, open nodes remain: {ids}"},
    "automata.hitl": {
        "it": "nodo {id} HITL: un run AFK non puo' rispondere al posto dell'umano",
        "en": "node {id} is HITL: an AFK run cannot answer for the human"},
    "automata.not_terminal": {
        "it": "il nodo {id} non e' terminale dopo l'attesa: stato '{status}'",
        "en": "node {id} is not terminal after waiting: status '{status}'"},
    "automata.adapter_outcome": {
        "it": "adapter del nodo {id} ha terminato con esito '{status}': {detail}",
        "en": "adapter for node {id} terminated with '{status}': {detail}"},
    "automata.already_started": {
        "it": "il nodo {id} e' gia' stato avviato da questo run",
        "en": "node {id} was already started by this run"},
    "automata.retry_active": {
        "it": "retry non avviato: il nodo {id} ha ancora un agente attivo",
        "en": "retry not started: node {id} still has an active agent"},
    "automata.retry_exhausted": {
        "it": "run non riuscito: retry esauriti o errore permanente sui nodi: {ids}. "
              "Se la causa e' risolta, rimuovi la voce del nodo (o il file) da {path} "
              "prima di rilanciare: il budget resta segnato esaurito da un run precedente.",
        "en": "run failed: retries exhausted or permanent error on nodes: {ids}. "
              "If the cause is fixed, remove the node's entry (or the file) at {path} "
              "before relaunching: the budget stays marked exhausted from a previous run."},
    "automata.invalid_termination": {
        "it": "run non terminabile: la frontiera e' vuota ma restano nodi non terminali",
        "en": "run cannot terminate: the frontier is empty but non-terminal nodes remain"},
    # --- claims.py ---
    "claim.non_aperto": {"it": "{id} non è aperto: sta a '{stato}'",
                         "en": "{id} is not open: it's at '{stato}'"},
    "claim.bloccato": {"it": "{id} è bloccato da {bloccanti}", "en": "{id} is blocked by {bloccanti}"},
    "claim.tetto": {"it": "questa sessione tiene già {tenuti}: il tetto è {tetto} per sessione.\n"
                          "  Rilascia con 'atlas release {primo}', apri un'altra sessione,\n"
                          "  oppure forza con --force se sai cosa stai facendo.",
                    "en": "this session already holds {tenuti}: the cap is {tetto} per session.\n"
                          "  Release with 'atlas release {primo}', open another session,\n"
                          "  or force with --force if you know what you're doing."},
    "release.non_rivendicato": {"it": "{id} non è rivendicato: sta a '{stato}'",
                                "en": "{id} is not claimed: it's at '{stato}'"},
    "close.gia_chiuso": {"it": "{id} è già chiuso", "en": "{id} is already closed"},
    "close.altra_sessione": {"it": "{id} è rivendicato da un'altra sessione viva ({owner})",
                             "en": "{id} is claimed by another live session ({owner})"},
    "close.risposta_vuota": {"it": "la sezione Risposta di {file} è vuota.\n"
                                   "  Scrivila prima di chiudere, oppure usa --force se il nodo\n"
                                   "  si chiude senza risposta perché è diventato irrilevante.",
                             "en": "the Answer section of {file} is empty.\n"
                                   "  Write it before closing, or use --force if the node\n"
                                   "  closes without an answer because it became irrelevant."},
    "close.artifacts_non_dedotti": {"it": "artefatti non dedotti: più nodi sono in lavorazione insieme,\n"
                                          "  dichiarali con --artefatti",
                                    "en": "artifacts not deduced: several nodes are in progress at once,\n"
                                          "  declare them with --artefatti"},
    "close.artifacts_required": {"it": "non posso chiudere: la deduzione degli artefatti non è attendibile.\n"
                                        "  {dettaglio}\n"
                                        "  Scegli esplicitamente con --artefatti, anche senza argomenti per dichiarare il vuoto.",
                                  "en": "cannot close: artifact deduction is not reliable.\n"
                                        "  {dettaglio}\n"
                                        "  Choose explicitly with --artefatti, even without arguments to declare none."},
    "close.artifacts_finestra_condivisa": {"it": "artefatti non dedotti: {altro} è stato chiuso o rilasciato\n"
                                                 "  mentre questo nodo era in lavorazione, e i file dedotti\n"
                                                 "  sarebbero anche i suoi. Dichiarali con --artefatti",
                                           "en": "artifacts not deduced: {altro} was closed or released while\n"
                                                 "  this node was in progress, so the deduced files would be\n"
                                                 "  its files too. Declare them with --artefatti"},
    "close.artifacts_remoto_rete": {"it": "artefatti non dedotti: il lucchetto remoto non è raggiungibile\n"
                                          "  e non posso escludere che altre macchine abbiano lavorato in\n"
                                          "  questa finestra. Dichiarali con --artefatti",
                                    "en": "artifacts not deduced: the remote lock is unreachable and I\n"
                                          "  can't rule out that other machines worked in this window.\n"
                                          "  Declare them with --artefatti"},
    "close.artifacts_presa_illeggibile": {"it": "artefatti non dedotti: l'istante di presa di {id} non si legge\n"
                                                "  ('{at}'). Correggilo in graph.json oppure dichiara i file\n"
                                                "  con --artefatti",
                                          "en": "artifacts not deduced: the claim timestamp of {id} is unreadable\n"
                                                "  ('{at}'). Fix it in graph.json or declare the files with\n"
                                                "  --artefatti"},
    "close.artifacts_non_tracciati": {"it": "avviso: questi artefatti esistono ma non sono tracciati da Git: {elenco}.\n"
                                               "  Aggiungili a Git o correggi la contabilità; la chiusura prosegue.",
                                       "en": "warning: these artifacts exist but are not tracked by Git: {elenco}.\n"
                                               "  Add them to Git or fix the bookkeeping; closing continues."},
    "close.artifacts_mancanti": {"it": "avviso: questi artefatti non esistono nel progetto: {elenco}.\n"
                                          "  Controlla i path dichiarati; la chiusura prosegue.",
                                  "en": "warning: these artifacts do not exist in the project: {elenco}.\n"
                                          "  Check the declared paths; closing continues."},
    "close.artifacts_ambiguous": {"it": "artefatti ambigui rifiutati: {elenco}.\n"
                                             "  Passa un solo path per --artefatti e ripeti il flag; non usare spazi o virgole nel token.",
                                   "en": "ambiguous artifacts rejected: {elenco}.\n"
                                             "  Pass one path per --artefatti and repeat the flag; do not use spaces or commas in the token."},
    "close.artifacts_cli_usage": {"it": "Passa un solo path per --artefatti e ripeti il flag per ogni file.",
                                   "en": "Pass one path per --artefatti and repeat the flag for each file."},
    "close.premessa_scaduta": {"it": "{id} è cambiato da quando l'hai preso.\n"
                                     "  La tua risposta potrebbe poggiare su una premessa che non c'è più:\n"
                                     "  rileggi il nodo con 'atlas show {id}' e richiudi, oppure usa --force\n"
                                     "  se il cambiamento non tocca quello che hai scritto.",
                               "en": "{id} changed since you claimed it.\n"
                                     "  Your answer may rest on a premise that no longer holds:\n"
                                     "  re-read the node with 'atlas show {id}' and close again, or use\n"
                                     "  --force if the change doesn't affect what you wrote."},
    "claim.remoto_tenuto": {"it": "{id} è in lavorazione su un'altra macchina ({host}) "
                                  "con un lease fresco: aspetta che scada, o forza.",
                            "en": "{id} is being worked on another machine ({host}) "
                                  "with a fresh lease: wait for it to expire, or force."},
    "claim.remoto_rete": {"it": "il lucchetto remoto non è raggiungibile: niente è stato "
                                "scritto su {id}. Riprova, oppure togli lock.remote dalla "
                                "config per lavorare solo in locale.",
                          "en": "the remote lock is unreachable: nothing was written to {id}. "
                                "Retry, or remove lock.remote from the config to work local-only."},
    "claim.remoto_rete_rinnovo": {"it": "remote non raggiungibile: il rinnovo del lucchetto "
                                          "è rimandato, mostro lo stato locale",
                                 "en": "remote unreachable: lock renewal is postponed, "
                                       "showing local state"},
    "claim.remoto_gara": {"it": "il lucchetto remoto di {id} è cambiato nel frattempo: riprova.",
                          "en": "the remote lock of {id} changed meanwhile: retry."},
    "close.remoto_tenuto": {"it": "{id} è rivendicato da un'altra macchina ({host}) con un "
                                  "lease fresco: aspetta la scadenza o usa --force.",
                            "en": "{id} is claimed by another machine ({host}) with a fresh "
                                  "lease: wait for it to expire or use --force."},
    "close.remoto_rete": {"it": "il lucchetto remoto non è raggiungibile: {id} non è stato "
                                "chiuso. Riprova, oppure usa --force.",
                          "en": "the remote lock is unreachable: {id} was not closed. Retry, "
                                "or use --force."},
    "close.remoto_rete_rilascio": {"it": "non sono riuscito a liberare la serratura remota "
                                         "di {id}: scadrà da sola.",
                                   "en": "couldn't release the remote lock of {id}: it will "
                                         "expire on its own."},
    "release.remoto_non_tuo": {"it": "{id} è tenuto da un'altra macchina ({host}) con un "
                                     "lease fresco: non si può rilasciare qui.",
                               "en": "{id} is held by another machine ({host}) with a fresh "
                                     "lease: it can't be released here."},
    "release.remoto_rete": {"it": "il lucchetto remoto non è raggiungibile: {id} non è stato "
                                  "rilasciato. Riprova, oppure togli lock.remote dalla config.",
                            "en": "the remote lock is unreachable: {id} was not released. "
                                  "Retry, or remove lock.remote from the config."},
    "release.remoto_gara": {"it": "il lucchetto remoto di {id} è cambiato nel frattempo: riprova.",
                            "en": "the remote lock of {id} changed meanwhile: retry."},

    # --- mutate.py ---
    "mutate.id_duplicato": {"it": "id duplicato: {id}", "en": "duplicate id: {id}"},
    "mutate.ramo_inesistente": {"it": "{id} sta su un ramo inesistente: {branch}",
                               "en": "{id} is on a branch that doesn't exist: {branch}"},
    "mutate.vocab_non_valido": {"it": "{id} ha {chiave}='{valore}', fuori da {ammessi}",
                               "en": "{id} has {chiave}='{valore}', outside {ammessi}"},
    "mutate.modello_non_valido": {"it": "{id} ha un modello non valido: serve testo non vuoto",
                                   "en": "{id} has an invalid model: non-empty text is required"},
    "model.nodo_inesistente": {"it": "{id} non esiste nel grafo", "en": "{id} does not exist in the graph"},
    "model.ciclo": {"it": "ciclo di dipendenze su {id}", "en": "dependency cycle on {id}"},
    "mutate.dipendenza_inesistente": {"it": "{id} è bloccato da {dep}, che non esiste",
                                     "en": "{id} is blocked by {dep}, which doesn't exist"},
    "mutate.amend_non_chiuso": {"it": "{id} non è chiuso: sta a '{stato}'.\n"
                                      "  Su un nodo ancora aperto la contabilità la scrive 'atlas close'.",
                                "en": "{id} is not closed: it's at '{stato}'.\n"
                                      "  On a node still open the bookkeeping is written by 'atlas close'."},
    "mutate.amend_senza_campi": {"it": "niente da correggere su {id}: passa almeno uno fra\n"
                                       "  --artefatti, --costo e --sintesi",
                                 "en": "nothing to fix on {id}: pass at least one of\n"
                                       "  --artefatti, --costo and --sintesi"},
    "mutate.auto_dipendenza": {"it": "{id} dipende da se stesso", "en": "{id} depends on itself"},
    "mutate.ask_hitl": {"it": "non posso registrare una domanda su {id}: il nodo è HITL; serve l'umano",
                        "en": "cannot record a question on {id}: the node is HITL; it needs the human"},
    "mutate.ask_campo_vuoto": {"it": "il campo {campo} non può essere vuoto",
                                "en": "{campo} cannot be empty"},
    "mutate.domanda_inesistente": {"it": "la domanda {id} non esiste", "en": "question {id} does not exist"},
    "mutate.domanda_gia_risposta": {"it": "la domanda {id} ha già una risposta",
                                     "en": "question {id} already has an answer"},
    "mutate.domande_non_lista": {"it": "il registro delle domande non è una lista",
                                  "en": "the question ledger is not a list"},
    "mutate.domanda_invalida": {"it": "domanda non valida: {dettaglio}",
                                 "en": "invalid question: {dettaglio}"},
    "mutate.nome_non_valido": {"it": "'{nome}' non è un nome utilizzabile: serve del testo "
                                     "su una riga sola, al massimo {max} caratteri",
                               "en": "'{nome}' is not a usable name: it takes some text "
                                     "on a single line, at most {max} characters"},
    "mutate.ramo_bersaglio": {"it": "il ramo {branch} non esiste. Ci sono: {elenco}",
                              "en": "branch {branch} does not exist. There are: {elenco}"},
    "mutate.assegna_senza_bersaglio": {"it": "nessun nodo indicato: passa degli id, "
                                             "oppure --branch <ramo>",
                                       "en": "no node given: pass some ids, "
                                             "or --branch <branch>"},
    "mutate.assegna_senza_nome": {"it": "nessun nome indicato: passa almeno una persona, "
                                        "per esempio 'anna' o 'anna,marco'",
                                  "en": "no name given: pass at least one person, "
                                        "for example 'anna' or 'anna,marco'"},
    "mutate.nome_separatore": {"it": "«{nome}» contiene una virgola, che qui separa le persone: "
                                     "scrivi i nomi come 'anna,marco'",
                               "en": "'{nome}' contains a comma, which here separates people: "
                                     "write the names as 'anna,marco'"},
    "mutate.nome_accrocchio": {"it": "«{nome}» non è una persona sola: i nomi congiunti si "
                                     "scrivono separati da virgola, 'anna,marco'",
                               "en": "'{nome}' is not a single person: joint names are written "
                                     "comma-separated, 'anna,marco'"},
    "mutate.assegna_modo": {"it": "modo di assegnazione sconosciuto: {modo}",
                            "en": "unknown assignment mode: {modo}"},
    "mutate.ramo_esiste": {"it": "il ramo {chiave} esiste già", "en": "branch {chiave} already exists"},
    "mutate.nodo_esiste": {"it": "{id} esiste già", "en": "{id} already exists"},
    "mutate.campi_protetti": {"it": "questi campi non si toccano da mutate: {elenco}",
                             "en": "these fields aren't touched from mutate: {elenco}"},
    "mutate.blocca_ancora": {"it": "{id} blocca ancora {dipendenti}: sganciali prima",
                            "en": "{id} still blocks {dipendenti}: unlink them first"},
    "mutate.non_bloccato": {"it": "{id} non è bloccato da {blocked_by}",
                           "en": "{id} is not blocked by {blocked_by}"},
    "mutate.grafo_esiste": {"it": "il grafo '{slug}' esiste già in {dir}",
                           "en": "graph '{slug}' already exists in {dir}"},
    "mutate.ramo_default_label": {"it": "Percorso principale", "en": "Main path"},
    "mutate.ripristino_incompleto": {"it": "{id}: per ripristinare una chiusura servono la risposta, "
                                            "chi l'ha chiusa e quando",
                                    "en": "{id}: restoring a closure needs the answer, "
                                          "who closed it and when"},
    "mutate.ripristino_gia_chiuso": {"it": "{id} è già chiuso: ripristinare sopra una chiusura ne "
                                             "cancellerebbe un'altra",
                                    "en": "{id} is already closed: restoring over a closure "
                                          "would erase another one"},

    # --- config.py ---
    "config.root_mancante": {"it": "nessun {dirname}/ da qui in su: installa Atlas con 'atlas install'",
                            "en": "no {dirname}/ from here up: install Atlas with 'atlas install'"},
    "config.nessun_grafo_attivo": {"it": "più grafi in questo progetto e nessuno attivo.\n"
                                         "  Scegline uno con 'atlas use <slug>' fra: {elenco}",
                                   "en": "more than one graph in this project and none active.\n"
                                         "  Pick one with 'atlas use <slug>' among: {elenco}"},
    "config.nessun_grafo": {"it": "nessuno, creane uno con atlas new", "en": "none, create one with atlas new"},
    "config.grafo_inesistente": {"it": "il grafo '{scelto}' non esiste: ci sono {elenco}",
                                 "en": "graph '{scelto}' doesn't exist: there are {elenco}"},
    "config.zero_grafi": {"it": "zero grafi", "en": "zero graphs"},
    "config.json_rotto": {"it": "{path} non è JSON valido ({dettaglio}).\n"
                                "  Correggilo a mano, oppure cancellalo e rilancia 'atlas install'.",
                          "en": "{path} is not valid JSON ({dettaglio}).\n"
                                "  Fix it by hand, or delete it and run 'atlas install' again."},

    # --- store.py ---
    "store.lock_conteso": {"it": "il grafo è occupato da un altro processo e non si è liberato: "
                                 "niente è stato scritto, riprova fra poco.",
                          "en": "the graph is held by another process and did not free up: "
                                "nothing was written, try again shortly."},
    "store.grafo_rotto":{"it": "{path} non è JSON valido ({dettaglio}).\n"
                                "  Il grafo non si può leggere: recuperalo da git, se il progetto lo versiona.",
                          "en": "{path} is not valid JSON ({dettaglio}).\n"
                                "  The graph can't be read: restore it from git, if the project versions it."},
    "store.grafo_senza_nodi": {"it": "{path} non ha la lista 'nodes', quindi non è un grafo Atlas.",
                               "en": "{path} has no 'nodes' list, so it is not an Atlas graph."},

    # --- merge.py ---
    "merge.conflitto": {"it": "  conflitto su {nodo}: {campo} ({tipo})",
                        "en": "  conflict on {nodo}: {campo} ({tipo})"},
    "merge.illeggibile": {"it": "{path} non si legge come JSON ({dettaglio}): merge non eseguito.",
                          "en": "{path} is not readable as JSON ({dettaglio}): merge not performed."},

    # --- docs.py (errori) ---
    "docs.marker_sezione_persa": {"it": "la sezione '{heading}' di map.md ha perso il marker {mark}.\n"
                                        "  Senza quel confine non si sa dove finisce la prosa scritta a mano.",
                                 "en": "section '{heading}' of map.md lost the marker {mark}.\n"
                                       "  Without that boundary there's no telling where the hand-written prose ends."},
    "docs.sezione_rinominata": {"it": "map.md non ha la sezione '{heading}': rinominarla ferma la rigenerazione.\n"
                                      "  Rimettila, oppure cancella map.md e lascia che 'atlas render' la ricrei.",
                               "en": "map.md has no section '{heading}': renaming it stops regeneration.\n"
                                     "  Put it back, or delete map.md and let 'atlas render' recreate it."},

    # --- render_panels.py (lucchetti remoti nella dashboard) ---
    "render.remoto": {"it": "Lucchetti remoti", "en": "Remote locks"},
    "render.remoto_vuoto": {"it": "nessun lucchetto remoto su altre macchine",
                            "en": "no remote locks on other machines"},
    "render.remoto_rete": {"it": "remote non raggiungibile: mostro l'ultima lettura",
                           "en": "remote unreachable: showing the last read"},
    "render.remoto_scaduto": {"it": "scaduto", "en": "expired"},
    "render.remoto_scade": {"it": "scade alle {ora}", "en": "expires at {ora}"},
    "render.remoto_ignoto": {"it": "scadenza ignota", "en": "unknown expiry"},

    # --- doctor.py ---
    "doctor.remoto_rete": {"it": "il lucchetto remoto non risponde: le macchine non si "
                                 "vedono, verifica la rete o togli lock.remote dalla config",
                           "en": "the remote lock is not responding: the machines can't "
                                 "see each other, check the network or remove lock.remote "
                                 "from the config"},
    "doctor.remoto_spento": {"it": "la config dichiara lock.remote ma il lucchetto remoto "
                                   "non è attivo: le macchine non si proteggono a vicenda",
                             "en": "the config declares lock.remote but the remote lock is "
                                   "not active: the machines don't protect each other"},

    # --- telegram_actions.py (D06) ---
    "telegram_actions.resolved": {"it": "Fatto: {label}.", "en": "Done: {label}."},
    "telegram_actions.rejected": {
        "it": "Questa richiesta non è più valida (scaduta o già risolta).",
        "en": "This request is no longer valid (expired or already resolved)."},
}
