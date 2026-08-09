# This folder is an Atlas work graph

There's no code in here: there's the data of this project's work, broken into nodes connected by dependencies. Tickets, map and dashboards are regenerated from `graphs/*/graph.json`.

```
graphs/     the graphs: nodes, tickets, map, dashboard
scripts/    the scripts that change the graph's shape
skills/     the skills for the agent
config.json what the project is called, and which language it writes in
CONTRACT.md how work is done here: read it before touching anything
```

## You need the program to open it

The engine doesn't live in this folder. It's a single executable, installed once per machine.

```sh
curl -fsSL https://raw.githubusercontent.com/strawberry-code/atlas/main/install.sh | sh
```

On Windows, in PowerShell:

```powershell
irm https://raw.githubusercontent.com/strawberry-code/atlas/main/install.ps1 | iex
```

Python 3.10 or later is all it needs: no venv, no dependencies.

## Then

```sh
atlas how-to     # the full briefing: contract, commands, mutations, paths
atlas status     # where the work stands, and what can be picked up now
```

If `atlas` isn't found after installing, add `~/.local/bin` to your `PATH`.

The project lives at [github.com/strawberry-code/atlas](https://github.com/strawberry-code/atlas).
