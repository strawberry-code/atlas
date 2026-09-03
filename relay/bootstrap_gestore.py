"""Attribuzione del gestore (A03): comando locale, si lancia una volta sola.

Il gestore di questo relay non e' un valore scritto nel codice ne'
indovinabile (S11/3): nasce da un tap su un link Telegram monouso, con lo
stesso primitivo del pairing di un'installazione (relay/pairing.py). Questo
script gira sulla stessa macchina del servizio, con accesso diretto al file
di stato (nessuna rete in piu', nessun endpoint HTTP dedicato da esporre e
proteggere): stampa il link, e chi lo apre sul proprio telefono diventa il
gestore. Se un gestore e' gia' registrato non emette nulla di nuovo: il
ruolo non ruota da qui.

Uso, dopo il deploy (relay/deploy.py), sullo stesso ambiente del servizio:

    ssh <host> 'cd <deploy-path>/current && python3 bootstrap_gestore.py'
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pairing  # noqa: E402


def link_di_bootstrap(env: dict) -> tuple[int, str]:
    """(codice di uscita, riga da stampare): 1/stderr se manca un
    prerequisito o il relay ha gia' un gestore, 0/stdout col link altrimenti.
    Pura sull'ambiente passato, cosi' i test non toccano 'os.environ' vero
    (stessa forma di 'deploy.deploy(env, ...)')."""
    store = pairing.costruisci_da_ambiente(env)
    if store is None:
        return 1, "TELEGRAM_BOT_TOKEN_REF o TELEGRAM_BOT_USERNAME mancanti: nessun bot da collegare."
    codice = store.emetti_bootstrap_gestore()
    if codice is None:
        return 1, "Questo relay ha gia' un gestore: non se ne emette un secondo."
    return 0, f"https://t.me/{env['TELEGRAM_BOT_USERNAME']}?start={codice}"


def main(argv: list[str] | None = None) -> int:
    esito, riga = link_di_bootstrap(dict(os.environ))
    print(riga, file=sys.stderr if esito else sys.stdout)
    return esito


if __name__ == "__main__":
    raise SystemExit(main())
