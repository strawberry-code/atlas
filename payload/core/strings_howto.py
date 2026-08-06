"""Messaggi di howto.py: le intestazioni delle sei sezioni e le descrizioni delle mutazioni.

Le firme delle mutazioni le legge l'introspezione, quindi non stanno qui: qui c'e' solo
la riga in prosa che le accompagna, una per funzione con la chiave 'howto.mutate.<nome>'.
Una funzione nuova in mutate.py compare comunque nell'how-to, con la sola firma, finche'
non le si aggiunge la voce: vedi la regola in CLAUDE.md.

Parte del catalogo del motore: vedi strings.py per il meccanismo di lookup.
"""
from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "howto.intestazione": {"it": "  Atlas {versione} · progetto {progetto} · lingua {lingua}",
                           "en": "  Atlas {versione} · project {progetto} · language {lingua}"},
    "howto.avvertenza": {"it": "  Il contratto qui sotto è la regola; comandi, mutazioni e skill sono letti\n"
                               "  dal codice installato, quindi descrivono questa versione e non un'altra.",
                         "en": "  The contract below is the rule; commands, mutations and skills are read from\n"
                               "  the installed code, so they describe this version and no other."},
    "howto.sezione": {"it": "\n\n  ─── {n}. {titolo} ───\n", "en": "\n\n  ─── {n}. {titolo} ───\n"},
    "howto.titolo_contratto": {"it": "Il contratto: come si lavora qui",
                               "en": "The contract: how work happens here"},
    "howto.titolo_comandi": {"it": "I comandi", "en": "The commands"},
    "howto.titolo_mutazioni": {"it": "Cambiare la forma del grafo", "en": "Changing the graph's shape"},
    "howto.mutazioni_intro": {"it": "  Mai a mano su graph.json: solo da uno script in {path}, che definisce run(g)\n"
                                    "  e si esegue con 'atlas exec'. Dentro run(g) si chiamano queste, e solo queste:\n",
                              "en": "  Never by hand on graph.json: only from a script in {path}, which defines run(g)\n"
                                    "  and is run with 'atlas exec'. Inside run(g) you call these, and only these:\n"},
    "howto.titolo_skill": {"it": "Le skill installate", "en": "The installed skills"},
    "howto.skill_nessuna": {"it": "    nessuna", "en": "    none"},
    "howto.titolo_dove": {"it": "Dove sta cosa", "en": "Where things are"},
    "howto.dove_scripts": {"it": "    script     {path}", "en": "    scripts    {path}"},
    "howto.dove_nessun_grafo": {"it": "    nessun grafo ancora: 'atlas new <slug> -t \"Titolo\"' ne crea uno",
                                "en": "    no graph yet: 'atlas new <slug> -t \"Title\"' creates one"},
    "howto.dove_grafo": {"it": "  {segno} {slug}  {fatti}/{totale} nodi chiusi · {dir}",
                         "en": "  {segno} {slug}  {fatti}/{totale} nodes closed · {dir}"},
    "howto.dove_json": {"it": "    grafo      {path}", "en": "    graph      {path}"},
    "howto.dove_ticket": {"it": "    ticket     {path}", "en": "    tickets    {path}"},
    "howto.dove_mappa": {"it": "    mappa      {path}", "en": "    map        {path}"},
    "howto.dove_dashboard": {"it": "    dashboard  {path}", "en": "    dashboard  {path}"},
    "howto.titolo_primi_passi": {"it": "Il giro tipico", "en": "The usual round"},
    "howto.primi_passi": {"it": "    1. atlas status              la frontiera: cosa è prendibile adesso\n"
                                "    2. atlas take <ID>           rivendica e stampa il contesto, prima di toccare niente\n"
                                "    3. lavora, poi scrivi la Risposta nel ticket del nodo\n"
                                "    4. atlas close <ID> -s \"la sintesi in una riga\"\n"
                                "    5. quel che è emerso e non ha un nodo: atlas fog \"una riga\" --for <ID>\n\n"
                                "  Un nodo per sessione. La risposta di un nodo HITL si scrive con l'umano, mai da soli.\n"
                                "  'atlas doctor' prima di dichiarare finito un grafo.",
                          "en": "    1. atlas status              the frontier: what's takeable right now\n"
                                "    2. atlas take <ID>           claims it and prints its context, before touching anything\n"
                                "    3. work it, then write the Answer in the node's ticket\n"
                                "    4. atlas close <ID> -s \"the one-line summary\"\n"
                                "    5. what came up and has no node: atlas fog \"one line\" --for <ID>\n\n"
                                "  One node per session. A HITL node's answer is written with the human, never alone.\n"
                                "  Run 'atlas doctor' before calling a graph finished."},

    # --- una riga per ogni mutazione chiamabile da uno script ---
    "howto.mutate.add_branch": {"it": "crea un ramo: chiave, etichetta e colore",
                                "en": "creates a branch: key, label and colour"},
    "howto.mutate.add_node": {"it": "crea un nodo aperto sul ramo indicato",
                              "en": "creates an open node on the given branch"},
    "howto.mutate.edit_node": {"it": "cambia i campi descrittivi; stato e claim non passano da qui",
                               "en": "changes the descriptive fields; status and claim don't go through here"},
    "howto.mutate.remove_node": {"it": "cancella davvero: se il nodo è stato lavorato, drop() è quasi sempre meglio",
                                 "en": "really deletes it: if the node has been worked, drop() is almost always better"},
    "howto.mutate.link": {"it": "aggiunge una dipendenza: node_id resta fermo finché blocked_by non chiude",
                          "en": "adds a dependency: node_id waits until blocked_by closes"},
    "howto.mutate.unlink": {"it": "toglie una dipendenza", "en": "removes a dependency"},
    "howto.mutate.drop": {"it": "fuori scopo: il nodo esce dal percorso ma sblocca chi lo aspettava",
                          "en": "out of scope: the node leaves the path but still unblocks whoever waited for it"},
    "howto.mutate.reopen": {"it": "riporta un nodo chiuso allo stato aperto, senza risposta",
                            "en": "brings a closed node back to open, with no answer"},
    "howto.mutate.fog_add": {"it": "appunta una riga in nebbia da dentro uno script",
                             "en": "notes a line in the fog from inside a script"},
    "howto.mutate.fog_drop": {"it": "toglie dalla nebbia le righe che contengono needle, dopo averle promosse",
                              "en": "removes the fog lines containing needle, once they've been promoted"},
    "howto.mutate.set_meta": {"it": "cambia i campi di meta: titolo, destinazione, note",
                              "en": "changes the meta fields: title, destination, notes"},
    "howto.mutate.note_add": {"it": "aggiunge una nota al grafo, che finisce in mappa",
                              "en": "adds a note to the graph, which ends up in the map"},
}
