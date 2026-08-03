## Atlas: the graph runs the work

The work in this project is a graph of tasks in `.atlas/`. A node is a piece of work sized for one session, the `blockedBy` edges are the dependencies, and the **frontier** is the set of open nodes whose blockers are all closed. You don't pick what to do from a list: you look at the frontier.

```sh
.atlas/bin/atlas status              # frontier, locks, progress
.atlas/bin/atlas claim <ID>          # claim it, before touching anything
.atlas/bin/atlas close <ID> -s "..."  # closes it, after writing the Answer in the ticket
.atlas/bin/atlas fog "a line"        # notes down what came up and has no node yet
```

### One node per session

A claim is a lock, not a reminder: it carries the session's PID, and `claim` refuses if this session already holds one. To work on several nodes in parallel, open several sessions, one per node. The refusal is overridden with `--force`, which exists for the unexpected, not for being in a hurry.

A lock is orphaned when the process that took it no longer exists. `status` flags it, and it must be released or reconfirmed before claiming anything else.

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
.atlas/bin/atlas new-script adds-deploy-branch
.atlas/bin/atlas exec .atlas/scripts/003-adds-deploy-branch.py
```

The script runs inside a single transaction and the graph is validated before being written, so a cycle or an edge to a nonexistent node makes it fail without touching the file. Scripts stay version-controlled: they're the history of changes to the map.

Something you discover while working a node that would deserve a node of its own gets **proposed**, not created: in the meantime, note it with `atlas fog`.

### When a node is done

| Type | Done when |
|---|---|
| `grilling` | the decision is written and the artifact it produces exists |
| `research` | the answer cites sources read just now, with link and date, not remembered |
| `prototype` | the artifact can be looked at, and the ticket says what was learned and what was discarded |
| `task` | the work is done and verified, with the proof described in the ticket |

`close` checks exactly one thing: that the ticket's **Answer** section is filled in. Everything else is declared by whoever closes it. No machine can verify that the answer is also true, and the only defense is that whoever did the work writes it while it's still fresh.

### Multiple graphs

One graph per epic, each isolated in `.atlas/graphs/<slug>/` with its own map and its own dashboard. The switch is up to whoever's working: `atlas use <slug>`, or `--graph <slug>` on the single command.
