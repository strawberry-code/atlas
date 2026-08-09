"""Avvisi sulla salute di un grafo: controlli diagnostici e segnalazioni."""
from __future__ import annotations

from datetime import datetime

from . import claims, docs, gitscan
from .config import ConfigError, Graph, Workspace
from .model import blocks, by_id, claimed, is_done
from .report import ETICHETTA
from .store import load
from .strings import t


def doctor_avvisi(data: dict, ref: Graph, agente: dict) -> list[str]:
    """Avvisi sulla salute di un grafo: non bloccano niente, segnalano soltanto."""
    avvisi = []

    foglie = [n["id"] for n in data["nodes"] if not is_done(n) and not blocks(data, n["id"])]
    if len(foglie) > 1:
        avvisi.append(t("doctor.nodi_pendenti", elenco=", ".join(foglie)))

    for nodo in claimed(data):
        stato = claims.claim_state(nodo, agente)
        if stato != "live":
            avvisi.append(t("doctor.lucchetto_fermo", id=nodo["id"], stato=t(ETICHETTA[stato])))

    if ref.dashboard_path.is_file() and ref.json_path.stat().st_mtime > ref.dashboard_path.stat().st_mtime:
        avvisi.append(t("doctor.dashboard_stantia"))

    if scollegati := docs.unalignable(ref, data):
        avvisi.append(t("doctor.ticket_scollegato", elenco=", ".join(scollegati), mark=docs.MARK_END))

    index = by_id(data)
    for nodo in claimed(data):
        chi = claims.holder(nodo).get("identity")
        autoverificati = [d for d in nodo["blockedBy"] if index[d].get("closedBy") == chi]
        if chi and autoverificati:
            avvisi.append(t("doctor.autoverifica", id=nodo["id"], chi=chi, elenco=", ".join(autoverificati)))

    for nodo in data["nodes"]:
        chiuso = nodo.get("closedAt")
        if nodo["status"] != "closed" or not chiuso or not nodo.get("artifacts"):
            continue
        tocchi = []
        for a in nodo["artifacts"]:
            if not (ref.workspace.project_root / a).is_file():
                continue
            # Usa git se siamo in una repo per verificare se il file e' davvero cambiato.
            # Se gitscan non puo' verificare (repo non git O rev-list vuoto), fallback all'mtime.
            result = gitscan.changed_since(ref.workspace.project_root, a, chiuso)
            if result is True:
                tocchi.append(a)
            elif result is None:
                # Fallback all'mtime: il file e' stato scritto dopo la chiusura.
                soglia = datetime.fromisoformat(chiuso)
                if datetime.fromtimestamp((ref.workspace.project_root / a).stat().st_mtime).astimezone() > soglia:
                    tocchi.append(a)
        if tocchi:
            avvisi.append(t("doctor.ambito_toccato", id=nodo["id"], elenco=", ".join(tocchi)))

    return avvisi


def show_doctor(ws: Workspace) -> None:
    """Avvisi sulla salute di ogni grafo del progetto: non bloccano niente, segnalano soltanto."""
    agente = ws.config["agent"]
    for slug in ws.slugs():
        ref = Graph(ws, slug)
        try:
            data = load(ref.json_path)
        except ConfigError as errore:
            # Un grafo illeggibile e' la diagnosi piu' importante che doctor possa
            # dare: se lo lasciassimo passare, l'unico comando che serve a capire
            # cosa non va sarebbe anche l'unico che si ferma prima di dirlo.
            print(t("doctor.grafo_titolo", slug=slug))
            print(f"    {errore}")
            continue
        avvisi = doctor_avvisi(data, ref, agente)
        if avvisi:
            print(t("doctor.grafo_titolo", slug=slug))
            for avviso in avvisi:
                print(f"    {avviso}")
    print()
