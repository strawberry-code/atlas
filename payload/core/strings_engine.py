"""Messaggi d'errore del motore: claims.py, mutate.py, config.py.

Parte del catalogo del motore: vedi strings.py per il meccanismo di lookup,
strings_cli.py e strings_docs.py per il resto del catalogo.
"""
from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
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

    # --- mutate.py ---
    "mutate.id_duplicato": {"it": "id duplicato: {id}", "en": "duplicate id: {id}"},
    "mutate.ramo_inesistente": {"it": "{id} sta su un ramo inesistente: {branch}",
                               "en": "{id} is on a branch that doesn't exist: {branch}"},
    "mutate.vocab_non_valido": {"it": "{id} ha {chiave}='{valore}', fuori da {ammessi}",
                               "en": "{id} has {chiave}='{valore}', outside {ammessi}"},
    "mutate.dipendenza_inesistente": {"it": "{id} è bloccato da {dep}, che non esiste",
                                     "en": "{id} is blocked by {dep}, which doesn't exist"},
    "mutate.auto_dipendenza": {"it": "{id} dipende da se stesso", "en": "{id} depends on itself"},
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

    # --- docs.py (errori) ---
    "docs.marker_sezione_persa": {"it": "la sezione '{heading}' di map.md ha perso il marker {mark}.\n"
                                        "  Senza quel confine non si sa dove finisce la prosa scritta a mano.",
                                 "en": "section '{heading}' of map.md lost the marker {mark}.\n"
                                       "  Without that boundary there's no telling where the hand-written prose ends."},
    "docs.sezione_rinominata": {"it": "map.md non ha la sezione '{heading}': rinominarla ferma la rigenerazione.\n"
                                      "  Rimettila, oppure cancella map.md e lascia che 'atlas render' la ricrei.",
                               "en": "map.md has no section '{heading}': renaming it stops regeneration.\n"
                                     "  Put it back, or delete map.md and let 'atlas render' recreate it."},
}
