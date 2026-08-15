"""'atlas update': aggiorna il CLI globale, mai i progetti.

Scarica l'ultima release da GitHub, verifica lo sha256, sostituisce l'eseguibile
in corsa con uno scambio atomico (os.replace sullo stesso filesystem). Mai una
scrittura in place sul file che sta girando: romperebbe sia questo processo sia
una seconda invocazione di atlas lanciata a meta' del download.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from . import registry
from .strings import t
from .version import current_version

REPO = "strawberry-code/atlas"
DEFAULT_BASE_URL = "https://api.github.com"
USER_AGENT = "atlas-cli"  # GitHub risponde 403 alle richieste senza User-Agent
# Un eseguibile che si riscrive da solo e' il pezzo piu' delicato del prodotto:
# 40 MB bastano a un binario che oggi ne pesa meno di uno, e oltre quella soglia
# si smette di leggere invece di riempire la memoria con quel che manda il server.
TETTO_DOWNLOAD = 40 * 1024 * 1024


def _base_url() -> str:
    return os.environ.get("ATLAS_UPDATE_BASE_URL", DEFAULT_BASE_URL)


def _in_chiaro(url: str) -> bool:
    """Vero se l'URL non e' https e non punta al server di prova locale.

    L'indirizzo da cui scarichiamo arriva dal JSON della release, cioe' da fuori:
    seguirlo in chiaro significa lasciare che chi sta sulla tratta decida quale
    eseguibile finisce al posto di questo. L'eccezione e' il fixture dei test,
    che parla http su localhost e non esce dalla macchina.
    """
    if url.startswith("https://"):
        return False
    resto = url.split("://", 1)[-1]
    ospite = resto.split("/", 1)[0].split(":", 1)[0]
    return ospite not in ("127.0.0.1", "localhost", "::1")


def _get_json(url: str) -> dict:
    richiesta = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(richiesta, timeout=15) as risposta:
        return json.loads(risposta.read().decode("utf-8"))


def _get_bytes(url: str) -> bytes:
    """Scarica, rifiutando il testo in chiaro e fermandosi al tetto di dimensione.

    Il controllo sullo schema sta qui e non nel chiamante perche' urllib segue i
    redirect da solo: e' l'URL finale, quello che apriamo davvero, a dover essere
    https, e questo e' l'unico punto che lo vede.
    """
    if _in_chiaro(url):
        raise ValueError(t("update.url_non_sicuro", url=url))
    richiesta = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(richiesta, timeout=30) as risposta:
        if _in_chiaro(risposta.geturl()):                    # redirect che declassa a http
            raise ValueError(t("update.url_non_sicuro", url=risposta.geturl()))
        blob = risposta.read(TETTO_DOWNLOAD + 1)
    if len(blob) > TETTO_DOWNLOAD:
        raise ValueError(t("update.troppo_grande", tetto=TETTO_DOWNLOAD // (1024 * 1024)))
    return blob


def _parse_version(v: str) -> tuple:
    parti = []
    for pezzo in v.lstrip("v").split("."):
        cifre = "".join(c for c in pezzo if c.isdigit())
        parti.append(int(cifre) if cifre else 0)
    return tuple(parti)


def _asset_url(release: dict, nome: str) -> str | None:
    for asset in release.get("assets", []):
        if asset["name"] == nome:
            return asset["browser_download_url"]
    return None


def _adesso() -> str:
    """Timestamp ISO8601 UTC, compatibile con registry._adesso()."""
    return datetime.now(timezone.utc).isoformat()


def _tempo_passato_secondi(timestamp_iso: str) -> float:
    """Secondi tra un timestamp ISO8601 UTC e ora."""
    try:
        passato = datetime.fromisoformat(timestamp_iso)
        return (datetime.now(timezone.utc) - passato).total_seconds()
    except (ValueError, TypeError):
        return float('inf')  # timestamp invalido: tratta come scaduto


def check_for_update() -> str | None:
    """Controlla se c'e' una versione piu' recente, cacheato per 24 ore.

    Ritorna la versione nuova se disponibile e piu' recente della corrente,
    altrimenti None. Gli errori di rete non sollevano eccezioni: la funzione
    ritorna None silenziosamente.
    """
    attuale = current_version()
    data = registry.load()

    # Controlla se la cache e' ancora fresca (< 24 ore)
    ultimo_check = data.get("last_update_check")
    versione_nota = data.get("latest_known_version")

    if ultimo_check and versione_nota:
        secondi_passati = _tempo_passato_secondi(ultimo_check)
        if secondi_passati < 86400:  # 24 * 60 * 60
            if _parse_version(versione_nota) > _parse_version(attuale):
                return versione_nota
            return None

    # Cache assente o scaduta: consulta la rete
    try:
        release = _get_json(f"{_base_url()}/repos/{REPO}/releases/latest")
        nuova = release.get("tag_name", "").lstrip("v")

        # Aggiorna la cache indipendentemente dal risultato, toccando solo i suoi
        # campi: fra la load() qui sopra e adesso e' passata una chiamata di rete,
        # e in quel tempo un altro comando puo' aver registrato un progetto.
        aggiornamento = {"last_update_check": _adesso()}
        if nuova:
            aggiornamento["latest_known_version"] = nuova
        registry.aggiorna_cache(aggiornamento)

        if nuova and _parse_version(nuova) > _parse_version(attuale):
            return nuova
        return None
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError):
        # Errore di rete: registra comunque il timestamp per evitare retry infiniti
        registry.aggiorna_cache({"last_update_check": _adesso()})
        return None


def cmd_update(args) -> int:
    attuale = current_version()
    try:
        release = _get_json(f"{_base_url()}/repos/{REPO}/releases/latest")
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as errore:
        print(t("update.errore_rete", errore=errore), file=sys.stderr)
        return 1

    ultima = release.get("tag_name", "").lstrip("v")
    if not ultima:
        print(t("update.senza_tag"), file=sys.stderr)
        return 1
    if _parse_version(ultima) <= _parse_version(attuale):
        print(t("update.gia_ultima", versione=attuale))
        return 0

    asset_url = _asset_url(release, "atlas")
    sha_url = _asset_url(release, "atlas.sha256")
    if not asset_url:
        print(t("update.asset_assente", versione=ultima), file=sys.stderr)
        return 1
    # L'impronta non e' un di piu' quando c'e': senza, non si sa cosa si sta per
    # mettere al posto dell'eseguibile, e una release pubblicata dimenticando
    # atlas.sha256 diventerebbe un aggiornamento cieco che riesce in silenzio.
    if not sha_url:
        print(t("update.sha_assente", versione=ultima), file=sys.stderr)
        return 1

    try:
        blob = _get_bytes(asset_url)
        atteso = _get_bytes(sha_url).decode("utf-8", errors="replace").split()
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as errore:
        print(t("update.errore_rete", errore=errore), file=sys.stderr)
        return 1
    if not blob:
        print(t("update.download_vuoto"), file=sys.stderr)
        return 1
    if not atteso or len(atteso[0]) != 64 or not all(c in "0123456789abcdefABCDEF" for c in atteso[0]):
        # asset sha vuoto, o una pagina di errore servita da un proxy al suo posto
        print(t("update.sha_illeggibile"), file=sys.stderr)
        return 1
    trovato = hashlib.sha256(blob).hexdigest()
    if atteso[0].lower() != trovato:
        print(t("update.sha_mismatch", atteso=atteso[0], trovato=trovato), file=sys.stderr)
        return 1

    target = Path(sys.argv[0]).resolve()
    tmp = tempfile.NamedTemporaryFile(dir=target.parent, delete=False)
    try:
        tmp.write(blob)
        tmp.close()
        os.chmod(tmp.name, 0o755)
        os.replace(tmp.name, target)
    except Exception:
        os.unlink(tmp.name)
        raise

    print(t("update.fatto", attuale=attuale, ultima=ultima, target=target))
    # L'import sta qui e non in testa: riallinea importa install_cmd, che tira
    # dentro il payload delle skill, e 'atlas update' non ha motivo di pagarlo
    # quando non c'e' niente da aggiornare.
    if getattr(args, "no_projects", False):
        _ricorda_riallineamento()
    else:
        from . import riallinea
        riallinea.riallinea(target)
    return 0


def _ricorda_riallineamento() -> None:
    """Con --no-projects, dice quali progetti restano indietro e con che comando.

    Il binario nuovo rigenera da se' ticket, mappa e dashboard alla prima occasione,
    ma skill, CONTRACT.md e il blocco in CLAUDE.md sono file veri dentro il progetto.
    Chi sceglie di non farli toccare dall'aggiornamento deve almeno sapere quali
    sono rimasti alla versione di prima, e con che comando si rimettono in pari.
    """
    progetti = sorted(registry.load()["projects"])
    if not progetti:
        return
    print(t("update.riallinea", n=len(progetti)))
    for slug in progetti[:5]:
        print(t("update.riallinea_riga", slug=slug))
    if len(progetti) > 5:
        print(t("update.riallinea_altri", n=len(progetti) - 5))
    print()
