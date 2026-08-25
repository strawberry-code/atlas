"""Avvisi sulla salute di un grafo: controlli diagnostici e segnalazioni."""
from __future__ import annotations

from datetime import datetime

from . import claims, docs, gitscan, remotelock
from .config import ConfigError, Graph, Workspace
from .model import by_id, claimed, is_done, istante, owners_of
from .report import ETICHETTA
from .store import StateError, load
from .strings import t
from .topology import convergence


def doctor_avvisi(data: dict, ref: Graph, agente: dict) -> list[str]:
    """Avvisi sulla salute di un grafo: non bloccano niente, segnalano soltanto."""
    avvisi = []

    # Un merge che non ha saputo risolvere lascia il campo conflicts nel grafo
    # (A02): e' il caso in cui doctor serve di piu', perche' git ha gia' dichiarato
    # il conflitto e il grafo aspetta una decisione che solo un umano prende.
    # Il grafo resta leggibile e valido, quindi il controllo non puo' mai morire.
    conflitti = [s for s in data.get("conflicts") or [] if isinstance(s, dict)]
    for s in conflitti:
        avvisi.append(t("doctor.conflitto", nodo=s.get("node") or "-",
                        campo=s.get("field") or "-", tipo=s.get("type") or "-"))
    if conflitti:
        avvisi.append(t("doctor.conflitti_rimedio"))

    # A grafo finito la non-convergenza non ha piu' niente da dire, e ripetuta
    # a ogni esecuzione insegnerebbe solo a ignorare gli avvisi.
    end, sciolti = convergence(data)
    if sciolti and not all(is_done(n) for n in data["nodes"]):
        avvisi.append(t("doctor.non_converge", end=end, elenco=", ".join(sciolti)))

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
                soglia = istante(chiuso)
                if soglia is None:
                    continue        # senza un istante leggibile non c'e' confronto da fare
                if datetime.fromtimestamp((ref.workspace.project_root / a).stat().st_mtime).astimezone() > soglia:
                    tocchi.append(a)
        if tocchi:
            avvisi.append(t("doctor.ambito_toccato", id=nodo["id"], elenco=", ".join(tocchi)))

    # La forma di owner si rimette in pari da sola alla prima mutazione: qui si segnala
    # e basta. Un nodo senza chiave o con None e' un grafo vecchio legittimo.
    for nodo in data["nodes"]:
        grezzo = nodo.get("owner")
        canonico = owners_of(nodo)
        if grezzo is not None and grezzo != canonico:
            avvisi.append(t("doctor.owner_non_canonico", id=nodo["id"], chi=", ".join(canonico)))

    # Il lucchetto remoto (L07): riferirne lo stato senza morire. Attivo e
    # raggiungibile e' silenzio; dichiarato in config ma non attivo, o attivo ma
    # irraggiungibile, e' un avviso: due macchine che non si vedono possono pestarsi,
    # ed e' esattamente cio' che il lucchetto deve evitare. Un trasporto che alza
    # invece di rispondere non deve far morire l'unico comando che serve quando qualcosa
    # e' gia' rotto.
    if remotelock.attivo():
        try:
            letto = remotelock.elenca()
        except Exception:
            letto = remotelock.Esito(remotelock.RETE)
        if not isinstance(letto, list):
            avvisi.append(t("doctor.remoto_rete"))
    elif ref.workspace.config.get("lock", {}).get("remote"):
        avvisi.append(t("doctor.remoto_spento"))

    return avvisi


def show_doctor(ws: Workspace) -> None:
    """Avvisi sulla salute di ogni grafo del progetto: non bloccano niente, segnalano soltanto."""
    agente = ws.config["agent"]
    for slug in ws.slugs():
        ref = Graph(ws, slug)
        try:
            data = load(ref.json_path)
            avvisi = doctor_avvisi(data, ref, agente)
        except (ConfigError, StateError) as errore:
            # Un grafo illeggibile o strutturalmente rotto (arco verso un id che non
            # esiste, ciclo di dipendenze) e' la diagnosi piu' importante che doctor
            # possa dare: se la lasciassimo passare, l'unico comando che serve a
            # capire cosa non va sarebbe anche l'unico che si ferma prima di dirlo.
            # Vale per tutti e due i momenti, la lettura e l'analisi, e per un grafo
            # solo: gli altri devono restare diagnosticabili.
            print(t("doctor.grafo_titolo", slug=slug))
            print(f"    {errore}")
            continue
        if avvisi:
            print(t("doctor.grafo_titolo", slug=slug))
            for avviso in avvisi:
                print(f"    {avviso}")
    print()
