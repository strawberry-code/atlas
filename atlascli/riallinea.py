"""Rimette in pari i progetti registrati dopo che il CLI si e' aggiornato.

Sta fuori da self_update.py per due motivi. Il primo e' di mestiere: quello
scarica e sostituisce un eseguibile, questo cammina sul registro e tocca i
progetti. Il secondo decide il disegno: il riallineamento non puo' girare in
questo processo. Skill, CONTRACT.md e README arrivano dal payload compilato
dentro l'eseguibile, e questo processo e' ancora la versione appena sostituita
sul disco; scrivere di qui installerebbe nei progetti la versione da cui si sta
scappando. Quindi si invoca l'eseguibile nuovo, una volta per progetto.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from . import hook, registry
from .errori import ErroreAtlas, leggi_json
from .install_cmd import BEGIN
from .strings import t
from .version import current_version

# Un install non chiede niente con --yes e non parla con la rete: se dopo tre
# minuti un progetto non ha finito, e' bloccato su qualcosa che non e' nostro.
TIMEOUT = 180


def _scelte(target: Path) -> list[str]:
    """I flag che preservano com'era installato questo progetto.

    Un aggiornamento rinfresca quel che il progetto ha, non aggiunge quel che
    non ha mai avuto: il registro non ricorda chi era stato installato con
    --no-hooks o --no-claude-md, ma il progetto lo dice guardandolo. Un
    settings.json illeggibile vale come 'niente hook': e' un file di Claude
    Code, non nostro, e non deve far fallire il riallineamento degli altri.
    """
    flag = []
    settings = target / ".claude" / "settings.json"
    gruppi = []
    if settings.is_file():
        try:
            gruppi = leggi_json(settings, "errore.settings_rotto").get("hooks", {}).get("SessionEnd", [])
        except ErroreAtlas:
            gruppi = []
    if not any(hook.nostro(g) for g in gruppi):
        flag.append("--no-hooks")
    claude_md = target / "CLAUDE.md"
    if not (claude_md.is_file() and BEGIN in claude_md.read_text(encoding="utf-8", errors="replace")):
        flag.append("--no-claude-md")
    return flag


def _motivo(esito: subprocess.CompletedProcess) -> str:
    """La riga che dice cosa e' andato storto, senza rovesciare l'output intero."""
    for flusso in (esito.stderr, esito.stdout):
        for riga in (flusso or "").splitlines():
            if riga.strip():
                return riga.strip()
    return t("riallinea.senza_messaggio", codice=esito.returncode)


def riallinea(eseguibile: Path, *, solo_indietro: bool = False) -> None:
    """Passa i progetti registrati uno per uno, senza fermarsi al primo guasto.

    Un progetto sparito dal disco, o rimasto senza .atlas/config.json perche'
    disinstallato, non e' un errore da segnalare come tale: si dice che e' stato
    saltato e si va avanti. L'aggiornamento del CLI e' gia' riuscito, e nessun
    progetto puo' rimetterlo in discussione.

    Con solo_indietro si toccano i soli progetti la cui versione registrata non e'
    quella di adesso. Serve quando l'eseguibile e' gia' all'ultima versione e non
    c'e' nessun download a dire che qualcosa e' cambiato: senza, chi ha aggiornato
    partendo da una versione che ancora non riallineava resterebbe indietro per
    sempre, perche' da li' in poi ogni update direbbe solo 'sei gia' aggiornato'.
    Il confronto vale solo in quel caso: dopo un aggiornamento vero questo processo
    e' ancora la versione di prima, e current_version() direbbe il falso.
    """
    progetti = sorted(registry.load()["projects"].items())
    if solo_indietro:
        adesso = current_version()
        progetti = [(slug, voce) for slug, voce in progetti if voce.get("version") != adesso]
    if not progetti:
        return
    print(t("riallinea.intestazione", n=len(progetti)))
    for slug, voce in progetti:
        target = Path(voce["path"])
        stato = registry.status_of(target)
        if stato != registry.STATO_OK:
            print(t("riallinea.saltato", slug=slug, motivo=stato))
            continue
        comando = [sys.executable, str(eseguibile), "install", str(target), "--yes", *_scelte(target)]
        try:
            esito = subprocess.run(comando, capture_output=True, text=True, timeout=TIMEOUT)
        except (subprocess.TimeoutExpired, OSError) as errore:
            print(t("riallinea.errore", slug=slug, motivo=errore))
            continue
        if esito.returncode == 0:
            print(t("riallinea.ok", slug=slug))
        else:
            print(t("riallinea.errore", slug=slug, motivo=_motivo(esito)))
    print()
