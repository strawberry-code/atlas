"""'atlas list': i progetti registrati, il loro stato dal vivo, --prune per pulire."""
from __future__ import annotations

from pathlib import Path

from . import registry
from .strings import t


def scheda_progetto(slug: str) -> int:
    """'atlas <slug>' senza verbo: scheda informativa invece di un errore secco."""
    path = registry.resolve(slug)
    stato = registry.status_of(path)
    versione = registry.installed_version(path) or "-"
    print(t("list.scheda", slug=slug, path=path, stato=stato, versione=versione))
    return 0


def cmd_list(args) -> int:
    if getattr(args, "prune", False):
        tolti = registry.prune()
        if tolti:
            print(t("list.prune_fatto", elenco=", ".join(tolti)))
        else:
            print(t("list.prune_niente"))
        return 0

    progetti = registry.load()["projects"]
    if not progetti:
        print(t("list.vuoto"))
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
