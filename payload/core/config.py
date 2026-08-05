"""Dove sta l'harness, com'e' configurato, e su quale grafo stiamo lavorando.

Tutte le costanti di path del progetto ospite muoiono qui: il resto del motore
riceve un Workspace o un Graph e non sa piu' nulla di dove siano le cartelle.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .strings import t

DIRNAME = ".atlas"
ENV_GRAPH = "ATLAS_GRAPH"
ENV_ROOT = "ATLAS_ROOT"
ENV_IDENTITY = "ATLAS_IDENTITY"

DEFAULTS = {
    "project": "progetto",
    "language": "it",
    "agent": {"process_name": "claude", "default_assignee": "claude",
              "idle_hours": 4, "max_claims_per_session": 1},
    "git": {"commit_on_close": False, "commit_type": "feat", "stage": "node-paths"},
    "vocab": {"types": ["grilling", "research", "prototype", "task"],
              "modes": ["HITL", "AFK"],
              "statuses": ["open", "claimed", "closed", "out-of-scope"]},
}


class ConfigError(Exception):
    """L'harness non e' installato qui, o il grafo chiesto non esiste."""


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for key, value in over.items():
        out[key] = _merge(base[key], value) if isinstance(value, dict) and isinstance(base.get(key), dict) else value
    return out


def find_root(start: Path | None = None) -> Path:
    """Risale dalla cartella corrente fino alla prima che contiene .atlas/."""
    if env := os.environ.get(ENV_ROOT):
        return Path(env).resolve()
    here = (start or Path.cwd()).resolve()
    for folder in (here, *here.parents):
        if (folder / DIRNAME / "core").is_dir():
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
    def templates_dir(self) -> Path:
        return self.root / "templates"

    @property
    def current_file(self) -> Path:
        return self.root / "current"

    @property
    def config(self) -> dict:
        path = self.root / "config.json"
        stored = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        return _merge(DEFAULTS, stored)

    def template(self, name: str) -> str:
        """Inserisce la lingua dopo il primo punto: 'map.md' -> 'map.it.md',
        'migration.py.tmpl' -> 'migration.it.py.tmpl' (estensione composta:
        va dopo il nome base, non prima dell'ultima estensione)."""
        lingua = self.config.get("language", "it")
        base, sep, resto = name.partition(".")
        nome_lingua = f"{base}.{lingua}.{resto}" if sep else f"{base}.{lingua}"
        return (self.templates_dir / nome_lingua).read_text(encoding="utf-8")

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
