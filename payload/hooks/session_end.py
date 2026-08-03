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
sys.path.insert(0, str(ROOT))

from core import claims, render as dash  # noqa: E402
from core.config import Graph, Workspace  # noqa: E402
from core.store import load  # noqa: E402


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
    sid, pid = sessione_corrente()
    rimasti: list[str] = []
    for slug in ws.slugs():
        ref = Graph(ws, slug)
        data = load(ref.json_path)
        dash.write(ref, data)
        rimasti += [f"{slug}/{n['id']}" for n in data["nodes"]
                    if n["status"] == "claimed"
                    and (claims.holder(n).get("session") == sid or claims.holder(n).get("pid") == pid)]
    if rimasti:
        print(f"Atlas: {', '.join(rimasti)} resta rivendicato. "
              f"Alla prossima sessione chiudilo con 'atlas close', oppure rilascialo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
