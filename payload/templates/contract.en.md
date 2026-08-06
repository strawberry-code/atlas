## Atlas: the graph runs the work

The work in this project is a graph of tasks in `.atlas/`. A node is a piece of work sized for one session, the `blockedBy` edges are the dependencies, and the **frontier** is the set of open nodes whose blockers are all closed. You don't pick what to do from a list: you look at the frontier.

```sh
python3 .atlas/bin/atlas how-to              # this contract, the commands, the mutations, the skills and the paths
python3 .atlas/bin/atlas status              # frontier, locks, progress
python3 .atlas/bin/atlas next                 # the frontier ranked by impact: a suggestion
python3 .atlas/bin/atlas take <ID>            # claims it and prints its context in one step, before touching anything
python3 .atlas/bin/atlas close <ID> -s "..."  # closes it, after writing the Answer in the ticket
python3 .atlas/bin/atlas fog "a line" --for <ID>   # notes down what came up, addressed to a node if it concerns one
```

`atlas brief <ID>` prints the same context package as `take` (question, blockers' answers, fog that names it) without claiming: useful to reread it without touching the lock.

If you get here knowing nothing about Atlas, `atlas how-to` is the way in: it prints this contract, the list of commands, the mutations a script can call, the installed skills and this project's paths. Same doctrine you're reading now, reachable from a command instead of a file.

### One node per session

A claim is a lock, not a reminder: it carries the claiming identity (the process PID, or `ATLAS_IDENTITY` if set) and a heartbeat that renews by re-claiming the same node. `claim`/`take` refuse if this identity already holds one. To work on several nodes in parallel with subagents that share the same parent process, each one sets a different `ATLAS_IDENTITY`: otherwise the per-session cap counts them as a single actor. The refusal is overridden with `--force`, which exists for the unexpected, not for being in a hurry.

A lock is orphaned when the process that took it no longer exists, or stalled when its heartbeat hasn't updated in too long. `atlas doctor` flags both cases, along with nodes nothing requires and dashboards that are out of date: run it before declaring a graph done.

### HITL and AFK

Every node declares who writes its answer.

| Action | Autonomy |
|---|---|
| claim, release, close | yes, it's bookkeeping |
| working and answering an **AFK** node | yes, it's the node's own work |
| answering a **HITL** node | no, it's written together with the human: that's what the acronym means |
| creating nodes, changing `blockedBy`, marking out of scope | never autonomously, and only ever via a script |

An agent that answers a HITL node on its own has broken the most important rule in this contract.

### The graph's shape changes only through code

`graph.json` is never edited by hand, and the CLI has no commands that create nodes or edges. Every structural change is a Python script in `.atlas/scripts/` that goes through `core/mutate.py`:

```sh
python3 .atlas/bin/atlas new-script adds-deploy-branch
python3 .atlas/bin/atlas exec .atlas/scripts/003-adds-deploy-branch.py
```

The script runs inside a single transaction and the graph is validated before being written, so a cycle or an edge to a nonexistent node makes it fail without touching the file. Scripts stay version-controlled: they're the history of changes to the map.

A node's ticket is not a second copy of the graph. Its head (title, branch, type, mode, blockers, question) descends from `graph.json` and is rewritten on every regeneration, while Work and Answer belong to whoever writes them. The boundary between the two is the `<!-- /atlas:auto -->` comment. So a script that changes a title, a question or a dependency leaves no stale markdown behind and there's nothing to fix by hand; if that comment disappears, the ticket stops realigning and `atlas doctor` flags it.

Something you discover while working a node that would deserve a node of its own gets **proposed**, not created: in the meantime, note it with `atlas fog`. To turn one into a node there's a ready example at `.atlas/scripts/000-promote-fog.py`: fill in the entry's index and the node's fields, then run it with `atlas exec`.

### When a node is done

| Type | Done when |
|---|---|
| `grilling` | the decision is written and the artifact it produces exists |
| `research` | the answer cites sources read just now, with link and date, not remembered |
| `prototype` | the artifact can be looked at, and the ticket says what was learned and what was discarded |
| `task` | the work is done and verified, with the proof described in the ticket |

`close` checks exactly one thing: that the ticket's **Answer** section is filled in. Everything else is declared by whoever closes it. No machine can verify that the answer is also true, and the only defense is that whoever did the work writes it while it's still fresh.

Under Answer there are three light, optional sub-sections: **non-canonical choices** (what you decided on your own, not dictated by the design doc), **declared debt** (what you're deliberately leaving incomplete, and why), and **authorizations received** (if you acted beyond the node's scope on the user's explicit direction, what and when). A verification gate reads them without having to reconstruct the same archaeology from free prose, and the third one makes a "per your request" verifiable instead of merely asserted.

`close` also accepts `-c/--costo` (a rough order of magnitude for what it cost, free text, nothing precise) and `--artefatti` (the files produced, filling in the field the graph already has). Without `--artefatti`, inside a git repository the field fills itself with the files touched since the node was claimed, `.atlas/` ones excluded. That field is what lets `doctor` spot a write inside the scope of an already closed node; to leave it deliberately empty, pass `--artefatti` with no arguments. If a gate releases a node instead of closing it, `-r/--ragione` on `release` records why as an event in the map, not just a silent return to the frontier.

### Multiple graphs

One graph per epic, each isolated in `.atlas/graphs/<slug>/` with its own map and its own dashboard. The switch is up to whoever's working: `atlas use <slug>`, or `--graph <slug>` on the single command.
