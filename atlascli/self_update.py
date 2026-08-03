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
from pathlib import Path

from .version import current_version

REPO = "strawberry-code/atlas"
DEFAULT_BASE_URL = "https://api.github.com"
USER_AGENT = "atlas-cli"  # GitHub risponde 403 alle richieste senza User-Agent


def _base_url() -> str:
    return os.environ.get("ATLAS_UPDATE_BASE_URL", DEFAULT_BASE_URL)


def _get_json(url: str) -> dict:
    richiesta = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(richiesta, timeout=15) as risposta:
        return json.loads(risposta.read().decode("utf-8"))


def _get_bytes(url: str) -> bytes:
    richiesta = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(richiesta, timeout=30) as risposta:
        return risposta.read()


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


def cmd_update(args) -> int:
    attuale = current_version()
    try:
        release = _get_json(f"{_base_url()}/repos/{REPO}/releases/latest")
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as errore:
        print(f"\n  impossibile controllare la nuova versione: {errore}\n", file=sys.stderr)
        return 1

    ultima = release.get("tag_name", "").lstrip("v")
    if not ultima:
        print("\n  risposta di GitHub senza tag_name: aggiornamento annullato.\n", file=sys.stderr)
        return 1
    if _parse_version(ultima) <= _parse_version(attuale):
        print(f"\n  atlas è già alla versione più recente ({attuale})\n")
        return 0

    asset_url = _asset_url(release, "atlas")
    if not asset_url:
        print(f"\n  la release {ultima} non ha un asset 'atlas': aggiornamento annullato.\n", file=sys.stderr)
        return 1
    blob = _get_bytes(asset_url)
    if not blob:
        print("\n  download vuoto: aggiornamento annullato.\n", file=sys.stderr)
        return 1

    sha_url = _asset_url(release, "atlas.sha256")
    if sha_url:
        atteso = _get_bytes(sha_url).decode("utf-8").split()[0]
        trovato = hashlib.sha256(blob).hexdigest()
        if atteso != trovato:
            print(f"\n  sha256 non combacia (atteso {atteso}, trovato {trovato}): "
                  f"aggiornamento annullato.\n", file=sys.stderr)
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

    print(f"\n  atlas {attuale} → {ultima}  ({target})\n")
    return 0
