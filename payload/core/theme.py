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


SHADOW = "0 1px 2px rgba(15,23,42,.04), 0 8px 20px -12px rgba(15,23,42,.12)"
SHADOW_LIFT = "0 4px 10px rgba(15,23,42,.08), 0 14px 28px -12px rgba(15,23,42,.18)"

CSS = f"""
*{{box-sizing:border-box}}
body{{margin:0;background:#f4f6f8;color:{INK};
  font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Inter,system-ui,sans-serif}}
header{{padding:26px 34px 4px;background:#fff;border-bottom:1px solid {BORDER}}}
h1{{margin:0;font-size:19px;font-weight:600;letter-spacing:-.01em}}
.sub{{margin:4px 0 0;color:{FAINT};font-size:12.5px}}
.sub code{{background:#eef2f6;border-radius:4px;padding:1px 5px;font-size:11.5px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(268px,1fr));
  gap:16px;padding:22px 34px 8px;align-items:start}}
.box{{background:#fff;border:1px solid {BORDER};border-radius:12px;padding:16px 18px;
  box-shadow:{SHADOW}}}
h2{{margin:0 0 11px;font-size:10.5px;font-weight:600;letter-spacing:.09em;
  color:{FAINT};text-transform:uppercase}}
ul{{margin:0;padding:0;list-style:none}}
li{{padding:4px 6px;margin:0 -6px;border-radius:6px;color:{MUTED};font-size:13px;
  display:flex;gap:8px;align-items:baseline;transition:background-color .1s ease}}
li:hover{{background:#f8fafc}}
li b{{color:{INK};font-weight:500}}
.mono{{font:11.5px ui-monospace,SFMono-Regular,Menlo,monospace;color:{MUTED}}}
.tag{{margin-left:auto;font-size:11px;color:{FAINT};white-space:nowrap}}
.track{{height:7px;background:#eef2f6;border-radius:99px;overflow:hidden;margin:2px 0 10px}}
.fill{{height:100%;border-radius:99px;background:linear-gradient(90deg,#0f766e,#14b8a6)}}
.pct{{font-size:23px;font-weight:600;letter-spacing:-.02em}}
.pct span{{font-size:12.5px;font-weight:400;color:{FAINT};margin-left:6px}}
.dest{{margin:8px 0 0;color:{MUTED};font-size:12.5px;line-height:1.45}}
.dot{{width:9px;height:9px;border-radius:3px;flex:none;display:inline-block}}
.legend{{display:flex;flex-wrap:wrap;gap:10px;padding:16px 34px 6px;
  color:{MUTED};font-size:12px;align-items:center}}
.legend span{{display:flex;gap:6px;align-items:center;background:#fff;
  border:1px solid {BORDER};border-radius:99px;padding:5px 11px}}
.legend span.hint{{background:none;border:none;padding:5px 0;color:{FAINT}}}
.wrap{{overflow-x:auto;padding:12px 34px 34px}}
.canvas{{background:#fff;border:1px solid {BORDER};border-radius:12px;padding:10px;
  box-shadow:{SHADOW}}}
.nid{{font:600 11px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.02em}}
.nbadge{{font:10px ui-monospace,SFMono-Regular,Menlo,monospace}}
.ntt{{font:12.5px -apple-system,system-ui,sans-serif}}
.ndp{{font:10px ui-monospace,SFMono-Regular,Menlo,monospace}}
.n{{cursor:pointer;transition:opacity .12s ease,transform .12s ease;transform-box:fill-box;transform-origin:center}}
.n:hover{{transform:translateY(-1.5px)}}
.n rect.card{{filter:drop-shadow(0 1px 1px rgba(15,23,42,.05)) drop-shadow(0 3px 8px rgba(15,23,42,.06));
  transition:filter .12s ease,stroke-width .12s ease}}
.n:hover rect.card{{stroke-width:2.2;
  filter:drop-shadow(0 2px 2px rgba(15,23,42,.07)) drop-shadow(0 8px 16px rgba(15,23,42,.12))}}
path.edge{{transition:opacity .12s ease,stroke .12s ease,stroke-width .12s ease}}
svg:has(.n:hover) .n{{opacity:.35}}
svg:has(.n:hover) .n:hover{{opacity:1}}
svg:has(.n:hover) path.edge{{opacity:.15}}
footer{{padding:0 34px 30px;color:{FAINT};font-size:11.5px}}
a{{text-decoration:none}}
"""
