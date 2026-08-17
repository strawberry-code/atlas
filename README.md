# Atlas

![A nautical chart whose coastline is a dependency graph: wax-sealed nodes on the left are closed, two brass padlocks rest on the lit frontier, and the right side dissolves into fog.](docs/hero.jpg)

*[Versione italiana](README.it.md)*

A graph-based task harness. Tasks are nodes, dependencies are edges, and the **frontier** is whatever can be picked up right now. Every node declares who writes its answer: the human (**HITL**) or the agent on its own (**AFK**).

## What it is, and when it's worth using

Atlas takes a project's work, breaks it into nodes connected by dependencies, and lets it live as a graph instead of a list. Each node is a ticket sized for one session: a feature to build, a question to settle, an exploration that has to happen before a decision is even possible. The frontier is the set of nodes you can pick up right now, the ones whose blockers are already closed: you don't choose by reading a list top to bottom, you look at what's actually available.

Every node also declares who writes its answer. An **AFK** node (away from keyboard) is worked by the agent alone, and its output always lands in a file: the ticket itself or the artifact it produces. An **HITL** node (human in the loop) gets resolved by talking it through: the question is put to the user one at a time, and the answer is written together.

It's worth installing when a piece of work spans more than one session and has real dependencies between its parts. An epic with a dozen connected tasks is the typical case, one graph per epic. If the work fits in a single session, or it's really a list without real dependencies, the graph adds ceremony instead of structure.

## How you work, in practice

Install the CLI, install it in a project (creates `.atlas/`, registers the project, adds the two skills), then the loop stays the same every time:

1. **Create or import a graph**, from a text you already have or by tracing it from scratch with the wayfinder if the idea is still fog. The `atlas-new-graph` skill handles this.
2. **Look at the frontier** with `atlas status`, or `atlas next` to rank it by impact when several nodes are up for grabs.
3. **Take a node** with `atlas take <ID>`, before touching it: claims it and prints its context (question, blockers' answers, fog that names it) in the same step.
4. **Work it**: if the node is AFK, the agent does it alone; if it's HITL, the `atlas-work` skill asks its questions one at a time and waits.
5. **Close it** with `atlas close <ID> -s "summary"`, after writing the Answer section in the ticket. The map and dashboard regenerate on their own.

One way to orchestrate several nodes at once, if the project has many available: a "main" session that watches the frontier and coordinates, AFK nodes delegated to sub-agents that work in parallel and write their results into their own tickets, HITL nodes reserved for a dedicated session. This isn't a feature of the engine, it's just one way of using it: Atlas stays the source of truth on what's done, whoever's coordinating on top is free to organize however they like.

## Installing the CLI

```bash
curl -fsSL https://raw.githubusercontent.com/strawberry-code/atlas/main/install.sh | sh
```

On native Windows (no WSL needed):

```powershell
irm https://raw.githubusercontent.com/strawberry-code/atlas/main/install.ps1 | iex
```

Lands in `~/.local/bin/atlas` (`%USERPROFILE%\.local\bin\atlas` on Windows, override with `ATLAS_INSTALL_DIR`). Needs Python 3.10+: no venv, no dependency beyond the stdlib.

## Installing in a project

```bash
atlas install .                      # or atlas install /path/to/project
atlas install . --graph my-epic      # create the first graph right away
atlas install . --lang en            # content and skills in English instead of Italian
```

Only the project's own data lands in `.atlas/`: `config.json`, the graphs, the mutation scripts, the skills, the contract, and a `README.md` telling whoever finds that folder how to get `atlas`. The engine doesn't go in there: it lives in the executable, one per machine. Outside `.atlas/` you get two symlinks in `.claude/skills/`, the end-of-session hook in `.claude/settings.json`, and the contract in `CLAUDE.md`. The project also gets registered in `~/.config/atlas.json` under a slug (default: the folder name; `--slug` for a different one).

```bash
atlas list                           # registered projects and their state
atlas list my-project                # the card for just one
atlas update                         # updates atlas and realigns the registered projects
atlas update --no-projects           # updates only the executable, projects stay behind
atlas lang en                        # content language of this project
atlas lang --global en               # default for future projects
```

A project's engine never gets updated, because a project has none: it lives in the executable, and the moment `atlas` changes version every project uses the new one. What stays behind are the real files written inside the project, namely the skills, `.atlas/CONTRACT.md`, `.atlas/README.md`, and the delimited block in `CLAUDE.md`, while the project's own `README.md` is never touched. Those are what `atlas update` brings back in line, walking the registry project by project once the executable has been replaced. It does so even when there is nothing to download, in that case only for projects installed by a different version: without it, anyone who upgraded from a version that didn't yet realign would stay behind forever. Anything no longer on disk is skipped and reported; a project that fails on its own account doesn't stop the others. Realigning refreshes what a project has, it doesn't add what it never had: installed without the hook or without the `CLAUDE.md` block, it stays that way. With `--no-projects` only the executable is updated, and projects are brought back in line by hand with `atlas install <path>`.

Switching an existing project's language regenerates `SKILL.md`, `CONTRACT.md`, and every dashboard: a `map.md` already written in the old language is left untouched (its headings no longer match), so that graph stays as it was until you update it by hand, while new tickets follow the current language.

## Working

Graph commands work from inside the project, which `atlas` finds on its own by walking up the folders:

```bash
atlas how-to                         # the whole briefing: contract, commands, mutations, skills, paths
atlas status                         # frontier, locks, progress
atlas next                           # frontier ranked by impact, as a suggestion
atlas take F01                       # claims it and prints its context in one step
# work it, then write the Answer section in .atlas/graphs/<slug>/tickets/F01.md
atlas close F01 -s "one-line summary"
atlas amend F01 --artefatti src/a.py # fixes the bookkeeping of an already closed node
atlas render --open                  # dashboard
atlas doctor                         # health check: dangling nodes, stale locks, stale dashboard
```

One node per session. `close` refuses if the Answer is empty.

## Who does what

Assignments are optional, for when a graph is split across several people. An assigned node stays up for grabs: the lock is still the `claim`, the assignment says whose piece it is, not who has their hands on it right now.

```bash
atlas whoami marco                   # who works from this copy, remembered in .atlas/whoami
atlas assign lucia F02 F03           # assigns nodes to a person
atlas assign lucia --branch B        # and the nodes branch B has now
atlas assign --me F04                # to you, without retyping the name
atlas unassign F02                   # back to no assignee
```

The name is plain text and the list changes whenever it needs to: there is no roster to keep up to date. `.atlas/whoami` is not versioned, because it is whoever has the repo in front of them, not a project fact. The dashboard grows one chip per person plus one for the unassigned: clicking one leaves only their nodes lit, the same way the status filter works.

`atlas how-to` is the single entry point for an agent that lands here cold: it prints the project's contract, the command list, the mutations a script can call, the installed skills, and where every file lives. The contract is the only hand-written part, and everything else is read from the installed code, so it can't drift from the version in use.

## Changing the graph

Never by hand, always with a script:

```bash
atlas new-script adds-deploy-branch
# write the mutations in .atlas/scripts/002-adds-deploy-branch.py
atlas exec .atlas/scripts/002-adds-deploy-branch.py
```

```python
from core import mutate

def run(g):
    mutate.add_branch(g, "X", "Delivery", "#0f766e")
    mutate.add_node(g, id="X01", branch="X", type="task", mode="AFK",
                    title="Build pipeline",
                    question="What does it produce, and how do you verify it's good?",
                    blockedBy=["F03"])
```

It all runs in a single transaction and gets validated before writing: cycles, edges pointing nowhere, and duplicate ids fail the script without touching the file.

Other functions: `edit_node`, `link`, `unlink`, `drop` (out of scope), `remove_node`, `reopen`, `assign`, `unassign`, `fog_add`, `fog_drop`, `note_add`, `set_meta`.

## Multiple graphs

One per epic, isolated.

```bash
atlas new other-epic -t "Title" -d "Where it lands."
atlas graphs
atlas use other-epic       # or -g <slug>, or ATLAS_GRAPH=<slug>
```

## The two skills

`atlas-new-graph` builds a new graph, from a text you already have or by tracing it with the wayfinder. `atlas-work` works a node from the frontier to its close. They invoke themselves when needed.

## License

AGPL-3.0. See `LICENSE`.

## Developing Atlas

```bash
python3 -m unittest discover -s tests   # engine + global CLI (registry, self-update, install.sh)
python3 build.py && python3 tests/e2e.py  # dist/atlas, tried for real
```

`payload/` is the engine that ends up in the host project, and it has to stay pure stdlib, cross-platform (POSIX and Windows), no network. `atlascli/` is the global CLI (install/update/uninstall/list, registry, self-update): pure stdlib there too, but network access to GitHub is allowed since it's a different product. Every change needs `dist/atlas` regenerated with `build.py`. To cut a release: `python3 release.py X.Y.Z` (version bump, build, test, sha256 — the git/GitHub commands stay manual).
