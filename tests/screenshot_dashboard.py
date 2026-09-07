"""Foto della dashboard Atlas, a fianco di quelle di Nodavia (V03, grafo
260906-grafite-dashboard). Rilanciabile con un comando solo:

    python3 tests/screenshot_dashboard.py --node-modules <cartella-con-node_modules>

Dipendenza dichiarata, non nascosta: le scene interattive (hover, selezione,
palline in movimento, scheda del ticket, tabella) servono un browser vero
pilotato da script, non solo uno screenshot statico (quello lo offre gia'
payload/core/view_capture.py, riusato qui SOLO per trovare il primo browser
gia' installato: mai un download). Lo strumento pilota quel browser con
'playwright-core' via Node.js. Ne' Node ne' playwright-core sono nel repo
(payload/ e atlascli/ restano a dipendenza zero, e i test qui non aggiungono
un node_modules versionato): in questa sessione erano installati nello
scratchpad di un'altra sessione, che sparisce quando la sessione finisce.
Passa la cartella che contiene 'node_modules/playwright-core' con
--node-modules, o imposta ATLAS_SHOT_NODE_MODULES: senza, lo strumento stampa
come procurarselo (playwright-core via npm, licenza MIT, nessuna build
nativa: pilota il Chrome/Edge/Chromium gia' installato via CDP) ed esce con
un codice diverso da zero, mai un traceback.

Le foto finiscono di default in
.atlas/graphs/260906-grafite-dashboard/notes/atlas/, a fianco di
notes/nodavia/ (C01). Il grafo primario (260906-grafite-dashboard) prende
tutte le scene; gli altri cinque grafi reali (16-34 nodi) prendono solo la
vista d'apertura, a riprova che il canvas regge taglie diverse. Una fixture
sintetica (nessun file reale del progetto) copre l'arco di ritorno: vedi
render_sintetico_ciclo() per il perche' non esiste un grafo vero con un ciclo.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from html import escape as _esc
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "payload"))

from core import mutate, render as dash                       # noqa: E402
from core import render_notifiche, render_panels, render_sheet, render_table  # noqa: E402
from core.config import Workspace                              # noqa: E402
from core.editor import editing                                 # noqa: E402
from core.model import claimed, frontier                        # noqa: E402
from core.render_owners import indice as owners_indice           # noqa: E402
from core.risorse import leggi_css_dashboard, leggi_js_dashboard  # noqa: E402
from core.store import StateError                               # noqa: E402
from core.strings import current                                # noqa: E402
from core.view_capture import _candidati as _browser_candidati   # noqa: E402

GRAFI_REALI = [
    "260825-sync-distribuita", "260830-atlas-automata", "260830-atlas-interactions",
    "260830-issue-reliability-and-flow", "260902-atlas-relay", "260906-grafite-dashboard",
]
PRIMARIO = "260906-grafite-dashboard"
NODO_PRIMARIO = "Q01"          # 3 blockedBy + 5 dipendenti: il fan-in/fan-out piu' ricco del grafo
VIEWPORT = {"width": 1600, "height": 1100}   # stessa finestra delle foto di Nodavia (canvas-contract.md)


def trova_browser() -> str | None:
    """Riusa la lista di candidati di view_capture.py (S6-bis/13): stesso ordine,
    nessun download. Qui serve il path eseguibile per playwright, non un
    sottoprocesso --screenshot."""
    for candidato in _browser_candidati():
        if sys.platform in ("darwin", "win32"):
            if Path(candidato).is_file():
                return candidato
        elif shutil.which(candidato):
            return shutil.which(candidato)
    return None


def trova_node_modules(esplicito: str | None) -> Path | None:
    candidati = []
    if esplicito:
        candidati.append(Path(esplicito))
    if env := os.environ.get("ATLAS_SHOT_NODE_MODULES"):
        candidati.append(Path(env))
    candidati.append(Path(__file__).parent)   # tests/node_modules, se qualcuno lo installa li'
    for c in candidati:
        if (c / "node_modules" / "playwright-core").is_dir():
            return c.resolve()
    return None


def render_reale(slug: str) -> str:
    """Sola lettura: legge il graph.json vero e costruisce l'HTML in memoria,
    senza mai scrivere dashboard.html del progetto (che un altro agente puo'
    rigenerare mentre lavoriamo: due nodi ci hanno gia' perso tempo)."""
    ws = Workspace(root=ROOT / ".atlas")
    ref = ws.graph(slug)
    data = json.loads(ref.json_path.read_text(encoding="utf-8"))
    return dash.build(ref, data)


def render_sintetico_ciclo() -> tuple[str, str | None]:
    """Fixture sintetica per l'arco di ritorno: nessuno dei sei grafi reali ne
    contiene uno, e non e' un caso raro da colmare. Un ciclo e' un difetto che
    editor.validate rifiuta di scrivere (mutate.link dentro 'editing' solleva
    in chiusura), e che 'atlas render' rifiuta di assemblare PER INTERO: il
    pannello 'convergenza' (render_panels._blocco_caution -> topology.
    convergence -> topology.levels) solleva SEMPRE su un ciclo, per progetto
    (vedi il docstring di levels: "e' anche la sola convalida strutturale che
    serve a ogni comando"). Quindi oggi non esiste un graph.json, reale o
    costruito ad arte, da cui 'atlas render' produca un dashboard.html con un
    arco di ritorno: il codice che lo disegnerebbe (render_svg/render_edges/
    edge_geometry, portato da Nodavia) non e' mai raggiungibile dal punto
    d'ingresso normale.

    Qui si aggira quel muro SOLO per fotografare la geometria: si costruisce
    il grafo SENZA ciclo con l'API vera (mutate/editing, cosi' lo schema e'
    quello giusto e passa la validazione), lo si rilegge da disco, e SOLO
    ALLORA si patcha a mano il campo blockedBy per introdurre il ciclo,
    bypassando deliberatamente editor.validate (che altrove nel progetto non
    si aggira mai: qui e' un dato del tutto sintetico, non un file del
    progetto). La pagina si riassembla a mano, non con dash.build(), per poter
    isolare il solo pezzo che crasha (il pannello) da tutto il resto, che
    invece funziona: canvas, tabella, notifiche, scheda, script.
    """
    tmp = Path(tempfile.mkdtemp(prefix="atlas-shot-ciclo-"))
    ws = Workspace(root=tmp / ".atlas")
    ref = mutate.create_graph(
        ws, "ciclo-di-prova", "Ciclo di prova (fixture sintetica)",
        "Non e' un grafo del progetto: serve solo a V03 per mostrare come il "
        "canvas disegna un arco di ritorno, dato che nessuno dei sei grafi reali ne ha uno.")
    with editing(ref) as g:
        mutate.add_node(g, id="AVVIO", branch="A", title="Avvio", question="q")
        mutate.add_node(g, id="X", branch="A", title="X", question="q", blockedBy=["AVVIO"])
        mutate.add_node(g, id="Y", branch="A", title="Y", question="q", blockedBy=["X"])
        mutate.add_node(g, id="Z", branch="A", title="Z", question="q", blockedBy=["Y"])
        mutate.add_node(g, id="W", branch="A", title="W", question="q", blockedBy=["Z"])
    data = json.loads(ref.json_path.read_text(encoding="utf-8"))
    for nodo in data["nodes"]:
        if nodo["id"] == "X":
            nodo["blockedBy"].append("Z")   # il ciclo: X <- Y <- Z <- X (stessa forma di test_layout_rank.Ciclo)

    front, presi = frontier(data), claimed(data)
    front_ids = {n["id"] for n in front}
    gruppi = owners_indice(data)
    messaggio_ciclo = None
    try:
        aside = render_panels.panels(ref, data, front, presi, gruppi, remoto=None, remoto_errore=False)
    except StateError as exc:
        messaggio_ciclo = str(exc)
        aside = f'<p class="errore-ciclo">{_esc(messaggio_ciclo)}</p>'

    css, js = leggi_css_dashboard(), leggi_js_dashboard()
    html = (
        f'<!doctype html><html lang="{current()}"><head><meta charset="utf-8">'
        f'<title>ciclo di prova · atlas</title><style>{css}</style></head>'
        f'<body data-slug="ciclo-di-prova">'
        f'{dash._topbar(ref, data, front, presi)}'
        f'<aside class="side">{aside}</aside>'
        f'{dash._mappa(data, front_ids, gruppi)}'
        f'{render_notifiche.panel(ref, data)}'
        f'{render_table.table(data, front_ids)}'
        f'{render_sheet.sheet()}{render_sheet.data_island(ref, data, front_ids)}'
        f'<script>{js}</script></body></html>'
    )
    return html, messaggio_ciclo


def _scrivi(tmp_dir: Path, nome: str, html: str) -> Path:
    path = tmp_dir / nome
    path.write_text(html, encoding="utf-8")
    return path


def costruisci_jobs(tmp_dir: Path, out_dir: Path) -> list[dict]:
    primario = _scrivi(tmp_dir, "primario.html", render_reale(PRIMARIO))
    ciclo_html, messaggio_ciclo = render_sintetico_ciclo()
    ciclo = _scrivi(tmp_dir, "ciclo.html", ciclo_html)
    if messaggio_ciclo:
        (out_dir / "messaggio-ciclo.txt").write_text(
            "atlas render su un grafo con un ciclo si ferma con questa diagnosi "
            "(render_panels.panels -> topology.convergence -> topology.levels), "
            "mai un traceback:\n\n" + messaggio_ciclo + "\n", encoding="utf-8")

    sel_nodo = f'a[data-node="{NODO_PRIMARIO}"]'
    # chrome.js anima ogni '[data-count]' (l'anello di avanzamento, i tre readout
    # della topbar) per 1100ms da 0 al valore finale (count-up, legge 3 di
    # Grafite): uno screenshot preso prima che finisca mostra un numero di
    # passaggio, non quello vero. ASSESTA e' il margine di sicurezza sopra
    # quel tempo, da rispettare PRIMA di ogni screenshot che inquadra la
    # topbar o l'anello (trovato proprio scrivendo questo strumento: le prime
    # prove leggevano 67% e poi 47% sulla STESSA pagina, mai il 76% vero).
    ASSESTA = 1300
    jobs = [
        {"name": "01-apertura-rinquadrata", "html": primario.as_uri(), "reducedMotion": False, "steps": [
            {"op": "waitForSelector", "sel": ".map .n"},
            {"op": "waitForTimeout", "ms": ASSESTA},
            {"op": "screenshot", "out": str(out_dir / "01-apertura-rinquadrata.png")},
        ]},
        {"name": "02-hover-su-nodo", "html": primario.as_uri(), "reducedMotion": False, "steps": [
            {"op": "waitForSelector", "sel": ".map .n"},
            {"op": "waitForTimeout", "ms": ASSESTA},
            {"op": "hover", "sel": sel_nodo},
            {"op": "waitForTimeout", "ms": 150},
            {"op": "screenshot", "out": str(out_dir / "02-hover-su-nodo.png")},
        ]},
        {"name": "03-selezione-pulse-animato", "html": primario.as_uri(), "reducedMotion": False, "steps": [
            {"op": "waitForSelector", "sel": ".map .n"},
            {"op": "waitForTimeout", "ms": ASSESTA},
            {"op": "focus", "sel": sel_nodo},   # focus da tastiera: aggiunge .sel SENZA aprire la scheda (keyboard.js)
            {"op": "waitForTimeout", "ms": 120},
            {"op": "screenshot", "out": str(out_dir / "03a-selezione-pulse-animato-frame1.png")},
            {"op": "waitForTimeout", "ms": 350},
            {"op": "screenshot", "out": str(out_dir / "03b-selezione-pulse-animato-frame2.png")},
        ]},
        {"name": "04-selezione-pulse-reduced-motion", "html": primario.as_uri(), "reducedMotion": True, "steps": [
            {"op": "waitForSelector", "sel": ".map .n"},
            {"op": "focus", "sel": sel_nodo},
            {"op": "waitForTimeout", "ms": 200},
            {"op": "screenshot", "out": str(out_dir / "04-selezione-pulse-reduced-motion.png")},
        ]},
        {"name": "05-scheda-ticket-aperta", "html": primario.as_uri(), "reducedMotion": False, "steps": [
            {"op": "waitForSelector", "sel": ".map .n"},
            {"op": "waitForTimeout", "ms": ASSESTA},
            {"op": "click", "sel": sel_nodo},   # il clic seleziona E apre la scheda (sheet.js)
            {"op": "waitForTimeout", "ms": 200},
            {"op": "screenshot", "out": str(out_dir / "05-scheda-ticket-aperta.png")},
        ]},
        {"name": "06-vista-tabellare", "html": primario.as_uri(), "reducedMotion": False, "steps": [
            {"op": "waitForSelector", "sel": ".map .n"},
            {"op": "waitForTimeout", "ms": ASSESTA},
            {"op": "click", "sel": ".viewmode"},
            {"op": "waitForTimeout", "ms": 150},
            {"op": "screenshot", "out": str(out_dir / "06-vista-tabellare.png")},
        ]},
        {"name": "07-minimap-crop", "html": primario.as_uri(), "reducedMotion": False, "steps": [
            {"op": "waitForSelector", "sel": ".minimap"},
            {"op": "waitForTimeout", "ms": 300},
            {"op": "screenshotEl", "sel": ".minimap", "out": str(out_dir / "07-minimap-crop.png")},
        ]},
        {"name": "08-controls-crop", "html": primario.as_uri(), "reducedMotion": False, "steps": [
            {"op": "waitForSelector", "sel": ".controls"},
            {"op": "screenshotEl", "sel": ".controls", "out": str(out_dir / "08-controls-crop.png")},
        ]},
        {"name": "09-arco-di-ritorno-a-riposo", "html": ciclo.as_uri(), "reducedMotion": False, "steps": [
            {"op": "waitForSelector", "sel": ".map .n"},
            {"op": "waitForTimeout", "ms": ASSESTA},
            {"op": "screenshot", "out": str(out_dir / "09-arco-di-ritorno-a-riposo.png")},
        ]},
        {"name": "10-arco-di-ritorno-selezionato", "html": ciclo.as_uri(), "reducedMotion": False, "steps": [
            {"op": "waitForSelector", "sel": ".map .n"},
            {"op": "waitForTimeout", "ms": ASSESTA},
            {"op": "focus", "sel": 'a[data-node="X"]'},   # X e' bloccato sia da AVVIO (arco sano) sia da Z (il ritorno)
            {"op": "waitForTimeout", "ms": 120},
            {"op": "screenshot", "out": str(out_dir / "10a-arco-di-ritorno-selezionato-frame1.png")},
            {"op": "waitForTimeout", "ms": 350},
            {"op": "screenshot", "out": str(out_dir / "10b-arco-di-ritorno-selezionato-frame2.png")},
        ]},
    ]
    for slug in GRAFI_REALI:
        if slug == PRIMARIO:
            continue
        html_path = _scrivi(tmp_dir, f"{slug}.html", render_reale(slug))
        jobs.append({
            "name": f"apertura-{slug}", "html": html_path.as_uri(), "reducedMotion": False, "steps": [
                {"op": "waitForSelector", "sel": ".map .n"},
                {"op": "waitForTimeout", "ms": ASSESTA},
                {"op": "screenshot", "out": str(out_dir / f"11-apertura-{slug}.png")},
            ],
        })
    return jobs


_DRIVER_JS = r"""
import { chromium } from "playwright-core";
import { readFileSync } from "node:fs";

const manifest = JSON.parse(readFileSync(process.argv[2], "utf-8"));

async function esegui(page, step) {
  switch (step.op) {
    case "waitForSelector": await page.waitForSelector(step.sel, { timeout: step.timeout || 15000 }); return;
    case "waitForTimeout": await page.waitForTimeout(step.ms); return;
    case "focus": await page.locator(step.sel).first().focus(); return;
    case "click": await page.locator(step.sel).first().click(); return;
    case "hover": await page.locator(step.sel).first().hover(); return;
    case "press": await page.keyboard.press(step.key); return;
    case "screenshot": await page.screenshot({ path: step.out }); return;
    case "screenshotEl": await page.locator(step.sel).first().screenshot({ path: step.out }); return;
    default: throw new Error("step sconosciuto: " + step.op);
  }
}

async function main() {
  const browser = await chromium.launch({ executablePath: manifest.chrome, headless: true });
  let ok = 0, tot = 0;
  for (const job of manifest.jobs) {
    tot++;
    try {
      const context = await browser.newContext({
        viewport: manifest.viewport,
        reducedMotion: job.reducedMotion ? "reduce" : "no-preference",
      });
      const page = await context.newPage();
      await page.goto(job.html);
      for (const step of job.steps) await esegui(page, step);
      await context.close();
      ok++;
      console.log("OK   " + job.name);
    } catch (e) {
      console.log("FAIL " + job.name + ": " + e.message);
    }
  }
  await browser.close();
  console.log("--- " + ok + "/" + tot + " job riusciti ---");
  process.exit(ok === tot ? 0 : 1);
}

main();
"""


def esegui_driver(node_modules_dir: Path, manifest_path: Path) -> int:
    """Il driver .mjs si scrive DENTRO node_modules_dir (non in tests/): la
    risoluzione ESM di un bare specifier ('playwright-core') risale dalla
    cartella del file che importa verso i suoi node_modules, non parte dalla
    cwd. Scrivere il driver altrove (per esempio in tests/) non troverebbe mai
    un node_modules nello scratchpad di un'altra sessione."""
    driver_path = node_modules_dir / ".atlas-screenshot-driver.mjs"
    driver_path.write_text(_DRIVER_JS, encoding="utf-8")
    try:
        esito = subprocess.run(["node", str(driver_path), str(manifest_path)],
                               cwd=str(node_modules_dir))
        return esito.returncode
    finally:
        driver_path.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--node-modules", help="cartella che contiene node_modules/playwright-core")
    ap.add_argument("--chrome", help="path del browser da pilotare (default: il primo trovato)")
    ap.add_argument("--out", default=str(ROOT / ".atlas/graphs/260906-grafite-dashboard/notes/atlas"),
                    help="cartella di destinazione delle foto")
    args = ap.parse_args()

    if not shutil.which("node"):
        print("Node.js non trovato sul PATH: playwright-core e' un pacchetto npm, serve un "
              "runtime Node per eseguirlo. Installa Node (nodejs.org) o passa un ambiente che "
              "lo abbia gia'.")
        return 2

    node_modules_dir = trova_node_modules(args.node_modules)
    if node_modules_dir is None:
        print("playwright-core non trovato. Questo strumento dipende da un pacchetto npm "
              "(playwright-core, licenza MIT) che NON e' nel repo: payload/ e atlascli/ restano "
              "a dipendenza zero, e qui non versioniamo un node_modules. Procurartelo:\n"
              "  mkdir -p /una/cartella/qualsiasi && cd /una/cartella/qualsiasi\n"
              "  npm install playwright-core\n"
              "poi rilancia con --node-modules /una/cartella/qualsiasi (o esporta "
              "ATLAS_SHOT_NODE_MODULES=/una/cartella/qualsiasi). Senza, niente foto interattive: "
              "questo messaggio e' il degrado atteso, non un guasto.")
        return 2

    browser = args.chrome or trova_browser()
    if browser is None:
        print("Nessun browser installato trovato (Chrome/Chromium/Edge/Firefox): stesso elenco "
              "di payload/core/view_capture.py. Installane uno, o passa --chrome.")
        return 2

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"browser:       {browser}")
    print(f"node_modules:  {node_modules_dir}")
    print(f"destinazione:  {out_dir}")

    with tempfile.TemporaryDirectory(prefix="atlas-shot-") as tmp:
        tmp_dir = Path(tmp)
        jobs = costruisci_jobs(tmp_dir, out_dir)
        manifest = {"chrome": browser, "viewport": VIEWPORT, "jobs": jobs}
        manifest_path = tmp_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        codice = esegui_driver(node_modules_dir, manifest_path)

    return codice


if __name__ == "__main__":
    raise SystemExit(main())
