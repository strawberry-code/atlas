## Atlas: the graph runs the work

The work in this project is a graph of tasks in `.atlas/`. A node is a piece of work sized for one session, the `blockedBy` edges are the dependencies, and the **frontier** is the set of open nodes whose blockers are all closed. You don't pick what to do from a list: you look at the frontier.

```sh
atlas how-to                   # this contract, the commands, the mutations, the skills and the paths
atlas status                   # frontier, locks, progress
atlas next                     # the frontier ranked by impact: a suggestion
atlas take <ID>                # claims it and prints its context in one step, before touching anything
atlas close <ID> -s "..."      # closes it, after writing the Answer in the ticket
atlas fog "a line" --for <ID>  # notes down what came up, addressed to a node if it concerns one
```

`atlas brief <ID>` prints the same context package as `take` (question, blockers' answers, fog that names it) without claiming: useful to reread it without touching the lock.

If you get here knowing nothing about Atlas, `atlas how-to` is the way in: it prints this contract, the list of commands, the mutations a script can call, the installed skills and this project's paths. Same doctrine you're reading now, reachable from a command instead of a file.

### One node per session

A claim is a lock, not a reminder: it carries the claiming identity (the process PID, or `ATLAS_IDENTITY` if set) and a heartbeat that renews by re-claiming the same node. `claim`/`take` refuse if this identity already holds one. To work on several nodes in parallel with subagents that share the same parent process, each one sets a different identity using the `--identity` flag on the commands that take the lock (`claim`, `take`, `release`, `close`), or the `ATLAS_IDENTITY` environment variable: otherwise the per-session cap counts them as a single actor. The flag takes precedence over the environment variable, and it is what an agent needs when every command starts in a fresh shell: there an `export` never reaches the next call, and the lock falls back to the parent PID, which is the very identity its siblings share. The refusal is overridden with `--force`, which exists for the unexpected, not for being in a hurry.

A lock is orphaned when the process that took it no longer exists, or stalled when its heartbeat hasn't updated in too long. `atlas doctor` flags both cases, along with terminal nodes that don't flow into the final one and dashboards that are out of date: run it before declaring a graph done.

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
atlas new-script adds-deploy-branch
atlas exec .atlas/scripts/003-adds-deploy-branch.py
```

The script runs inside a single transaction and the graph is validated before being written, so a cycle or an edge to a nonexistent node makes it fail without touching the file. Scripts stay version-controlled: they're the history of changes to the map.

When the graph is shared and the histories diverge, the base is the one already published: your work gets re-applied on top with scripts renumbered to the end, never by merging `graph.json` by hand, because a manual merge would detach the map from the sequence of scripts that produced it. `atlas renumber` puts the scripts back in order, closing the gaps in the numbering without arguments or moving the files you pass to the end, in the order given; `--dry-run` shows the renames without doing them. Closures that already happened on another copy are brought back with `mutate.restore_closure`, which recreates them with their original metadata. It is not a way to close a node: that stays `atlas close`, which checks the lock and the Answer written in the ticket. It serves instead to re-apply your work on top of a graph that came from others. The full cycle, pull, compare, merge, renumber, re-run and push, is described at length in the `atlas-sync` skill.

A node's ticket is not a second copy of the graph. Its head (title, branch, type, mode, blockers, question) descends from `graph.json` and is rewritten on every regeneration, while Work and Answer belong to whoever writes them. The boundary between the two is the `<!-- /atlas:auto -->` comment. So a script that changes a title, a question or a dependency leaves no stale markdown behind and there's nothing to fix by hand; if that comment disappears, the ticket stops realigning and `atlas doctor` flags it.

Something you discover while working a node that would deserve a node of its own gets **proposed**, not created: in the meantime, note it with `atlas fog`. To turn one into a node there's a ready example at `.atlas/scripts/000-promote-fog.py`: fill in the entry's index and the node's fields, then run it with `atlas exec`.

### When a node is done

| Type | Done when |
|---|---|
| `grilling` | the decision is written and the artifact it produces exists |
| `research` | the answer cites sources read just now, with link and date, not remembered |
| `prototype` | the artifact can be looked at, and the ticket says what was learned and what was discarded |
| `task` | the work is done and verified, with the proof described in the ticket |

That table says when a node is finished, not how it gets worked. The *how* lives in the skills installed in the project, one per type. A `grilling` node has two, because there are two ways to grill: `atlas-strategic-grilling` when the decision is structural or irreversible, with no budget, until the design tree has been walked; `atlas-tactical-grilling` when the scope is narrow, in three phases, the agent's reconnaissance on the code, then a declared number of questions to the user, then a synthesis to confirm. A `research` node goes through `atlas-research`, a `prototype` one through `atlas-prototype`, and the domain language through `atlas-domain-modeling`. The method behind the whole graph, destination, fog and scope, lives in `atlas-wayfinder`. `atlas how-to` lists the skills present here.

`close` checks exactly one thing: that the ticket's **Answer** section is filled in. Everything else is declared by whoever closes it. No machine can verify that the answer is also true, and the only defense is that whoever did the work writes it while it's still fresh.

There is one refusal that doesn't depend on what you wrote: the node changed since you claimed it. Atlas records a fingerprint of the node's content when you take it and checks it again when you close, because all the work happens between those two moments, and in that time another agent or a mutation script may have changed the question, the dependencies or the scope you were reasoning about. Your answer would land cleanly and rest on a premise that no longer holds, with nobody noticing. When it happens, re-read the node with `atlas show <ID>` and decide: close again if your answer still stands, or update it. `--force` closes anyway, and is meant for when the change doesn't affect what you wrote.

Under Answer there are three light, optional sub-sections: **non-canonical choices** (what you decided on your own, not dictated by the design doc), **declared debt** (what you're deliberately leaving incomplete, and why), and **authorizations received** (if you acted beyond the node's scope on the user's explicit direction, what and when). A verification gate reads them without having to reconstruct the same archaeology from free prose, and the third one makes a "per your request" verifiable instead of merely asserted.

`close` also accepts `-c/--costo` (a rough order of magnitude for what it cost, free text, nothing precise) and `--artefatti` (the files produced, filling in the field the graph already has). Without `--artefatti`, inside a git repository the field fills itself with the files touched since the node was claimed, `.atlas/` ones excluded. Deduction skips, leaving the field empty for you to declare with explicit `--artefatti`, in two cases: if more than one node is claimed at close time, and if another node of the graph was closed or released while this one was in progress, because over that window the two pieces of work overlap and git cannot tell whose each file is. When it does deduce, `close` prints the list of deduced files: look at it, because that is the only moment you notice without going to look. That field is what lets `doctor` spot a write inside the scope of an already closed node; to leave it deliberately empty, pass `--artefatti` with no arguments.

If that list holds something that isn't yours, or the cost and the summary came out wrong, the fix is `atlas amend <ID> [--artefatti ...] [--costo ...] [--sintesi ...]`. It rewrites only the fields you pass and leaves everything else alone: the node stays closed, and the closing instant does not move, because that is what `doctor` measures later writes from. The correction stays recorded in the node with who made it and when, so whoever reads it knows that field was set by hand and not deduced. A node still open can't be amended: there the bookkeeping is written by `close`. If a gate releases a node instead of closing it, `-r/--ragione` on `release` records why as an event in the map, not just a silent return to the frontier.

### Who does what, if it helps

A node can be assigned to one or more people with `atlas assign <names> <ID...>`, where a comma separates the names; `atlas assign cristiano,pedro F01` leaves it to both. Without `--add` and without `--remove` the command replaces the node's whole list, which is the old behavior extended to several names; `atlas assign lucia F02` leaves it to her alone, whatever the previous assignment was. The comma separates people and a name can't hold one, nor a `+`: the command rejects it and points to the comma as the fix. A graph written in the old form, even with joined names like `cristiano+pedro`, keeps being readable, and the first mutation brings it back in line on its own.

`--branch <branch>` takes the nodes that branch has at that moment, and one added later is born unassigned. Assigning a branch overwrites the nodes that already belonged to someone else, and the command prints the ids it changed. `--add <name>` adds a person to the ones the node already has, `--remove <name>` takes away just one and leaves the others, and `--me` assigns to you without retyping the name, because `atlas whoami <name>` remembers who works from this copy of the project. The `.atlas/whoami` file is not versioned. `atlas unassign <ID...>` brings the node back to nobody.

An assignment is not the lock and does not replace it: it says whose piece of work this is, while the `claim` says who has their hands on it right now. An assigned node stays up for grabs, and assigning it while someone is working on it doesn't stop them from closing it. If you don't use them, the graph behaves exactly as before: no node is born assigned and the dashboard shows nothing extra.

### Multiple graphs

One graph per epic, each isolated in `.atlas/graphs/<slug>/` with its own map and its own dashboard. `atlas new <name>` prefixes the creation date to the technical name you give it on its own (`<name>` becomes `YYMMDD-<name>`): the real slug is that one, not the one passed on the command line. The switch is up to whoever's working: `atlas use <slug>`, or `-g/--graph <slug>` on the single command, which works both before and after the command itself. The slug does not go where the command goes: `atlas <slug> render` doesn't exist.
