"""Fusione a tre vie di graph.json per id di nodo, in sola stdlib.

Git chiama il driver con tre path: %O (antenato), %A (nostra, che il driver
riscrive) e %B (loro). Parsa i tre JSON, fonde per id di nodo invece che per
riga e scrive in %A un JSON valido; se restano conflitti veri esce con codice
1 (git registra il conflitto) e li annota in un campo 'conflicts' (A04).

Regole da research/A01-divergenza.md: chiusura e claim sono blocchi atomici,
array fusi per elemento con set-merge che rispetta le cancellazioni,
meta.updated = massimo, owner rinormalizzato, ordine canonico per id, campi
nuovi (host/lease_until di L) conservati. Mai marker git: non parsa.
"""
from __future__ import annotations

import json
import sys

from .model import owners_of
from .store import CLAIMED, CLOSED, dumps
from .strings import t

# Il blocco che una close scrive in un colpo solo (claims.py:175-179): si fonde
# come oggetto unico, mai campo per campo (mischiare due chiusure non e' stato reale).
STATO = ("status", "assignee", "claim", "answer", "cost", "closedBy", "closedAt", "artifacts")
# Rumore locale del claim (B4 di A01): differenze qui vincono il nostro in silenzio.
RUMORE = {"pid", "session", "at", "heartbeat", "fingerprint"}


def merge(base: dict, ours: dict, theirs: dict) -> tuple[dict, list[dict]]:
    """Fonde tre grafi (dict) in (grafo_fuso, conflitti)."""
    segnali: list[dict] = []
    b, o, g3 = base or {}, ours or {}, theirs or {}
    ris: dict = {}
    for chiave in sorted(set(b) | set(o) | set(g3)):
        if chiave == "nodes":
            ris[chiave] = _fonde_nodi(b.get("nodes", []), o.get("nodes", []),
                                      g3.get("nodes", []), segnali)
        elif chiave == "meta":
            ris[chiave] = _fonde_meta(b.get(chiave, {}), o.get(chiave, {}),
                                      g3.get(chiave, {}), segnali)
        elif chiave in ("fog", "outOfScope"):
            ris[chiave] = _set_merge(b.get(chiave), o.get(chiave), g3.get(chiave))
        elif chiave == "schemaVersion":
            ris[chiave] = o.get(chiave, b.get(chiave, g3.get(chiave)))
        else:
            ris[chiave] = _fonde_valore(chiave, b.get(chiave), o.get(chiave),
                                        g3.get(chiave), segnali, None, chiave)
    for nodo in ris.get("nodes", []):
        nodo["owner"] = owners_of(nodo)
    if segnali:
        ris["conflicts"] = segnali
    return ris, segnali


def merge_files(base: str, ours: str, theirs: str) -> int:
    """Il driver per git: legge %O %A %B, scrive il risultato in %A, esce 0/1."""
    try:
        b, o, g3 = _leggi(base), _leggi(ours), _leggi(theirs)
    except ValueError as errore:
        print(t("merge.illeggibile", path=ours, dettaglio=errore), file=sys.stderr)
        return 1
    fuso, segnali = merge(b, o, g3)
    with open(ours, "w", encoding="utf-8") as fh:
        fh.write(dumps(fuso))
    for s in segnali:
        print(t("merge.conflitto", nodo=s["node"] or "-", campo=s["field"],
                tipo=s["type"]), file=sys.stderr)
    return 1 if segnali else 0


def _leggi(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            testo = fh.read()
    except OSError:
        return {}
    if not testo.strip():
        return {}
    letto = json.loads(testo)
    if not isinstance(letto, dict):
        raise ValueError("non è un oggetto JSON")
    return letto


def _fonde_nodi(nb: list, no: list, nt: list, segnali: list) -> list:
    ib = {n["id"]: n for n in nb}
    io = {n["id"]: n for n in no}
    it = {n["id"]: n for n in nt}
    return [_fonde_nodo(i, ib.get(i), io.get(i), it.get(i), segnali)
            for i in sorted(set(ib) | set(io) | set(it))]


def _fonde_nodo(nid: str, b: dict | None, o: dict | None, t: dict | None,
                segnali: list) -> dict:
    if b is None:
        if o is None:
            return t
        if t is None:
            return o
        b = {}
    if o is None:
        return t                        # cancellare non e' un gesto del motore: il nodo resta
    if t is None:
        return o
    if o == t or o == b or t == b:
        return o if o == t else (t if o == b else o)
    if _stato(b) != _stato(o) and _stato(b) != _stato(t) and _stato(o) != _stato(t):
        if o.get("status") == CLOSED and t.get("status") == CLOSED and _chiusura(o) != _chiusura(t):
            segnali.append(_conflitto(nid, "close", "concurrent close"))
        elif o.get("status") == CLAIMED and t.get("status") == CLAIMED \
                and (o.get("claim") or {}).get("identity") != (t.get("claim") or {}).get("identity"):
            segnali.append(_conflitto(nid, "claim.identity", "concurrent claim"))
        else:
            segnali.append(_conflitto(nid, "status", "divergent state"))
        return {**_solo_nonstato(b, o, t, segnali, nid), **_blocco(o)}
    return _fonde_dizionario(b, o, t, segnali, nid, "")


def _solo_nonstato(b: dict, o: dict, t: dict, segnali: list, nid: str) -> dict:
    ris = {}
    for chiave in sorted(set(b) | set(o) | set(t)):
        if chiave not in STATO:
            ris[chiave] = _fonde_valore(chiave, b.get(chiave), o.get(chiave),
                                        t.get(chiave), segnali, nid, chiave)
    return ris


def _blocco(nodo: dict) -> dict:
    return {k: nodo.get(k) for k in STATO if k in nodo}


def _stato(nodo: dict) -> dict:
    s = _blocco(nodo)                    # senza rumore locale del claim: per confrontare
    if isinstance(s.get("claim"), dict):
        s["claim"] = {k: v for k, v in s["claim"].items() if k not in RUMORE}
    return s


def _chiusura(nodo: dict) -> tuple:
    return tuple(nodo.get(k) for k in ("answer", "closedBy", "closedAt", "cost", "artifacts"))


def _fonde_meta(b: dict, o: dict, t: dict, segnali: list) -> dict:
    b, o, t = b or {}, o or {}, t or {}
    senza = lambda g: {k: v for k, v in g.items() if k != "updated"}
    ris = _fonde_dizionario(senza(b), senza(o), senza(t), segnali, None, "meta")
    date = [d for d in (b.get("updated"), o.get("updated"), t.get("updated")) if d]
    if date:
        ris["updated"] = max(date)      # "YYYY-MM-DD": lessicografico = cronologico
    return ris


def _fonde_dizionario(b: dict, o: dict, t: dict, segnali: list, nodo: str | None,
                      campo: str) -> dict:
    ris = {}
    for chiave in sorted(set(b) | set(o) | set(t)):
        esteso = f"{campo}.{chiave}" if campo else chiave
        ris[chiave] = _fonde_valore(chiave, b.get(chiave), o.get(chiave),
                                    t.get(chiave), segnali, nodo, esteso)
    return ris


def _fonde_valore(chiave: str, b, o, t, segnali: list, nodo: str | None, campo: str):
    if o == t:
        return o
    if b is not None and o == b:
        return t
    if b is not None and t == b:
        return o
    if o is None and isinstance(t, (dict, list)):
        return t                        # campo nuovo scritto solo dall'altro ramo: lo conservo
    if t is None and isinstance(o, (dict, list)):
        return o
    if isinstance(o, dict) and isinstance(t, dict):
        return _fonde_dizionario(b if isinstance(b, dict) else {},
                                 o, t, segnali, nodo, campo)
    if isinstance(o, list) and isinstance(t, list):
        return _set_merge(b if isinstance(b, list) else [], o, t)
    if chiave in RUMORE:
        return o                        # rumore locale: vince il nostro, senza conflitto
    segnali.append(_conflitto(nodo, campo or chiave, "value conflict"))
    return o


def _set_merge(b: list, o: list, t: list) -> list:
    """Tre vie per elementi: le aggiunte di entrambi entrano, un elemento di base
    sopravvive solo se nessuna parte lo ha tolto (la rimozione di un lato vale)."""
    b, o, t = b or [], o or [], t or []
    sopravvive = [x for x in b if x in o and x in t]
    aggiunte = []
    for elenco in (o, t):
        for x in elenco:
            if x not in b and x not in aggiunte:
                aggiunte.append(x)
    return sopravvive + aggiunte


def _conflitto(nodo: str | None, campo: str, tipo: str) -> dict:
    return {"node": nodo, "field": campo, "type": tipo}
