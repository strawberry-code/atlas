"""Hook di fine sessione: rinfresca le dashboard e dice cosa resta rivendicato.

Non rilascia niente e non committa niente. La chiusura di un nodo resta un gesto
di chi lo lavora, mai di un hook: un hook che chiude al posto tuo scrive risposte
che nessuno ha scritto.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Il motore e' l'archivio .atlas/atlas, non una cartella di sorgenti accanto a questo
# file: zipimport lo rende importabile. Dai sorgenti (sviluppo e test) c'e' core/.
_MOTORE = ROOT / "atlas"
sys.path.insert(0, str(_MOTORE if _MOTORE.is_file() else ROOT))

from core import claims, render as dash  # noqa: E402
from core.config import Graph, Workspace  # noqa: E402
from core.store import load  # noqa: E402
from core.strings import set_language, t  # noqa: E402


def sessione_corrente() -> tuple[str | None, int | None]:
    payload = {}
    if not sys.stdin.isatty():
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except json.JSONDecodeError:
            payload = {}
    sid = payload.get("session_id") or os.environ.get("CLAUDE_CODE_SESSION_ID")
    pid = os.environ.get("CLAUDE_PID")
    return sid, int(pid) if pid and pid.isdigit() else None


def main() -> int:
    ws = Workspace(ROOT)
    set_language(ws.config.get("language", "it"))
    sid, _ = sessione_corrente()
    io = claims.identity()
    rimasti: list[str] = []
    for slug in ws.slugs():
        ref = Graph(ws, slug)
        data = load(ref.json_path)
        dash.write(ref, data)
        rimasti += [f"{slug}/{n['id']}" for n in data["nodes"]
                    if n["status"] == "claimed"
                    and (claims.holder(n).get("session") == sid or claims.holder(n).get("identity") == io)]
    if rimasti:
        print(t("hook.rivendicato", elenco=", ".join(rimasti)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
