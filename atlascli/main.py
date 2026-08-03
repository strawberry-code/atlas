"""Entrypoint del CLI globale: main:run e' il target invocato dallo zipapp dist/atlas.

Il template di zipapp chiama la funzione senza usarne il valore di ritorno ('modulo.fn()',
non 'sys.exit(modulo.fn())'): run() fa l'exit da sola, altrimenti il processo
terminerebbe sempre con codice 0 anche sugli errori.
"""
from __future__ import annotations

import sys

from .dispatch import main


def run() -> None:
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    run()
