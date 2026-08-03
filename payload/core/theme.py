"""Tema slate: la sola cosa che sa che aspetto ha la dashboard.

Il colore porta lo stato, la forma porta il ramo. Uno stato si riconosce anche in
scala di grigi, perche' ogni stato ha il suo glifo oltre al suo colore.
"""
from __future__ import annotations

INK = "#1f2933"
MUTED = "#64748b"
FAINT = "#94a3b8"
BORDER = "#dde3ea"
EDGE = "#cbd5e1"
ACCENT = "#4f46e5"

# stato visivo -> bordo, riempimento, testo, glifo, chiave-etichetta (in strings.py), tratteggio
STATE = {
    "frontier": ("#b7791f", "#fffbeb", "#8a5a12", "▲", "state.frontier", None),
    "claimed": ("#4f46e5", "#eef2ff", "#3730a3", "⬤", "state.claimed", None),
    "closed": ("#0f766e", "#f0fdfa", "#115e59", "✓", "state.closed", None),
    "blocked": ("#cbd5e1", "#f8fafc", "#64748b", "·", "state.blocked", None),
    "out-of-scope": ("#cbd5e1", "#ffffff", "#94a3b8", "✕", "state.out_of_scope", "4 3"),
}

ORDER = ["frontier", "claimed", "blocked", "closed", "out-of-scope"]


def state_of(node: dict, front_ids: set[str]) -> str:
    """Lo stato visivo non e' lo stato del nodo: 'open' si biforca in prendibile o bloccato."""
    if node["status"] in ("closed", "out-of-scope"):
        return node["status"]
    if node["status"] == "claimed":
        return "claimed"
    return "frontier" if node["id"] in front_ids else "blocked"


CSS = f"""
*{{box-sizing:border-box}}
body{{margin:0;background:#f6f8fa;color:{INK};
  font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Inter,system-ui,sans-serif}}
header{{padding:26px 34px 4px;background:#fff;border-bottom:1px solid {BORDER}}}
h1{{margin:0;font-size:19px;font-weight:600;letter-spacing:-.01em}}
.sub{{margin:4px 0 0;color:{FAINT};font-size:12.5px}}
.sub code{{background:#eef2f6;border-radius:4px;padding:1px 5px;font-size:11.5px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(268px,1fr));
  gap:14px;padding:20px 34px 6px;align-items:start}}
.box{{background:#fff;border:1px solid {BORDER};border-radius:10px;padding:14px 16px}}
h2{{margin:0 0 10px;font-size:10.5px;font-weight:600;letter-spacing:.09em;
  color:{FAINT};text-transform:uppercase}}
ul{{margin:0;padding:0;list-style:none}}
li{{padding:3px 0;color:{MUTED};font-size:13px;display:flex;gap:8px;align-items:baseline}}
li b{{color:{INK};font-weight:500}}
.mono{{font:11.5px ui-monospace,SFMono-Regular,Menlo,monospace;color:{MUTED}}}
.tag{{margin-left:auto;font-size:11px;color:{FAINT};white-space:nowrap}}
.track{{height:7px;background:#eef2f6;border-radius:99px;overflow:hidden;margin:2px 0 10px}}
.fill{{height:100%;background:#0f766e;border-radius:99px}}
.pct{{font-size:22px;font-weight:600;letter-spacing:-.02em}}
.pct span{{font-size:12.5px;font-weight:400;color:{FAINT};margin-left:6px}}
.dest{{margin:8px 0 0;color:{MUTED};font-size:12.5px;line-height:1.45}}
.dot{{width:9px;height:9px;border-radius:3px;flex:none;display:inline-block}}
.legend{{display:flex;flex-wrap:wrap;gap:16px;padding:14px 34px 4px;
  color:{FAINT};font-size:12px;align-items:center}}
.legend span{{display:flex;gap:6px;align-items:center}}
.wrap{{overflow-x:auto;padding:10px 34px 34px}}
.canvas{{background:#fff;border:1px solid {BORDER};border-radius:10px;padding:8px}}
.nid{{font:600 11px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.02em}}
.nty{{font:10.5px -apple-system,system-ui,sans-serif}}
.ntt{{font:12.5px -apple-system,system-ui,sans-serif}}
.ndp{{font:10px ui-monospace,SFMono-Regular,Menlo,monospace}}
.n{{cursor:pointer}}
.n rect.card{{transition:none}}
.n:hover rect.card{{stroke-width:2.2}}
footer{{padding:0 34px 30px;color:{FAINT};font-size:11.5px}}
a{{text-decoration:none}}
"""
