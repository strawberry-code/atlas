"""Orchestratore di deploy per il relay isolato (D02): rollout su una directory
versionata, restart della unit systemd dedicata, health check e rollback
automatico se il nuovo rilascio non risponde.

Stessa disciplina di A01/D01: verifica soltanto i riferimenti dichiarati
nell'ambiente, non seleziona ne' inventa un host, un hostname o un segreto.
Se manca un prerequisito, il deploy si rifiuta con la stessa forma diagnostica
di A01 invece di tentare comunque con un valore di comodo.

Isolamento: unit systemd propria (atlas-relay.service), utente di sistema
proprio, porta locale propria dietro un Caddyfile a parte
(Caddyfile.atlas-relay). Nessun comando qui nomina o tocca la unit o il blocco
Caddy del bot WhenAGI o di Claude Proxy.
"""
from __future__ import annotations

import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Riferimenti da dichiarare nell'ambiente prima del deploy. RELAY_HTTPS_HOSTNAME e
# ATLAS_RELAY_TOKEN_REF vengono da A01/D01; ATLAS_RELAY_DEPLOY_HOST (bersaglio ssh,
# es. "utente@host") e ATLAS_RELAY_DEPLOY_PATH (directory base sul remote) sono i
# due che D02 aggiunge, seguendo la stessa convenzione: un riferimento, non un
# segreto o una risorsa scelta qui.
PREREQUISITI = [
    "RELAY_HTTPS_HOSTNAME",
    "ATLAS_RELAY_TOKEN_REF",
    "ATLAS_RELAY_DEPLOY_HOST",
    "ATLAS_RELAY_DEPLOY_PATH",
]

TENTATIVI_HEALTH = 10
ATTESA_HEALTH = 2.0


class PrerequisitiMancanti(RuntimeError):
    pass


def verifica_prerequisiti(env: dict) -> None:
    mancanti = [nome for nome in PREREQUISITI if not env.get(nome)]
    if mancanti:
        raise PrerequisitiMancanti(
            "Prerequisiti relay mancanti: " + ", ".join(mancanti) + ". "
            "Configurare esplicitamente questi riferimenti approvati e riprovare; "
            "nessun host o hostname e' stato selezionato da qui."
        )


def _run(argv: list[str], runner=subprocess.run, **kwargs) -> subprocess.CompletedProcess:
    esito = runner(argv, **kwargs)
    if esito.returncode != 0:
        raise RuntimeError(f"comando fallito ({esito.returncode}): {' '.join(argv)}")
    return esito


def rilascio_precedente(env: dict, runner=subprocess.run) -> str | None:
    host = env["ATLAS_RELAY_DEPLOY_HOST"]
    base = env["ATLAS_RELAY_DEPLOY_PATH"]
    esito = runner(["ssh", host, "readlink", "-f", f"{base}/current"], capture_output=True, text=True)
    if esito.returncode != 0 or not esito.stdout.strip():
        return None
    return esito.stdout.strip()


def rilascia(env: dict, versione: str, runner=subprocess.run) -> str:
    """Copia il codice del relay in una directory versionata sul remote e sposta 'current'."""
    host = env["ATLAS_RELAY_DEPLOY_HOST"]
    base = env["ATLAS_RELAY_DEPLOY_PATH"]
    destinazione = f"{base}/releases/{versione}"
    _run(["ssh", host, "mkdir", "-p", destinazione], runner)
    # I quattro moduli che atlas_relay.py importa: se manca uno di questi sul
    # remote il servizio non si avvia nemmeno ('import' fallisce prima di
    # 'main()'). Visto con tunnel.py, dimenticato qui da D03 finche' D05 non
    # l'ha notato aggiungendo pairing.py alla stessa lista.
    sorgenti = [str(ROOT / "atlas_relay.py"), str(ROOT / "telegram_webhook.py"),
                str(ROOT / "tunnel.py"), str(ROOT / "pairing.py")]
    _run(["rsync", "-az", *sorgenti, f"{host}:{destinazione}/"], runner)
    _run(["ssh", host, "ln", "-sfn", destinazione, f"{base}/current"], runner)
    return destinazione


def riavvia_servizio(env: dict, runner=subprocess.run) -> None:
    host = env["ATLAS_RELAY_DEPLOY_HOST"]
    _run(["ssh", host, "sudo", "systemctl", "restart", "atlas-relay"], runner)


def controlla_salute(env: dict, tentativi: int = TENTATIVI_HEALTH,
                      attesa: float = ATTESA_HEALTH,
                      opener=urllib.request.urlopen, sleep=time.sleep) -> bool:
    url = f"https://{env['RELAY_HTTPS_HOSTNAME']}/healthz"
    for tentativo in range(tentativi):
        try:
            with opener(url, timeout=5) as risposta:
                if risposta.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        if tentativo < tentativi - 1:
            sleep(attesa)
    return False


def rollback(env: dict, precedente: str, runner=subprocess.run) -> None:
    host = env["ATLAS_RELAY_DEPLOY_HOST"]
    base = env["ATLAS_RELAY_DEPLOY_PATH"]
    _run(["ssh", host, "ln", "-sfn", precedente, f"{base}/current"], runner)
    riavvia_servizio(env, runner)


def deploy(env: dict, versione: str, runner=subprocess.run, opener=urllib.request.urlopen,
           sleep=time.sleep) -> None:
    verifica_prerequisiti(env)
    precedente = rilascio_precedente(env, runner)
    rilascia(env, versione, runner)
    riavvia_servizio(env, runner)
    if controlla_salute(env, opener=opener, sleep=sleep):
        return
    if precedente is None:
        raise RuntimeError("health check fallito e nessun rilascio precedente da ripristinare")
    rollback(env, precedente, runner)
    raise RuntimeError(f"health check fallito: rollback eseguito su {precedente}")


def main(argv: list[str] | None = None) -> int:
    import os
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("uso: python3 deploy.py <versione>", file=sys.stderr)
        return 1
    try:
        deploy(dict(os.environ), argv[0])
    except (PrerequisitiMancanti, RuntimeError) as errore:
        print(f"  {errore}", file=sys.stderr)
        return 1
    print("  deploy riuscito")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
