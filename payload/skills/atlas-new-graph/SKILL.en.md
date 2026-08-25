---
name: atlas-new-graph
description: Builds a new Atlas task graph, starting from a text the user already has or tracing it from scratch with the method in `atlas-wayfinder`. Use it when the user wants to plan an epic, turn a document into tasks, or says they want to create a graph.
---

# Building a graph

The result is never a hand-written JSON: it's a **mutation script** in `.atlas/scripts/`, which reads as a diff and re-runs. This skill goes from nothing to that script.

## Step 0 — where to start

Ask the user, with AskUserQuestion, one single thing:

- **Do they already have a text?** A document, a task list, meeting notes, an issue, a roadmap. In that case the work is translation, and you move to Branch A.
- **Or is there just an idea?** Then the map needs to be traced, and you move to Branch B.

Also ask for the graph's **technical name** (kebab-case, e.g. `epic-auth`) and its **title**, if not already given: `atlas new` prefixes it with the creation date on its own (`YYMMDD-epic-auth`), so the name alone is enough, no date needed. If the project already has graphs, show them with `atlas graphs`: maybe the work belongs to one of those.

## Branch A — there's a text

1. Read all of it before proposing anything.
2. **Name the destination**: one or two lines saying where this lands once the graph is done. If it can't be drawn from the text, ask for it. Without a destination you can't decide what's out of scope.
3. Identify the **branches**: 3-6 strands of work, each with a letter and a color. Branches exist to read the graph, not to organize execution.
4. Derive the **nodes**. Each is sized for a single work session. A node that holds three independent decisions should be split; three nodes that all close with the same sentence should be merged.
5. Wire the **dependencies**: a `blockedBy` edge exists when the second node isn't even formulable until the first has answered. A plain "comes later in time" is not a dependency. Make the **graph converge into a single final node**, usually a gate that verifies the destination: a terminal that doesn't flow into it is a strand whose outcome no one will collect, and `atlas doctor` flags it.
6. **Show the structure to the user before writing anything** — id, title, type, mode, blocker — and ask for confirmation. This is where things get corrected, not after.

## Branch B — there's just an idea

The method lives in `atlas-wayfinder`, which says how a destination gets named, how fog is told apart from a node, and what stays out of scope. Here is the procedure:

1. **Name the destination** with `atlas-strategic-grilling` and `atlas-domain-modeling`, one question at a time.
2. **Map the frontier** by grilling again, but breadth-first: fan out across the whole problem space instead of going deep on a single thread. This is what surfaces the fog, meaning what you don't know yet.
3. If no fog comes up from the grilling, **stop and tell the user**: if the work is already clear, a graph is an unnecessary ceremony.
4. Turn into nodes only what you can already formulate precisely. The test is whether you can state the question now, not whether you already know the answer. Everything else goes into the fog with `mutate.fog_add`, and it becomes a node once some answer has made it specifiable.
5. Tracing the map is a single session's work. **Don't also resolve nodes** in that same session.

## Type and mode of each node

| Type | When | Typical mode |
|---|---|---|
| `grilling` | working out a decision by talking | HITL |
| `research` | reading documentation, APIs, sources | AFK |
| `prototype` | building a rough artifact to react to | HITL |
| `task` | manual work that has to happen for a decision to become possible | HITL or AFK |

The **mode** is the most important question you ask of every node: can the agent write the answer alone (AFK), or does it need to be built with the human (HITL)? When in doubt, it's HITL. A node that decides something irreversible is always HITL.

## Writing the script

```sh
atlas new <slug> -t "Graph title" -d "The destination, in one or two lines."
atlas new-script first-draft
```

Then fill in the generated script under `.atlas/scripts/`:

```python
from core import mutate

def run(g):
    mutate.add_branch(g, "F", "Foundations", "#4f46e5")
    mutate.add_branch(g, "X", "Deployment", "#0f766e")

    mutate.add_node(g, id="F01", branch="F", type="grilling", mode="HITL",
                    title="Operating contract",
                    question="What contract does the agent work this repo under? The ticket's long text goes here.")
    mutate.add_node(g, id="X01", branch="X", type="task", mode="AFK",
                    title="Build pipeline",
                    question="What does the pipeline produce, and how do you verify the artifact is good?",
                    blockedBy=["F01"])

    mutate.note_add(g, "Domain language decisions get written down in CONTEXT.md.")
    mutate.fog_add(g, "how updates get distributed outside the store")
```

Creation order doesn't matter: validation happens at the end of the transaction, so you can name a node in `blockedBy` that you create further down. What matters is that every edge resolves by the end and that there are no cycles.

A fog entry (`atlas fog --list` rereads all of them) that matures into a node gets promoted in the same kind of script, adding the node and dropping the entry with `fog_drop`, which matches on a substring:

```python
def run(g):
    mutate.add_node(g, id="F04", branch="F", type="task", mode="AFK",
                    title="How updates get distributed",
                    question="...", blockedBy=["F01"])
    mutate.fog_drop(g, "updates get distributed")
```

Then:

```sh
atlas exec .atlas/scripts/001-first-draft.py
atlas render --open
```

`exec` writes the missing tickets, regenerates the map and the dashboard, and prints the frontier. Look at it together with the user: a graph with twenty nodes all up for grabs has no real dependencies, one with only a single node up for grabs is a list disguised as a graph, and several terminal nodes are strands that don't flow into the final one.

## Each node's question

The `question` field becomes the ticket's body, so write it out in full: a paragraph saying what needs to be decided or done, and what counts as an answer. A short title plus a long question reads well; a question that just repeats the title helps no one.
