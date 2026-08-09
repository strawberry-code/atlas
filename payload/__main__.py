#!/usr/bin/env python3
"""Entrypoint del motore dentro l'archivio .atlas/atlas.

Non tocca sys.path: zipapp ci mette da solo la radice dell'archivio, quindi
'core' e' un package importabile sia quando l'archivio viene eseguito, sia
quando uno script di mutazione se lo mette in sys.path per fare
'from core import mutate'. E' la ragione per cui il motore puo' essere un
file solo senza che gli script dell'utente cambino una riga.
"""
from core.cli import main

raise SystemExit(main())
