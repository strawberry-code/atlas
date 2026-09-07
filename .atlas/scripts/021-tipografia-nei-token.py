"""F04 prende anche la tipografia: i font entrano con F01, ma nessuno li usa ancora.

Chiudendo F01, l'agente ha visto che i tre caratteri di Grafite caricano davvero ma
la dashboard resta in monospace di sistema: tokens.css dichiara ancora "font di
sistema e basta" e ogni foglio porta il proprio font-family scritto a mano. E' il
nodo dei token che deve chiudere il giro, non un nodo nuovo.
"""
from core import mutate


def run(g):
    nodo = g.node("F04")
    mutate.edit_node(
        g, "F04",
        title="Via il tema scuro, e i token di Atlas diventano quelli di Grafite",
        question=nodo["question"] + (
            "\n\n**E la tipografia.** F01 ha portato dentro i caratteri e loro caricano, ma nessun "
            "foglio di Atlas li chiede: tokens.css dichiara ancora 'font di sistema e basta' e i "
            "sette fogli portano il proprio font-family scritto a mano, quindi la dashboard resta "
            "in monospace di sistema. Fai consumare a tutti i fogli i token --sans, --display e "
            "--mono di Grafite, secondo i ruoli fissi che la spec impone: display per titoli, "
            "wordmark e label, mono per numeri, id, path e badge, sans per il corpo e per il "
            "markdown della scheda. Nessun font-family letterale deve sopravvivere fuori dai "
            "token.\n\n"
            "Questa e' anche la prima volta che la dashboard vera cambia aspetto, quindi la "
            "verifica e' uno screenshot guardato: le tre voci tipografiche devono distinguersi, e "
            "i glifi di stato di theme.py (▲ ⬤ ✓ · ✕) devono rendersi, non uscire come rettangoli "
            "vuoti."))
    mutate.fog_drop(g, "manca il nodo che fa consumare")
    mutate.fog_drop(g, "i glifi di stato di theme.py")
