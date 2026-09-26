"""Avvisi sulla salute di un grafo: controlli diagnostici e segnalazioni."""
from __future__ import annotations

from datetime import datetime

from . import claims, docs, gitscan, questions, worklog
from .config import ConfigError, Graph, Workspace
from .model import by_id, claimed, is_done, istante, owners_of
from .report import ETICHETTA
from .store import SUSPENDED, StateError, load
from .strings import t
from .topology import convergence


def doctor_avvisi(data: dict, ref: Graph, agente: dict) -> list[str]:
    """Avvisi sulla salute di un grafo: non bloccano niente, segnalano soltanto."""
    avvisi = []

    if domande := questions.open_questions(data):
        vecchie = {q["id"] for q in questions.aged_questions(data)}
        avvisi.append(t("doctor.domande_aperte", elenco=", ".join(
            q["id"] + (" (invecchiata)" if q["id"] in vecchie else "") for q in domande)))

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

    # Un sospeso e' un lavoro parziale, e il lavoro parziale sta nel registro del
    # ticket: suspend() rifiuta senza, quindi uno cosi' arriva solo da un grafo
    # scritto a mano o da un ticket svuotato dopo. E' il nodo che nessuno sa riprendere.
    if senza_registro := [n["id"] for n in data["nodes"]
                          if n["status"] == SUSPENDED and not worklog.written(ref, n["id"])]:
        avvisi.append(t("doctor.sospeso_senza_registro", elenco=", ".join(senza_registro),
                        heading=t("heading.lavorazione")))

    index = by_id(data)
    for nodo in claimed(data):
        chi = claims.holder(nodo).get("identity")
        autoverificati = [d for d in nodo["blockedBy"] if index[d].get("closedBy") == chi]
        if chi and autoverificati:
            avvisi.append(t("doctor.autoverifica", id=nodo["id"], chi=chi, elenco=", ".join(autoverificati)))

    radice = ref.workspace.project_root
    try:
        grafo = ref.json_path.resolve().relative_to(radice.resolve()).as_posix()
    except ValueError:
        grafo = None
    sporchi = None   # il working tree non dipende dal nodo: si legge una volta, e solo se serve
    tracciati = gitscan.indice(radice)   # idem per l'indice (issue #35: erano processi per artefatto)
    for nodo in data["nodes"]:
        chiuso = nodo.get("closedAt")
        if nodo["status"] != "closed" or not chiuso or not nodo.get("artifacts"):
            continue
        mancanti = []
        non_tracciati = []
        tocchi = []
        base = gitscan.closing_commit(radice, grafo, nodo["id"], chiuso) if grafo else None
        cambiati = gitscan.postumi(radice, chiuso, base)
        if cambiati is not None and sporchi is None:
            sporchi = gitscan.non_committati(radice)
        for a in nodo["artifacts"]:
            try:
                # Una cartella e' un artefatto legittimo (close --artefatti research/b06):
                # conta come presente, e cambiata se lo e' un file sotto di lei.
                if not (radice / a).exists():
                    mancanti.append(a)
                    continue
                if tracciati is not None and not gitscan.contiene(tracciati, a):
                    non_tracciati.append(a)
                if cambiati is not None:
                    if gitscan.contiene(cambiati, a) or gitscan.contiene(sporchi, a):
                        tocchi.append(a)
                    continue
                # git non puo' verificare (repo non git O rev-list vuoto): ripiego sull'mtime.
                soglia = istante(chiuso)
                if soglia is None:
                    continue        # senza un istante leggibile non c'e' confronto da fare
                if datetime.fromtimestamp((radice / a).stat().st_mtime).astimezone() > soglia:
                    tocchi.append(a)
            except OSError as errore:
                avvisi.append(t("doctor.artefatto_non_ispezionabile", id=nodo["id"],
                                path=a, errore=errore))
        if mancanti:
            avvisi.append(t("doctor.artefatti_mancanti", id=nodo["id"], elenco=", ".join(mancanti)))
        if non_tracciati:
            avvisi.append(t("doctor.artefatti_non_tracciati", id=nodo["id"], elenco=", ".join(non_tracciati)))
        if tocchi:
            avvisi.append(t("doctor.ambito_toccato", id=nodo["id"], elenco=", ".join(tocchi)))

    # La forma di owner si rimette in pari da sola alla prima mutazione: qui si segnala
    # e basta. Un nodo senza chiave o con None e' un grafo vecchio legittimo.
    for nodo in data["nodes"]:
        grezzo = nodo.get("owner")
        canonico = owners_of(nodo)
        if grezzo is not None and grezzo != canonico:
            avvisi.append(t("doctor.owner_non_canonico", id=nodo["id"], chi=", ".join(canonico)))

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
