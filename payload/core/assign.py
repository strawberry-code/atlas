"""Chi si e' preso in carico un nodo, indipendentemente da chi lo sta lavorando.

Sono due cose diverse e il grafo le tiene separate. 'assignee' e' il lucchetto:
lo scrive claim, lo cancella release, dice chi ci ha le mani sopra adesso.
'owner', che si scrive da qui, e' la ripartizione del lavoro decisa da chi
costruisce il grafo: sopravvive alle prese e ai rilasci, e resta anche a nodo
chiuso, perche' la domanda a cui risponde e' 'di chi era questo pezzo'.

Spezzato da mutate.py per non farlo sfondare, come gia' editor.py: chi scrive
uno script continua a passare da 'mutate.assign', che re-importa questi nomi.
"""
from __future__ import annotations

from .editor import Editor
from .model import chiave_nome, owners_of
from .store import StateError
from .strings import t

NOME_MAX = 40


def nome_persona(name: str) -> str:
    """Il nome normalizzato, o un errore che dice cosa non va.

    Questo nome finisce nel grafo versionato, nei documenti e nella dashboard, e
    lo scrive chiunque passi dalla riga di comando: e' un confine del sistema, e
    si valida qui che e' l'unica porta in scrittura. Gli spazi ripetuti e gli a
    capo collassano, perche' 'anna  maria' e 'anna maria' non devono diventare
    due persone diverse nell'elenco.
    """
    pulito = " ".join(name.split())
    if not pulito or len(pulito) > NOME_MAX or any(ord(c) < 32 for c in pulito):
        raise StateError(t("mutate.nome_non_valido", nome=name, max=NOME_MAX))
    if "," in pulito:
        raise StateError(t("mutate.nome_separatore", nome=name))
    if "+" in pulito:
        raise StateError(t("mutate.nome_accrocchio", nome=name))
    return pulito


def persone(spec) -> list[str]:
    """I nomi che l'utente ha indicato, distinti e in ordine.

    Accetta sia la stringa della riga di comando ('cristiano,pedro') sia una lista di nomi,
    perche' la stessa funzione serve il CLI e gli script degli ospiti.
    """
    if isinstance(spec, str):
        pezzi = spec.split(",")
    elif spec is None:
        pezzi = []
    else:
        pezzi = [p for elemento in spec for p in str(elemento).split(",")]
    nomi = []
    for pezzo in pezzi:
        pulito = " ".join(pezzo.split())
        if not pulito:
            continue
        nome = nome_persona(pulito)
        if nome not in nomi:
            nomi.append(nome)
    if not nomi:
        raise StateError(t("mutate.assegna_senza_nome"))
    return sorted(nomi, key=chiave_nome)


def _bersagli(g: Editor, node_ids, branch: str | None) -> list[str]:
    """Gli id su cui agire: quelli nominati, piu' i nodi che il ramo ha adesso.

    Il ramo si espande subito e non resta appeso come regola: un nodo aggiunto
    dopo nasce senza assegnatario. Cosi' l'assegnazione sta scritta sul nodo e
    chi legge il grafo non deve derivarla da nessun'altra parte.
    """
    ids = list(dict.fromkeys(node_ids))
    for node_id in ids:
        g.node(node_id)      # nomina subito l'id che non esiste, invece di scrivere nel vuoto
    if branch is not None:
        if branch not in g.data["branches"]:
            raise StateError(t("mutate.ramo_bersaglio", branch=branch,
                               elenco=", ".join(g.data["branches"])))
        ids += [n["id"] for n in g.data["nodes"] if n["branch"] == branch and n["id"] not in ids]
    if not ids:
        raise StateError(t("mutate.assegna_senza_bersaglio"))
    return ids


def assign(g: Editor, names, node_ids: list[str] | tuple[str, ...] = (),
           branch: str | None = None, modo: str = "set") -> list[str]:
    """Assegna nodi a una o piu' persone. Torna solo i nodi il cui vettore e' cambiato.

    modo='set' sostituisce il vettore, 'add' lo allarga con i nomi nuovi, 'remove'
    ne toglie quelli indicati; il risultato resta sempre distinto e ordinato.
    """
    if modo not in ("set", "add", "remove"):
        raise StateError(t("mutate.assegna_modo", modo=modo))
    nomi = persone(names)
    cambiati = []
    for node_id in _bersagli(g, node_ids, branch):
        node = g.node(node_id)
        attuali = owners_of(node)
        if modo == "set":
            nuovo = list(nomi)
        elif modo == "add":
            nuovo = sorted(set(attuali) | set(nomi), key=chiave_nome)
        else:
            nuovo = [n for n in attuali if n not in set(nomi)]
        if nuovo != attuali:
            node["owner"] = nuovo
            cambiati.append(node_id)
    return cambiati


def unassign(g: Editor, node_ids: list[str] | tuple[str, ...] = (),
             branch: str | None = None) -> list[str]:
    """Toglie gli assegnatari. Torna solo i nodi che ne avevano davvero uno.

    Scrive [] invece di togliere la chiave: un nodo nasce con 'owner': [] e
    deve restare cosi' anche dopo essere passato di mano, altrimenti lo stesso
    stato si legge in due forme diverse nel JSON versionato.
    """
    cambiati = []
    for node_id in _bersagli(g, node_ids, branch):
        node = g.node(node_id)
        if owners_of(node):
            node["owner"] = []
            cambiati.append(node_id)
    return cambiati
