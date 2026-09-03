"""Orchestratore di deploy per il relay isolato (D02): rollout su una directory
versionata, restart della unit systemd dedicata, health check e rollback
automatico se il nuovo rilascio non risponde.

Stessa disciplina di A01/D01: verifica soltanto i riferimenti dichiarati
nell'ambiente, non seleziona ne' inventa un host, un hostname o un segreto.
Se manca un prerequisito, il deploy si rifiuta con la stessa forma diagnostica
di A01 invece di tentare comunque con un valore di comodo.

Isolamento: unit systemd propria (atlas-relay.service), utente di sistema
proprio, porta locale propria (127.0.0.1). G02 ha smontato l'unico blocco
Caddy che il relay aveva insieme al webhook Telegram, ma quel blocco
esponeva tutto il servizio, non solo il webhook: il tunnel client-relay e il
pairing (D03/D05) restano chiamate in ingresso da un client remoto e senza
un reverse proxy pubblico davanti a questa porta non le raggiunge nessuno
(vedi relay/README.md, "La parte pubblica che resta", G03). Nessun comando
qui nomina o tocca la unit o il blocco Caddy del bot WhenAGI o di Claude
Proxy.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Riferimenti da dichiarare nell'ambiente prima del deploy. ATLAS_RELAY_TOKEN_REF
# viene da A01/D01; ATLAS_RELAY_DEPLOY_HOST (bersaglio ssh, es. "utente@host") e
# ATLAS_RELAY_DEPLOY_PATH (directory base sul remote) sono i due che D02 aggiunge,
# seguendo la stessa convenzione: un riferimento, non un segreto o una risorsa
# scelta qui.
PREREQUISITI = [
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
    # Tutti i moduli del relay, presi dalla cartella invece che da un elenco
    # scritto a mano. L'elenco a mano ha dimenticato un modulo quattro volte
    # (tunnel.py, pairing.py, throttle.py, devices.py) e il guasto e' sempre lo
    # stesso: il servizio non parte, perche' un 'import' fallisce prima di
    # main(). Al momento di scrivere questa riga ne mancavano altri tre
    # (peers.py, protocol_watch.py, view_command.py), aggiunti da nodi che non
    # sapevano dell'elenco. Chi aggiunge un modulo non deve ricordarsi di
    # nulla: se e' un .py del relay, parte.
    #
    # Esclusioni, una sola e dichiarata: deploy.py e' l'orchestratore, gira da
    # questa parte e sul remote non serve a niente.
    sorgenti = sorted(str(percorso) for percorso in ROOT.glob("*.py")
                      if percorso.name != "deploy.py")
    _run(["rsync", "-az", *sorgenti, f"{host}:{destinazione}/"], runner)
    _run(["ssh", host, "ln", "-sfn", destinazione, f"{base}/current"], runner)
    return destinazione


def riavvia_servizio(env: dict, runner=subprocess.run) -> None:
    host = env["ATLAS_RELAY_DEPLOY_HOST"]
    _run(["ssh", host, "sudo", "systemctl", "restart", "atlas-relay"], runner)


def url_di_salute(env: dict) -> str:
    """L'indirizzo a cui bussare per sapere se il servizio e' vivo.

    Non e' sempre 127.0.0.1: il bind e' una scelta dell'installazione
    (ATLAS_RELAY_HOST nella unit), e un relay che ascolta solo sull'indirizzo
    di una VPN non risponde sul loopback. Cercarlo dove non e' faceva fallire
    ogni health check e scattare un rollback su un rilascio sano, senza che
    niente nominasse la causa.
    """
    host = env.get("ATLAS_RELAY_HOST") or "127.0.0.1"
    porta = env.get("ATLAS_RELAY_PORT") or "8765"
    return f"http://{host}:{porta}/healthz"


def controlla_salute(env: dict, tentativi: int = TENTATIVI_HEALTH,
                      attesa: float = ATTESA_HEALTH, runner=subprocess.run,
                      sleep=time.sleep) -> bool:
    """Nessuna porta pubblica a cui bussare da qui (G02 ha smontato l'unica che
    il relay aveva): il controllo passa dalla stessa sessione ssh che ha gia'
    riavviato la unit, verso l'indirizzo su cui il servizio ascolta davvero."""
    host = env["ATLAS_RELAY_DEPLOY_HOST"]
    url = url_di_salute(env)
    for tentativo in range(tentativi):
        esito = runner(["ssh", host, "curl", "-sf", "-o", "/dev/null", url],
                       capture_output=True, text=True)
        if esito.returncode == 0:
            return True
        if tentativo < tentativi - 1:
            sleep(attesa)
    print(f"  il servizio non ha risposto su {url} dopo {tentativi} tentativi")
    return False


def rollback(env: dict, precedente: str, runner=subprocess.run) -> None:
    host = env["ATLAS_RELAY_DEPLOY_HOST"]
    base = env["ATLAS_RELAY_DEPLOY_PATH"]
    _run(["ssh", host, "ln", "-sfn", precedente, f"{base}/current"], runner)
    riavvia_servizio(env, runner)


def deploy(env: dict, versione: str, runner=subprocess.run, sleep=time.sleep) -> None:
    verifica_prerequisiti(env)
    precedente = rilascio_precedente(env, runner)
    rilascia(env, versione, runner)
    riavvia_servizio(env, runner)
    if controlla_salute(env, runner=runner, sleep=sleep):
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
