"""D01 (260902-atlas-relay): i tre comandi di stato al bot, con la risposta
a Mac spento. Elenco chiuso (S11/6, non uno di piu'): '/stato' (a che punto
e' il lavoro), '/aspetta' (cosa aspetta una persona), '/storto' (cos'e'
andato storto).

Il relay non conserva lo stato di nessun progetto (grilling 7,
relay/status_commands.py si ferma al riconoscimento del testo e
all'instradamento): questo modulo e' l'unico che legge il ledger Atlas per
rispondere, esattamente come telegram_actions.py e' l'unico che lo scrive per
risolvere un tap. Gira nello stesso thread del tunnel (autopilot.py lo
combina con telegram_actions.gestore), risponde sempre con un messaggio
nuovo sulla chat di questa installazione (relay_client.invia_messaggio,
D07), mai un edit: qui non c'e' nessun messaggio precedente da aggiornare,
a differenza della risoluzione di un tap.

Ogni comando rilegge 'graph.json' e 'run-state.json' al momento della
domanda, mai uno snapshot preso all'apertura del tunnel: un run puo' restare
acceso per ore e il grafo cambia sotto ai suoi piedi mentre gira (nodi che si
chiudono, Interazioni che si aprono e si risolvono).
"""
from __future__ import annotations

from collections.abc import Mapping

from . import interactions_view, relay_client
from .config import Graph
from .model import frontier, progress
from .run_state import RunState
from .store import load
from .strings import t

COMANDO_STATO = "/stato"
COMANDO_ASPETTA = "/aspetta"
COMANDO_STORTO = "/storto"
COMANDI = frozenset({COMANDO_STATO, COMANDO_ASPETTA, COMANDO_STORTO})

_EVENTI_GUASTO = frozenset({"attempt-failed", "node-exhausted", "run-failed", "run-blocked"})
_MAX_GUASTI = 5


def gestore(graph: Graph, installation_id: str, config: relay_client.TunnelConfig,
           *, opener=None) -> relay_client.OnEvent:
    """Un on_event per il tunnel di questa sessione: ignora tutto cio' che
    non e' uno dei tre comandi chiusi, coerente col fatto che qui non nasce
    nessuna conversazione libera col bot."""
    def _on_event(evento: Mapping[str, object]) -> None:
        if evento.get("kind") != "message":
            return
        testo = evento.get("text")
        if testo not in COMANDI:
            return
        risposta = _componi(graph, testo)
        kwargs = {} if opener is None else {"opener": opener}
        relay_client.invia_messaggio(config, installation_id, risposta, [], **kwargs)
    return _on_event


def _componi(graph: Graph, comando: str) -> str:
    data = load(graph.json_path)
    titolo = data["meta"]["title"]
    if comando == COMANDO_STATO:
        corpo = _stato(graph, data)
    elif comando == COMANDO_ASPETTA:
        corpo = _aspetta(data)
    else:
        corpo = _storto(graph)
    return f"{titolo}\n\n{corpo}"


def _stato(graph: Graph, data: dict) -> str:
    fatti, totale = progress(data)
    stato_run = RunState.read(graph.run_state_path)
    if stato_run and stato_run.get("node"):
        return t("telegram_status.stato_in_corso", fatti=fatti, totale=totale,
                node=stato_run["node"], provider=stato_run.get("provider") or "-")
    front = frontier(data)
    if front:
        return t("telegram_status.stato_frontiera", fatti=fatti, totale=totale,
                elenco=", ".join(n["id"] for n in front))
    return t("telegram_status.stato_fermo", fatti=fatti, totale=totale)


def _aspetta(data: dict) -> str:
    aperte = [riga for riga in interactions_view.project(data) if riga["status"] == "open"]
    if not aperte:
        return t("telegram_status.aspetta_nessuna")
    righe = "\n".join(t("telegram_status.aspetta_riga", node=riga["node"], summary=riga["summary"])
                      for riga in aperte)
    return t("telegram_status.aspetta_titolo") + "\n" + righe


def _storto(graph: Graph) -> str:
    stato_run = RunState.read(graph.run_state_path)
    if stato_run is None:
        return t("telegram_status.storto_nessun_run")
    guasti = [e for e in stato_run["events"] if e["type"] in _EVENTI_GUASTO][-_MAX_GUASTI:]
    if not guasti and stato_run["status"] not in ("failed", "blocked"):
        return t("telegram_status.storto_nulla")
    righe = []
    if stato_run.get("reason"):
        righe.append(t("telegram_status.storto_motivo", reason=stato_run["reason"]))
    righe.extend(t("telegram_status.storto_riga", node=evento.get("node", "?"),
                   failure=evento.get("failure") or "-") for evento in guasti)
    return "\n".join(righe) if righe else t("telegram_status.storto_nulla")
