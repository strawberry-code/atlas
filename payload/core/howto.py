"""Tutto quel che serve a un agente per usare Atlas, in un comando solo.

Il contratto e' l'unica parte scritta a mano: comandi, mutazioni e skill si
generano per introspezione, quindi non possono divergere dal codice che
descrivono. Quando cambia un comando, un flag o il protocollo, la sola cosa da
aggiornare a mano e' templates/contract.{it,en}.md, che finisce qui integrale.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from . import mutate
from .config import Graph, Workspace
from .model import progress
from .store import load
from .strings import STRINGS, t


def contratto(ws: Workspace) -> str:
    """Quello installato nel progetto; se manca, il template nella lingua attiva."""
    path = ws.root / "CONTRACT.md"
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ws.template("contract.md").strip()


def mutazioni() -> list[str]:
    """Le funzioni di mutate che uno script puo' chiamare, con la firma vera.

    Il criterio e' 'prende g come primo parametro': e' quel che distingue un gesto
    da script dal resto del modulo, e non c'e' nessun elenco da tenere aggiornato.
    Vale anche per i gesti che mutate re-importa da un modulo spezzato (assign.py):
    chiedere in piu' che la funzione sia definita qui dentro faceva sparire da
    questo elenco le mutazioni vere il giorno in cui il file veniva diviso, cioe'
    proprio quando un agente aveva piu' bisogno di sapere che esistono.
    """
    righe = []
    for nome, funzione in vars(mutate).items():
        if nome.startswith("_") or not inspect.isfunction(funzione):
            continue
        firma = inspect.signature(funzione)
        if next(iter(firma.parameters), None) != "g":
            continue
        nuda = firma.replace(
            parameters=[p.replace(annotation=inspect.Parameter.empty) for p in firma.parameters.values()],
            return_annotation=inspect.Signature.empty)
        righe.append(f"    mutate.{nome}{nuda}")
        if (chiave := f"howto.mutate.{nome}") in STRINGS:   # senza voce esce la sola firma
            righe.append(f"        {t(chiave)}")
    return righe


def _descrizione(path: Path) -> str:
    """La riga 'description:' del frontmatter di una skill."""
    for riga in path.read_text(encoding="utf-8").splitlines()[:10]:
        if riga.startswith("description:"):
            return riga.split(":", 1)[1].strip()
    return ""


def skill(ws: Workspace) -> list[str]:
    cartelle = ws.root / "skills"
    if not cartelle.is_dir():
        return []
    lingua = ws.config.get("language", "it")
    righe = []
    for skill_dir in sorted(d for d in cartelle.iterdir() if d.is_dir()):
        path = skill_dir / "SKILL.md"
        if not path.is_file():                       # prima dell'install la copia localizzata non c'e' ancora
            path = skill_dir / f"SKILL.{lingua}.md"
        if path.is_file():
            righe.append(f"    {skill_dir.name}: {_descrizione(path)}")
    return righe


def rel(ws: Workspace, path: Path) -> Path:
    """Relativo alla radice del progetto: e' la forma che si digita, non quella assoluta."""
    try:
        return path.relative_to(ws.project_root)
    except ValueError:
        return path


def dove(ws: Workspace) -> list[str]:
    """I path che un agente deve saper trovare, risolti su questo progetto."""
    slugs = ws.slugs()
    if not slugs:
        return [t("howto.dove_nessun_grafo"), t("howto.dove_scripts", path=rel(ws, ws.scripts_dir))]
    attivo = ws.pinned() or (slugs[0] if len(slugs) == 1 else None)
    righe = []
    for slug in slugs:
        ref = Graph(ws, slug)
        fatti, totale = progress(load(ref.json_path))
        segno = "→" if slug == attivo else " "
        righe.append(t("howto.dove_grafo", segno=segno, slug=slug, fatti=fatti, totale=totale,
                       dir=rel(ws, ref.dir)))
    if attivo:
        ref = Graph(ws, attivo)
        righe += [t("howto.dove_json", path=rel(ws, ref.json_path)),
                  t("howto.dove_ticket", path=rel(ws, ref.tickets_dir)),
                  t("howto.dove_mappa", path=rel(ws, ref.map_path)),
                  t("howto.dove_dashboard", path=rel(ws, ref.dashboard_path))]
    righe.append(t("howto.dove_scripts", path=rel(ws, ws.scripts_dir)))
    return righe


def versione_motore() -> str:
    """La versione di chi sta girando, non un file nel progetto: dalla 0.7 il motore
    non abita piu' li' dentro, e un VERSION scritto sul disco mentirebbe al primo
    aggiornamento dell'eseguibile."""
    try:
        from atlascli.version import current_version
        return current_version()
    except ModuleNotFoundError:
        return (Path(__file__).resolve().parent.parent / "VERSION").read_text(encoding="utf-8").strip()


def show(ws: Workspace, aiuto: str) -> None:
    """Le sei sezioni, numerate perche' chi legge possa citarle."""
    versione = versione_motore()
    print()
    print(t("howto.intestazione", versione=versione, progetto=ws.config["project"],
            lingua=ws.config.get("language", "it")))
    print(t("howto.avvertenza"))

    print(t("howto.sezione", n=1, titolo=t("howto.titolo_contratto")))
    print(contratto(ws))
    print(t("howto.sezione", n=2, titolo=t("howto.titolo_comandi")))
    print(aiuto.rstrip())
    print(t("howto.sezione", n=3, titolo=t("howto.titolo_mutazioni")))
    print(t("howto.mutazioni_intro", path=rel(ws, ws.scripts_dir)))
    print("\n".join(mutazioni()))
    print(t("howto.sezione", n=4, titolo=t("howto.titolo_skill")))
    print("\n".join(skill(ws)) or t("howto.skill_nessuna"))
    print(t("howto.sezione", n=5, titolo=t("howto.titolo_dove")))
    print("\n".join(dove(ws)))
    print(t("howto.sezione", n=6, titolo=t("howto.titolo_primi_passi")))
    print(t("howto.primi_passi"))
    print()
