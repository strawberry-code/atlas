"""'atlas list': i progetti registrati, il loro stato dal vivo, --prune per pulire."""
from __future__ import annotations

from pathlib import Path

from . import registry
from .strings import t


def scheda_progetto(slug: str) -> int:
    """'atlas list <slug>': la scheda di un progetto solo."""
    path = registry.resolve(slug)
    if path is None:
        # Uno slug sbagliato e' un errore di battitura, non un guasto: prima usciva
        # come AttributeError su None, cioe' un traceback per una lettera storta.
        noti = ", ".join(sorted(registry.load()["projects"])) or t("list.nessuno")
        print(t("list.slug_ignoto", slug=slug, elenco=noti))
        return 1
    print(t("list.scheda", slug=slug, path=path, stato=registry.status_of(path)))
    return 0


def cmd_list(args) -> int:
    if slug := getattr(args, "slug", None):
        return scheda_progetto(slug)
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
        righe.append((slug, voce["path"], registry.status_of(path)))

    largh_slug = max(len(r[0]) for r in righe)
    largh_path = max(len(r[1]) for r in righe)
    print()
    for slug, path, stato in righe:
        print(f"  {slug.ljust(largh_slug)}   {path.ljust(largh_path)}   {stato}")
    print()
    return 0
