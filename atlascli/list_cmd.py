"""'atlas list': i progetti registrati, il loro stato dal vivo, --prune per pulire."""
from __future__ import annotations

from pathlib import Path

from . import registry


def scheda_progetto(slug: str) -> int:
    """'atlas <slug>' senza verbo: scheda informativa invece di un errore secco."""
    path = registry.resolve(slug)
    stato = registry.status_of(path)
    versione = registry.installed_version(path) or "-"
    print(f"\n  {slug}\n"
          f"  path      {path}\n"
          f"  stato     {stato}\n"
          f"  versione  {versione}\n\n"
          f"  Aggiorna con: atlas {slug} update\n")
    return 0


def cmd_list(args) -> int:
    if getattr(args, "prune", False):
        tolti = registry.prune()
        if tolti:
            print(f"\n  rimossi dal registro: {', '.join(tolti)}\n")
        else:
            print("\n  nessuna voce morta da rimuovere\n")
        return 0

    progetti = registry.load()["projects"]
    if not progetti:
        print("\n  nessun progetto registrato. Installa con 'atlas install <path>'.\n")
        return 0

    righe = []
    for slug, voce in sorted(progetti.items()):
        path = Path(voce["path"])
        stato = registry.status_of(path)
        versione = registry.installed_version(path) or "-"
        righe.append((slug, voce["path"], versione, stato))

    largh_slug = max(len(r[0]) for r in righe)
    largh_path = max(len(r[1]) for r in righe)
    print()
    for slug, path, versione, stato in righe:
        print(f"  {slug.ljust(largh_slug)}   {path.ljust(largh_path)}   {versione:<10} {stato}")
    print()
    return 0
