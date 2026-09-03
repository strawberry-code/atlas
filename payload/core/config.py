"""Dove sta l'harness, com'e' configurato, e su quale grafo stiamo lavorando.

Tutte le costanti di path del progetto ospite muoiono qui: il resto del motore
riceve un Workspace o un Graph e non sa piu' nulla di dove siano le cartelle.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .risorse import leggi_template
from .strings import t

DIRNAME = ".atlas"
ENV_GRAPH = "ATLAS_GRAPH"
ENV_ROOT = "ATLAS_ROOT"
ENV_IDENTITY = "ATLAS_IDENTITY"
ENV_HOST = "ATLAS_HOST"

DEFAULTS = {
    "project": "progetto",
    "language": "it",
    "agent": {"process_name": "claude", "default_assignee": "claude",
              "idle_hours": 4, "max_claims_per_session": 1,
              "lease_ttl_seconds": 3600},
    "lock": {"remote": None},
    "notify": {"telegram_enabled": True},
    "drift": {"collector_paths": []},
    "git": {"commit_on_close": False, "commit_type": "feat", "stage": "node-paths"},
    "vocab": {"types": ["grilling", "research", "prototype", "task"],
              "modes": ["HITL", "AFK"],
              "statuses": ["open", "claimed", "closed", "out-of-scope"]},
}


class ConfigError(Exception):
    """L'harness non e' installato qui, il grafo chiesto non esiste, o i suoi dati
    non si leggono. Il CLI la intercetta e la stampa: ogni altra eccezione esce
    come traceback nudo, che a chi legge non dice quale file aprire."""


def leggi_json(path: Path) -> dict:
    """Un JSON del progetto, con l'errore che nomina il file da aprire.

    Senza questa rete una virgola di troppo in config.json esce come JSONDecodeError
    nudo, e siccome la config si legge all'avvio di ogni comando muore anche quello
    che servirebbe a rimettere le cose a posto.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as errore:
        raise ConfigError(t("config.json_rotto", path=path, dettaglio=errore)) from errore


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for key, value in over.items():
        out[key] = _merge(base[key], value) if isinstance(value, dict) and isinstance(base.get(key), dict) else value
    return out


def find_root(start: Path | None = None) -> Path:
    """Risale dalla cartella corrente fino al primo progetto Atlas.

    La firma e' config.json e non .atlas/ da sola, che resta anche dopo un uninstall,
    ne' il motore, che dalla 0.7 non abita piu' dentro il progetto: li' ci sono solo
    dati, e sono i dati a dire che questo e' un progetto.
    """
    if env := os.environ.get(ENV_ROOT):
        return Path(env).resolve()
    here = (start or Path.cwd()).resolve()
    for folder in (here, *here.parents):
        if (folder / DIRNAME / "config.json").is_file():
            return folder / DIRNAME
    raise ConfigError(t("config.root_mancante", dirname=DIRNAME))


@dataclass(frozen=True)
class Graph:
    """Un grafo del progetto: cartella propria, ticket propri, dashboard propria."""
    workspace: "Workspace"
    slug: str

    @property
    def dir(self) -> Path:
        return self.workspace.graphs_dir / self.slug

    @property
    def json_path(self) -> Path:
        return self.dir / "graph.json"

    @property
    def retry_state_path(self) -> Path:
        return self.dir / "retry-state.json"

    @property
    def run_state_path(self) -> Path:
        return self.dir / "run-state.json"

    @property
    def notify_state_path(self) -> Path:
        return self.dir / "notify-state.json"

    @property
    def map_path(self) -> Path:
        return self.dir / "map.md"

    @property
    def tickets_dir(self) -> Path:
        return self.dir / "tickets"

    @property
    def dashboard_path(self) -> Path:
        return self.dir / "dashboard.html"

    def ticket_path(self, node_id: str) -> Path:
        return self.tickets_dir / f"{node_id}.md"

    def exists(self) -> bool:
        return self.json_path.is_file()


@dataclass(frozen=True)
class Workspace:
    root: Path                      # la cartella .atlas/

    @property
    def project_root(self) -> Path:
        return self.root.parent

    @property
    def graphs_dir(self) -> Path:
        return self.root / "graphs"

    @property
    def scripts_dir(self) -> Path:
        return self.root / "scripts"

    @property
    def current_file(self) -> Path:
        return self.root / "current"

    @property
    def whoami_file(self) -> Path:
        """Chi lavora da questa copia del progetto. Sta accanto a 'current' ed e'
        ignorato da git per la stessa ragione: e' stato locale di chi ha il repo
        davanti, non un dato del progetto. Versionarlo farebbe ereditare a chi
        clona il nome dell'ultimo che l'ha scritto."""
        return self.root / "whoami"

    def whoami(self) -> str | None:
        path = self.whoami_file
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8").strip() or None

    @property
    def config(self) -> dict:
        path = self.root / "config.json"
        return _merge(DEFAULTS, leggi_json(path) if path.is_file() else {})

    def template(self, name: str) -> str:
        """Inserisce la lingua dopo il primo punto: 'map.md' -> 'map.it.md',
        'migration.py.tmpl' -> 'migration.it.py.tmpl' (estensione composta:
        va dopo il nome base, non prima dell'ultima estensione)."""
        lingua = self.config.get("language", "it")
        base, sep, resto = name.partition(".")
        nome_lingua = f"{base}.{lingua}.{resto}" if sep else f"{base}.{lingua}"
        return leggi_template(nome_lingua)

    def slugs(self) -> list[str]:
        if not self.graphs_dir.is_dir():
            return []
        return sorted(d.name for d in self.graphs_dir.iterdir() if (d / "graph.json").is_file())

    def graph(self, slug: str | None = None) -> Graph:
        """Grafo attivo: argomento esplicito, poi ambiente, poi 'current', poi l'unico che c'e'."""
        known = self.slugs()
        chosen = slug or os.environ.get(ENV_GRAPH) or self.pinned() or (known[0] if len(known) == 1 else None)
        if not chosen:
            raise ConfigError(t("config.nessun_grafo_attivo",
                                elenco=", ".join(known) or t("config.nessun_grafo")))
        if chosen not in known:
            raise ConfigError(t("config.grafo_inesistente", scelto=chosen,
                                elenco=", ".join(known) or t("config.zero_grafi")))
        return Graph(self, chosen)

    def pinned(self) -> str | None:
        path = self.current_file
        return path.read_text(encoding="utf-8").strip() if path.is_file() else None

    def pin(self, slug: str) -> None:
        self.current_file.write_text(f"{slug}\n", encoding="utf-8")


def workspace(start: Path | None = None) -> Workspace:
    return Workspace(find_root(start))
