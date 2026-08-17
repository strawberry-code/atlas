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
    return pulito


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


def assign(g: Editor, name: str, node_ids: list[str] | tuple[str, ...] = (),
           branch: str | None = None) -> list[str]:
    """Assegna nodi a una persona. Torna solo quelli che hanno cambiato assegnatario."""
    nome = nome_persona(name)
    cambiati = []
    for node_id in _bersagli(g, node_ids, branch):
        node = g.node(node_id)
        if node.get("owner") != nome:
            node["owner"] = nome
            cambiati.append(node_id)
    return cambiati


def unassign(g: Editor, node_ids: list[str] | tuple[str, ...] = (),
             branch: str | None = None) -> list[str]:
    """Toglie l'assegnatario. Torna solo i nodi che ne avevano davvero uno.

    Scrive None invece di togliere la chiave: un nodo nasce con 'owner': None e
    deve restare cosi' anche dopo essere passato di mano, altrimenti lo stesso
    stato si legge in due forme diverse nel JSON versionato.
    """
    cambiati = []
    for node_id in _bersagli(g, node_ids, branch):
        node = g.node(node_id)
        if node.get("owner"):
            node["owner"] = None
            cambiati.append(node_id)
    return cambiati
