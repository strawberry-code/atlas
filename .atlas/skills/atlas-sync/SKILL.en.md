---
name: atlas-sync
description: Brings this project's Atlas graph copy in line with the other agents' copies and publishes your own work on top, even when `graph.json` has gone into conflict. Use it before a push on a shared graph, or when a merge touches the graph.
---

# Aligning a shared graph

The shared graph changes only through mutation scripts. When two agents work the same graph on separate copies, `graph.json` will eventually conflict. Merging it by hand is the worst remedy, because the file stops being the product of a script sequence and no one can reconstruct how it got there. This skill brings your copy in line with whoever published first and re-applies your work on top with scripts, so the history stays linear.

## 1. Close your session before publishing

```sh
atlas status
```

`status` shows the locks: if one of yours is still open, close the node with `atlas close <ID> -s "..."` or let it go with `atlas release <ID>`. The work must be committed before moving on.

## 2. Check whether the graph moved

```sh
git fetch
git log --oneline HEAD..origin/<branch> -- .atlas/
```

If nothing comes out, no one else touched the graph. The push is ordinary and the procedure ends here.

## 3. Note what you did

```sh
BASE=$(git merge-base HEAD origin/<branch>)
git diff $BASE..HEAD -- .atlas/graphs/<slug>/graph.json
```

Three categories come out of that diff, and all three are needed later: your own scripts not yet published, the closures you made, the assignments and the fog you added.

## 4. Merge by taking their graph

```sh
git merge origin/<branch>
git checkout origin/<branch> -- .atlas/graphs/<slug>/graph.json
```

Write the checkout of their file in full, naming the branch, never `--ours` or `--theirs`: the two words swap between merge and rebase, and that's the mistake people make. Whoever published first is the base, and your own work re-applies on top. Only in this direction does the script history stay linear and re-runnable.

The same goes for the other files. `map.md` is taken from the remote without a second thought, because the sections the graph owns, among them Decisions made, regenerate on their own at the first command that touches the graph. Only Destination and Notes remain to merge by hand, if you both wrote them. Tickets are one file per node and rarely conflict.

## 5. Renumber your scripts after theirs

```sh
atlas renumber <your files>
```

It moves them after the others' maximum, in the order you indicate, with `git mv` where it helps.

## 6. Write the alignment script

What wasn't a script re-applies through a new script, never by hand.

```sh
atlas new-script riallinea-<something>
```

Then fill in the generated script:

```python
from core import mutate

def run(g):
    mutate.restore_closure(g, "F02", answer="...", closedBy="...", closedAt="...")
    mutate.assign(g, "anna,marco", ["F05"])
    mutate.fog_add(g, "...")
```

Add one `restore_closure` for every node you closed. The metadata comes from the step 3 diff: those are the real ones, from the closure that happened on your copy, and they get copied, not invented. Then add the assignments with `mutate.assign` and the fog with `mutate.fog_add`.

## 7. Re-run in order

```sh
atlas exec <your scripts, in order>
```

`exec` accepts multiple scripts at once and applies them first to last, stopping at the first one that fails.

## 8. Verify and publish

```sh
atlas doctor
atlas status
```

`doctor` and `status` must pass clean before the commit. The push is a gesture the user asked for, not the last automatic step of the procedure. Ask for it, if it wasn't already said.

## What not to do

- **Don't open `graph.json` in an editor** to merge two versions. The file stops being the product of a script sequence, and no one can reconstruct how it got there.
- **Don't re-run a script already applied** to the graph you took as the base: its nodes are already there, and the run dies saying the id exists.
- **Don't use `restore_closure` to close a real node.** A node closes with `atlas close`.
