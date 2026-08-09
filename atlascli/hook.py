"""L'hook SessionEnd di Atlas dentro .claude/settings.json.

Quel file appartiene a Claude Code, non ad Atlas: dentro ci stanno anche gli hook di
altri, e vanno lasciati esattamente come sono. Da qui passano le tre operazioni che
li riguardano, cioe' riconoscere il nostro, rimetterlo al posto giusto, e toglierlo.

Sta fuori da install_cmd.py perche' e' un blocco che si ragiona da solo, e perche'
la sua parte piu' delicata, il riconoscimento, e' gia' stata sbagliata una volta.
"""
from __future__ import annotations

import json
from pathlib import Path

from .errori import ErroreAtlas, leggi_json

DIRNAME = ".atlas"
# Un comando, non uno script copiato nel progetto: dalla 0.7 il motore e' l'eseguibile.
COMANDO = "atlas render --all"


def nostro(gruppo: dict) -> bool:
    """Vero se questo gruppo SessionEnd lo ha messo Atlas, adesso o in una 0.6.

    Fino alla 0.6 l'hook era uno script dentro .atlas/, e il riconoscimento cercava
    quella cartella. Dalla 0.7 e' un comando, quindi cercare la cartella non trovava
    piu' nulla: ogni install ne accodava uno in piu' e l'uninstall non ne toglieva
    nessuno. Si riconoscono entrambe le forme, cosi' un progetto che arriva dalla 0.6
    si ritrova l'hook morto sostituito invece che affiancato.
    """
    testo = json.dumps(gruppo)
    return COMANDO in testo or f"{DIRNAME}/hooks" in testo


def elenco_aggiornato(gruppi: list, messaggio: str) -> list:
    """L'elenco SessionEnd con un hook nostro solo, in fondo, e gli altri intatti.

    Si riscrive l'elenco invece di accodare: accodare significa dipendere dal
    riconoscimento del gia'-fatto, e quando quel riconoscimento sbaglia il difetto
    non e' un hook mancante ma un hook in piu' a ogni install, che nessuno nota.
    """
    nuovo = {"hooks": [{"type": "command", "command": COMANDO, "statusMessage": messaggio}]}
    return [g for g in gruppi if not nostro(g)] + [nuovo]


def sgancia(path: Path) -> None:
    """Toglie gli hook di Atlas da settings.json e lascia il file al suo proprietario.

    Se non si legge si prosegue con un avviso, perche' quando l'uninstall arriva qui
    ha gia' cancellato dei file: fermarsi lascerebbe il progetto a meta' del guado per
    colpa di un file che non e' nostro.
    """
    if not path.is_file():
        return
    try:
        dati = leggi_json(path, "errore.settings_rotto")
    except ErroreAtlas as errore:
        print(f"  {errore}")
        return
    gruppi = dati.get("hooks", {}).get("SessionEnd", [])
    restanti = [g for g in gruppi if not nostro(g)]
    if restanti == gruppi:
        return
    dati["hooks"]["SessionEnd"] = restanti
    path.write_text(json.dumps(dati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
