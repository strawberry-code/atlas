"""Etichette dei documenti generati: report.py, theme.py, render.py, e le
poche stringhe di docs.py che non sono errori (quelle stanno in strings_engine.py).

Parte del catalogo del motore: vedi strings.py per il meccanismo di lookup.
"""
from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    # --- docs.py ---
    "docs.niente": {"it": "_niente, per ora._", "en": "_nothing, for now._"},
    "docs.nessuno_prendibile": {"it": "nessuno, prendibile subito", "en": "none, up for grabs right away"},

    # --- report.py ---
    "report.stato_live": {"it": "sessione viva", "en": "live session"},
    "report.stato_idle": {"it": "sessione viva ma ferma", "en": "live session but stalled"},
    "report.stato_dead": {"it": "sessione finita, lucchetto orfano", "en": "session ended, orphan lock"},
    "report.durata_ignota": {"it": "da quando non si sa", "en": "since who knows when"},
    "report.durata_minuti": {"it": "da {n}m", "en": "for {n}m"},
    "report.durata_ore": {"it": "da {h}h{m:02d}", "en": "for {h}h{m:02d}"},
    "report.durata_giorni": {"it": "da {g}g", "en": "for {g}d"},
    "report.titolo": {"it": "\n  {titolo} · {slug} · {fatti}/{totale} nodi chiusi\n",
                      "en": "\n  {titolo} · {slug} · {fatti}/{totale} nodes closed\n"},
    "report.frontiera_titolo": {"it": "  Frontiera, prendibile adesso:", "en": "  Frontier, up for grabs now:"},
    "report.grafo_vuoto_1": {"it": "  Grafo vuoto: popolalo con uno script di mutazione.",
                            "en": "  Empty graph: populate it with a mutation script."},
    "report.grafo_vuoto_2": {"it": "  'atlas new-script primo-disegno', poi 'atlas exec' su quel file.",
                            "en": "  'atlas new-script first-draft', then 'atlas exec' on that file."},
    "report.finito": {"it": "  Niente di aperto: il grafo è finito.", "en": "  Nothing open: the graph is done."},
    "report.frontiera_vuota": {"it": "  Frontiera vuota: tutto quel che resta aspetta un nodo in lavorazione.",
                              "en": "  Empty frontier: everything left is waiting on a node in progress."},
    "report.in_lavorazione": {"it": "\n  In lavorazione:", "en": "\n  In progress:"},
    "report.sistema": {"it": "\n  Sistema {elenco} prima di rivendicare altro:"
                             " 'atlas release <ID>' oppure riconfermalo lavorandolo.",
                       "en": "\n  Sort out {elenco} before claiming anything else:"
                             " 'atlas release <ID>' or reconfirm it by working on it."},
    "report.nessun_grafo": {"it": "\n  Nessun grafo. Creane uno con 'atlas new <slug> -t \"titolo\"'.\n",
                           "en": "\n  No graphs yet. Create one with 'atlas new <slug> -t \"title\"'.\n"},
    "report.riga_grafo": {"it": "  {segno} {slug:<22} {fatti}/{totale} chiusi · "
                                "{n} prendibili · {titolo}",
                         "en": "  {segno} {slug:<22} {fatti}/{totale} closed · "
                               "{n} up for grabs · {titolo}"},
    "report.nodo_bloccato_da": {"it": "  bloccato da: {elenco}", "en": "  blocked by:   {elenco}"},
    "report.nodo_blocca": {"it": "  blocca:      {elenco}", "en": "  blocks:       {elenco}"},
    "report.nodo_ticket": {"it": "  ticket:      {path}", "en": "  ticket:       {path}"},
    "report.nodo_nessuno": {"it": "nessuno", "en": "none"},
    "report.nodo_assegnato": {"it": "  assegnato a: {nome}", "en": "  assigned to:  {nome}"},
    "report.assegnazioni": {"it": "\n  Assegnazioni:", "en": "\n  Assignments:"},
    "report.assegnazione_riga": {"it": "    {nome:<14} {elenco}", "en": "    {nome:<14} {elenco}"},
    "report.assegnazione_tuoi": {"it": "    → i tuoi: {elenco}", "en": "    → yours: {elenco}"},
    "report.non_assegnati": {"it": "    {etichetta:<14} {n}", "en": "    {etichetta:<14} {n}"},
    "report.nodo_risposta": {"it": "  Risposta: {risposta}\n", "en": "  Answer: {risposta}\n"},
    "report.nebbia_vuota": {"it": "  nessuna voce in nebbia", "en": "  no fog entries"},
    "report.nebbia_titolo": {"it": "\n  Nebbia:", "en": "\n  Fog:"},
    "report.brief_bloccanti": {"it": "\n  Risposte dei bloccanti:", "en": "\n  Blockers' answers:"},
    "report.brief_bloccante_aperto": {"it": "    {id} {titolo}: ancora {stato}, non c'è risposta da leggere",
                                      "en": "    {id} {titolo}: still {stato}, no answer to read yet"},
    "report.brief_nebbia": {"it": "\n  Nebbia che lo nomina:", "en": "\n  Fog that names it:"},
    "report.brief_rilasci": {"it": "\n  Rilasci precedenti su questo nodo:", "en": "\n  Earlier releases of this node:"},
    "report.next_titolo": {"it": "\n  Frontiera, ordinata per impatto:", "en": "\n  Frontier, ranked by impact:"},
    "report.next_riga": {"it": "    {id}  {titolo}  · sblocca {sblocca} · cammino residuo {cammino}",
                         "en": "    {id}  {titolo}  · unlocks {sblocca} · {cammino} steps to the end"},

    # --- theme.py (etichette di stato nella dashboard) ---
    "state.frontier": {"it": "prendibile adesso", "en": "up for grabs now"},
    "state.claimed": {"it": "in lavorazione", "en": "in progress"},
    "state.closed": {"it": "chiuso", "en": "closed"},
    "state.blocked": {"it": "bloccato", "en": "blocked"},
    "state.out_of_scope": {"it": "fuori scopo", "en": "out of scope"},

    # --- render.py (dashboard) ---
    "render.libero": {"it": "libero", "en": "free"},
    "render.avanzamento": {"it": "avanzamento", "en": "progress"},
    "render.nodi_conteggio": {"it": "{fatti} di {totale} nodi", "en": "{fatti} of {totale} nodes"},
    "render.frontiera": {"it": "frontiera", "en": "frontier"},
    "render.frontiera_vuota": {"it": "niente di prendibile: o è tutto chiuso, o è tutto bloccato",
                              "en": "nothing up for grabs: it's either all closed or all blocked"},
    "render.rami": {"it": "rami", "en": "branches"},
    "render.assegnazioni": {"it": "assegnazioni", "en": "assignments"},
    "render.non_assegnati": {"it": "non assegnati", "en": "unassigned"},
    "render.sheet_assegnato": {"it": "assegnato a", "en": "assigned to"},
    "render.nessun_ramo": {"it": "nessun ramo", "en": "no branches"},
    "render.in_lavorazione": {"it": "in lavorazione", "en": "in progress"},
    "render.chiusi": {"it": "chiusi", "en": "closed"},
    "render.costo_ignoto": {"it": "costo non dichiarato", "en": "cost not declared"},
    "render.costi": {"it": "costo", "en": "cost"},
    "render.costi_copertura": {"it": "{con} di {totale} nodi con costo dichiarato",
                               "en": "{con} of {totale} nodes with a declared cost"},
    "render.costi_fuori_conteggio": {"it": "{n} valori non numerici esclusi dal totale",
                                     "en": "{n} non-numeric values excluded from the total"},
    "render.nodi_del_ramo": {"it": "{n} nodi", "en": "{n} nodes"},
    "render.sottotitolo": {"it": "grafo <code>{slug}</code> · {progetto} · aggiornato al {data}",
                          "en": "graph <code>{slug}</code> · {progetto} · updated on {data}"},
    "render.legenda_caption": {"it": "passa il puntatore su un nodo per vederne le dipendenze, "
                                     "cliccalo per leggerne il ticket; un clic sulla legenda filtra "
                                     "per stato o per persona",
                              "en": "hover a node to see its dependencies, click it to read its ticket; "
                                    "click the legend to filter by state or by person"},
    "render.tema": {"it": "cambia tema chiaro/scuro", "en": "switch light/dark theme"},
    "render.sheet_chiudi": {"it": "chiudi il ticket", "en": "close the ticket"},
    "render.sheet_vuoto": {"it": "ticket ancora tutto da scrivere: la lavorazione non ha lasciato appunti",
                          "en": "ticket still to be written: the work has left no notes yet"},
    "render.sheet_apri_file": {"it": "apri il file .md", "en": "open the .md file"},
    "render.caution": {"it": "avviso", "en": "caution"},
    "render.non_converge": {"it": "terminali che non confluiscono nel finale {end}: {elenco}. Un grafo "
                                   "di solito converge in un nodo end unico: agganciali con uno script "
                                   "di mutazione, o mettili fuori scopo.",
                            "en": "terminal nodes that don't flow into the final {end}: {elenco}. A graph "
                                  "usually converges into a single end node: link them with a mutation "
                                  "script, or drop them out of scope."},
    "render.zoom_in": {"it": "avvicina la carta", "en": "zoom the chart in"},
    "render.zoom_out": {"it": "allontana la carta", "en": "zoom the chart out"},
    "render.zoom_fit": {"it": "adatta la carta allo schermo", "en": "fit the chart to the screen"},
    "render.footer": {"it": "generato da atlas · la verità sta in graph.json, e si cambia solo con uno script",
                     "en": "generated by atlas · the truth lives in graph.json, and changes only via a script"},

    # --- intestazioni di map.md: devono combaciare col template map.{lingua}.md ---
    "heading.destinazione": {"it": "## Destinazione", "en": "## Destination"},
    "heading.decisioni": {"it": "## Decisioni prese", "en": "## Decisions made"},
    "heading.note": {"it": "## Note", "en": "## Notes"},
    "heading.non_specificato": {"it": "## Non ancora specificato", "en": "## Not yet specified"},
    "heading.fuori_scopo": {"it": "## Fuori scopo", "en": "## Out of scope"},
    "heading.risposta": {"it": "## Risposta", "en": "## Answer"},
    "heading.lavorazione": {"it": "## Lavorazione", "en": "## Work"},
}
