"""Numerazione degli script di mutazione: chi la legge e chi la cambia.

Atlas cambia la forma di un grafo solo con gli script numerati di .atlas/scripts/.
Quando due copie dello stesso grafo divergono, la procedura e' prendere come base
il grafo dell'altro e rinumerare i propri script in coda ai suoi: il calcolo delle
rinomine e' logica di ordinamento, non di parsing, e per questo sta qui in un file
a se' e non in cli.py, che e' un dispatcher.
"""
from __future__ import annotations

import re
from pathlib import Path

from .store import StateError
from .strings import t

NUMERO = "[0-9][0-9][0-9]-*.py"          # il glob dei file numerati

_FORMA = re.compile(r"[0-9]{3}-.+\.py")


def elenco(scripts_dir: Path) -> list[Path]:
    """Gli script numerati, in ordine di (numero, nome). Il numero sta davanti a
    larghezza fissa, quindi l'ordine lessicale del nome e' quello giusto."""
    return sorted(scripts_dir.glob(NUMERO), key=lambda p: p.name)


def prossimo(scripts_dir: Path) -> int:
    """Il numero da dare al prossimo script: il massimo esistente piu' uno, 1 se non ce n'e'."""
    presenti = elenco(scripts_dir)
    return int(presenti[-1].name[:3]) + 1 if presenti else 1


def _bersaglio_valido(path: Path) -> None:
    """Un bersaglio del renumber e' uno script numerato esistente, nient'altro."""
    if not _FORMA.fullmatch(path.name) or not path.is_file():
        raise StateError(t("renumber.non_numerato", nome=path.name))


def rinomine(scripts_dir: Path, bersagli: list[Path] | None = None) -> list[tuple[Path, Path]]:
    """Le rinomine da fare, in ordine, come coppie (da, a).

    Senza bersagli compatta la numerazione: gli script nell'ordine di elenco()
    prendono 1, 2, 3... Con bersagli sposta quei file in coda, nell'ordine in cui
    sono stati indicati, dopo il numero massimo fra gli altri. Il nome dopo il
    numero non cambia mai, e un file che avrebbe gia' il nome giusto non entra
    nell'elenco: le rinomine tornate sono solo quelle vere.
    """
    scripts_dir = scripts_dir.resolve()
    presenti = elenco(scripts_dir)
    if bersagli is None:
        bersagli = presenti
        altri: list[Path] = []
    else:
        # resolve() allinea i path del chiamante (che possono passare da una
        # cartella raggiungibile anche come symlink) a quelli del glob qui sotto:
        # due percorsi della stessa cartella devono essere lo stesso Path.
        bersagli = list(dict.fromkeys(b.resolve() for b in bersagli))
        for bersaglio in bersagli:
            _bersaglio_valido(bersaglio)
        altri = [p for p in presenti if p not in bersagli]
    base = max((int(p.name[:3]) for p in altri), default=0)
    rinumerate = []
    for pos, da in enumerate(bersagli):
        a = da.with_name(f"{base + 1 + pos:03d}{da.name[3:]}")
        if a != da:
            rinumerate.append((da, a))
    return rinumerate
