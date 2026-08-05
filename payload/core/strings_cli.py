"""Messaggi di cli.py: help di argparse, e quel che stampano i comandi.

Parte del catalogo del motore: vedi strings.py per il meccanismo di lookup,
strings_engine.py e strings_docs.py per il resto del catalogo.
"""
from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    # --- argparse: descrizione e help ---
    "parser.description": {"it": "Harness di task a grafo.", "en": "Graph-based task harness."},
    "opt.graph": {"it": "slug del grafo, se non è quello attivo",
                  "en": "graph slug, if not the active one"},
    "help.status": {"it": "frontiera, lucchetti, avanzamento", "en": "frontier, locks, progress"},
    "help.next": {"it": "la frontiera ordinata per impatto", "en": "the frontier ranked by impact"},
    "help.graphs": {"it": "i grafi di questo progetto", "en": "the graphs in this project"},
    "help.use": {"it": "rende attivo un grafo", "en": "makes a graph active"},
    "help.show": {"it": "scheda di un nodo", "en": "a node's card"},
    "help.brief": {"it": "il pacchetto di contesto per lavorare un nodo",
                   "en": "the context package to work a node"},
    "help.claim": {"it": "rivendica un nodo per questa sessione", "en": "claims a node for this session"},
    "help.release": {"it": "restituisce un nodo alla frontiera", "en": "returns a node to the frontier"},
    "help.close": {"it": "chiude un nodo con la sua sintesi", "en": "closes a node with its summary"},
    "help.fog": {"it": "appunta ciò che è emerso e non ha ancora un nodo",
                 "en": "notes down what came up and has no node yet"},
    "help.render": {"it": "rigenera ticket, mappa e dashboard",
                    "en": "regenerates tickets, map and dashboard"},
    "help.new": {"it": "crea un grafo nuovo", "en": "creates a new graph"},
    "default.destination": {"it": "Da scrivere: dove si arriva quando questo grafo è finito.",
                             "en": "To be written: where this graph leads when it's done."},
    "help.new_script": {"it": "crea uno script di mutazione numerato",
                        "en": "creates a numbered mutation script"},
    "help.exec": {"it": "esegue uno script di mutazione", "en": "runs a mutation script"},
    "help.validate": {"it": "verifica la forma dei grafi", "en": "checks the graphs' shape"},
    "help.doctor": {"it": "stato dell'installazione", "en": "installation status"},

    # --- refresh/commit ---
    "refresh.ticket_creati": {"it": "  {n} ticket creati in {dir}", "en": "  {n} tickets created in {dir}"},
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
    "doctor.hook": {"it": "  hook     {stato}", "en": "  hook     {stato}"},
    "doctor.hook_ok": {"it": "registrato", "en": "registered"},
    "doctor.hook_assente": {"it": "assente", "en": "absent"},
    "doctor.git": {"it": "  git      {presente} · commit alla chiusura: {commit}\n",
                   "en": "  git      {presente} · commit on close: {commit}\n"},
    "doctor.grafo_titolo": {"it": "  {slug}:", "en": "  {slug}:"},
    "doctor.nodi_pendenti": {"it": "nodi che non bloccano nient'altro, nemmeno un cancello finale: {elenco}. "
                                    "Controlla che non siano stati dimenticati.",
                             "en": "nodes that block nothing else, not even a final gate: {elenco}. "
                                   "Check they weren't forgotten."},
    "doctor.lucchetto_fermo": {"it": "{id} è rivendicato ma {stato}", "en": "{id} is claimed but {stato}"},
    "doctor.dashboard_stantia": {"it": "la dashboard è più vecchia dell'ultima modifica al grafo: esegui 'atlas render'",
                                 "en": "the dashboard is older than the last change to the graph: run 'atlas render'"},
    "doctor.autoverifica": {"it": "{id}, rivendicato da {chi}, verifica nodi che {chi} stessa ha chiuso: {elenco}",
                            "en": "{id}, claimed by {chi}, verifies nodes that {chi} closed themself: {elenco}"},
    "doctor.ambito_toccato": {"it": "{id} è chiuso ma questi artifacts sono stati modificati dopo: {elenco}. "
                                     "Verifica che non sia una scrittura fuori scopo.",
                              "en": "{id} is closed but these artifacts were modified afterwards: {elenco}. "
                                    "Check it isn't an out-of-scope write."},
    "si": {"it": "sì", "en": "yes"},
    "no": {"it": "no", "en": "no"},

    # --- dispatch ---
    "use.attivo": {"it": "  grafo attivo: {slug}", "en": "  active graph: {slug}"},
    "close.fatto": {"it": "  {id} chiuso · riga aggiunta in map.md", "en": "  {id} closed · line added to map.md"},
    "claim.fatto": {"it": "  {id} rivendicato · ticket in {path}", "en": "  {id} claimed · ticket at {path}"},
    "release.fatto": {"it": "  {id} tornato alla frontiera", "en": "  {id} back on the frontier"},
    "fog.fatto": {"it": "  appuntato nella nebbia", "en": "  noted in the fog"},
    "fog.per": {"it": "per {id}: {riga}", "en": "for {id}: {riga}"},
    "fog.riga_mancante": {"it": "una voce di nebbia richiede del testo: 'atlas fog \"...\"'",
                          "en": "a fog entry needs some text: 'atlas fog \"...\"'"},

    # --- hooks/session_end.py ---
    "hook.rivendicato": {"it": "Atlas: {elenco} resta rivendicato. "
                               "Alla prossima sessione chiudilo con 'atlas close', oppure rilascialo.",
                         "en": "Atlas: {elenco} is still claimed. "
                               "Next session, close it with 'atlas close', or release it."},
}
