"""Entrypoint del CLI globale: main:run e' il target invocato dallo zipapp dist/atlas.

Il template di zipapp chiama la funzione senza usarne il valore di ritorno ('modulo.fn()',
non 'sys.exit(modulo.fn())'): run() fa l'exit da sola, altrimenti il processo
terminerebbe sempre con codice 0 anche sugli errori.
"""
from __future__ import annotations

import sys

from .dispatch import main


def _uscita_utf8() -> None:
    """Forza stdout e stderr a UTF-8, prima che venga stampato qualsiasi cosa.

    Su una console vera Python scrive gia' in Unicode, ma appena l'output finisce in
    una pipe o in un file torna alla codifica di sistema: su Windows e' cp1252, che
    non sa rappresentare la freccia di 'atlas update' ne' i filetti di 'atlas how-to'.
    Il comando moriva con UnicodeEncodeError, e nel caso di update subito dopo aver
    sostituito l'eseguibile. 'backslashreplace' e' l'ultima rete, per flussi che a
    UTF-8 non si lasciano riconfigurare: meglio un carattere brutto di un crash.
    """
    for flusso in (sys.stdout, sys.stderr):
        try:
            flusso.reconfigure(encoding="utf-8")
        except (AttributeError, OSError, ValueError):
            pass
        else:
            continue
        try:
            flusso.reconfigure(errors="backslashreplace")
        except (AttributeError, OSError, ValueError):
            pass


def run() -> None:
    _uscita_utf8()
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    run()
