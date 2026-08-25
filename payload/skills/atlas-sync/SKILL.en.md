---
name: atlas-sync
description: Brings this project's copy of the Atlas graph in line with the other agents' and publishes your own work, even when `graph.json` has gone into conflict. Use it before pushing to a shared graph, or when a merge touches the graph.
---

# Aligning a shared graph

A shared graph only changes through mutation scripts. When two agents work the same graph on different copies, `graph.json` ends up in a git merge.

**That merge is the driver's job, not yours.** At install time Atlas registers a merge driver (one line in `.gitattributes` and a section in the local git config) that merges `graph.json` by node id instead of by line: two closures on different nodes compose on their own, the file stays valid JSON, and git markers never end up inside it. This skill covers what the driver cannot decide by itself.

## 1. Before publishing, close your session

```sh
atlas status
```

`status` shows the locks: if one of yours is still open, close the node with `atlas close <ID> -s "..."` or drop it with `atlas release <ID>`. Commit the work before going further.

## 2. Merge, and let the driver work

```sh
git fetch
git merge origin/<branch>
```

If the merge comes out clean, the graph is already merged properly and only steps 4 and 5 remain. Don't open `graph.json`, and don't run `git checkout origin/<branch> -- graph.json`: you would throw away the very merge that was just done.

## 3. If git declares a conflict on the graph

The driver conflicts when the two branches changed the same node in irreconcilable ways, for instance two different closures of the same node or two concurrent claims. The file it leaves you is still valid JSON, carrying the list of what it could not decide.

```sh
atlas conflicts
```

It prints which nodes and which fields it stopped on, and of what kind: `concurrent close`, `concurrent claim`, `divergent state`, `value conflict`.

Then you decide, node by node, and fix it. A closure that really happened on the other copy and got lost in the merge is restored with `mutate.restore_closure` inside a script, with the original metadata read from the diff, never invented. Once the graph tells the truth:

```sh
atlas conflicts --resolve
```

It removes the annotation, declaring that you resolved it. It decides nothing on your behalf: it's a signature, not a remedy.

## 4. Renumber your scripts after theirs

Scripts are separate files and hardly ever conflict, but two copies may have created the same number.

```sh
atlas renumber <your files>
```

It moves them past the highest of the others, in the order you give, using `git mv` where needed. With no arguments it compacts the numbering; `--dry-run` shows the renames without doing them.

## 5. Check and publish

```sh
atlas doctor
atlas status
```

Before committing, `doctor` and `status` must come out clean. `doctor` also reports conflicts that are still annotated, so it's the one that tells you whether step 3 is really finished. Pushing is something the user asked for, not the automatic last step of the procedure. Ask, if it hasn't already been said.

## What not to do

- **Don't merge `graph.json` in an editor**, and don't take one of the two versions with `git checkout origin/<branch> --`. The driver already did the work by node id, and overwriting it undoes that.
- **Don't use `--ours` or `--theirs`.** Between merge and rebase the two words swap meaning, and that's the mistake people make. If you must name a branch, spell it out.
- **Don't re-run a script already applied** to the graph you took as your base: its nodes are already there, and the run dies saying the id exists.
- **Don't use `restore_closure` to close a real node.** A node is closed with `atlas close`, which checks the lock and the Answer written in the ticket.
- **Don't run `atlas conflicts --resolve` just to make the warning go away** without looking at the nodes it names. It declares that the graph tells the truth, and if it doesn't, the defect stays, only silent.
