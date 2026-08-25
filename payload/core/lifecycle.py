"""Il ciclo di vita di un nodo dopo la sua creazione: fuori scopo, contabilita',
riapertura, ripristino di una chiusura.

Spezzato da mutate.py come gia' assign.py ed editor.py, quando il file ha passato le
200 righe: qui stanno i gesti che cambiano lo STATO di un nodo, la' quelli che
cambiano la forma del grafo. Chi scrive uno script continua a chiamarli da mutate,
che li re-importa.
"""
from __future__ import annotations

from .editor import Editor, now
from .identity import identity
from .model import is_done
from .store import CLOSED, DROPPED, OPEN, StateError
from .strings import t


def drop(g: Editor, node_id: str, reason: str) -> dict:
    """Fuori scopo: il nodo esce dal percorso ma continua a sbloccare chi lo aspettava."""
    node = g.node(node_id)
    node.update(status=DROPPED, assignee=None, claim=None, answer=reason)
    g.data["outOfScope"].append(f"**{node['title']}** ({node_id}): {reason}")
    return node


def amend(g: Editor, node_id: str, artifacts: list[str] | None = None,
          cost: str | None = None, summary: str | None = None) -> dict:
    """Corregge la contabilita' di un nodo gia' chiuso: artefatti, costo, sintesi.

    La deduzione automatica degli artefatti sbaglia in una classe di casi nota, e
    chi se ne accorge lo fa rileggendo la chiusura appena fatta: senza questa via
    il dato sbagliato resta li', e con lui gli avvisi che doctor ne ricava.

    Tocca solo i campi passati e lascia stare stato, closedAt e closedBy: e' una
    riga di contabilita' riscritta, non una chiusura rifatta, e doctor deve
    continuare a misurare le scritture postume dall'istante vero della chiusura.
    La correzione resta scritta nel nodo, cosi' chi rilegge sa che quel campo e'
    stato messo a mano e non dedotto.
    """
    node = g.node(node_id)
    if not is_done(node):
        raise StateError(t("mutate.amend_non_chiuso", id=node_id, stato=node["status"]))
    cambiati = {}
    if artifacts is not None:
        cambiati["artifacts"] = list(artifacts)
    if cost is not None:
        cambiati["cost"] = cost
    if summary is not None:
        cambiati["answer"] = summary
    if not cambiati:
        raise StateError(t("mutate.amend_senza_campi", id=node_id))
    node.update(cambiati)
    node.setdefault("amendments", []).append(
        {"at": now(), "by": identity(), "fields": sorted(cambiati)})
    return node


def reopen(g: Editor, node_id: str) -> dict:
    node = g.node(node_id)
    node.update(status=OPEN, assignee=None, claim=None, answer=None)
    node.pop("closedAt", None)
    return node


def restore_closure(g: Editor, node_id: str, answer: str, closedBy: str, closedAt: str,
                    cost: str | None = None,
                    artifacts: list[str] | tuple[str, ...] = ()) -> dict:
    """Riporta un nodo allo stato chiuso che la chiusura aveva su un'altra copia.

    Serve quando due copie del grafo divergono e si riapplica il proprio lavoro
    sopra il graph.json gia' pubblicato: una chiusura gia' avvenuta e gia'
    verificata dove e' successa davvero non si rifa', si ripristina con i
    metadati che aveva. Per questo non e' una scorciatoia per 'atlas close':
    non controlla il lucchetto, non pretende la Risposta nel ticket, non deduce
    gli artefatti da git, perche' quelle verifiche sono gia' state fatte una
    volta, li' dove la chiusura e' avvenuta davvero.

    closedBy e closedAt sono obbligatori proprio per questo: chi volesse usarla
    per chiudere un nodo vero dovrebbe inventarsi un'identita' e un timestamp,
    e la cosa si vedrebbe nel diff.
    """
    node = g.node(node_id)
    for campo in (answer, closedBy, closedAt):
        if not isinstance(campo, str) or not campo.strip():
            raise StateError(t("mutate.ripristino_incompleto", id=node_id))
    if is_done(node):
        raise StateError(t("mutate.ripristino_gia_chiuso", id=node_id))
    node.update(status=CLOSED, assignee=None, claim=None, owner=node.get("owner") or [],
                answer=answer, cost=cost, closedBy=closedBy, closedAt=closedAt)
    node["artifacts"] = list(artifacts)
    return node
