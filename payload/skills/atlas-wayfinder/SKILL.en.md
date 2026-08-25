---
name: atlas-wayfinder
description: The doctrine behind an Atlas graph: naming the destination, deciding rather than doing, telling fog apart from a node, ruling out of scope whatever sits past the destination. Use it when a loose idea arrives that is too big for one session and still wrapped in fog, before you even know a graph is warranted.
---

# Finding the way

A big idea has arrived, and the way from here to the **destination** isn't visible yet. Finding that way is the work, not charging at the destination head down. An Atlas graph is the map of that search: nodes that each settle one uncertainty, until the route is clear and nothing is left to decide.

This skill is the method. The mechanics of building a graph live in `atlas-new-graph`, the mechanics of working it in `atlas-work`.

## The destination is named first

The destination is what you see when the map is finished: a spec to hand off, a decision to lock before planning can start, a change made in place like a data migration. One or two lines, and they live in `map.md` under **Destination**: every session orients to it before picking a node.

You name it first because it **fixes the scope**. Everything that follows, which nodes exist and which don't, is measured against it.

## You decide, you don't do

A graph plans. Each node settles a decision, and the map is done when the way is clear, meaning nothing is left to decide before someone goes and builds. The urge to just get on with the work, which shows up almost every time, is usually the signal that you've reached the edge of the map and it's time to hand off.

The `task` type is the exception that proves the rule: it does real work, but it earns its place by unblocking a decision, not by delivering the destination. A project that wants execution inside the map declares it in the **Notes** with `mutate.note_add`. Absent that declaration, produce decisions.

## Call them by name

Atlas ids are short (`F01`, `X02`) and they exist for the commands. When you talk to the user, though, a wall of ids is illegible: always name the title next to the id. The id doesn't vanish, it rides inside the name instead of standing in for it.

## The map is an index, not a store

`map.md` says where you're going, what has already been decided, and which node holds the detail. It never restates the Answers: a decision lives in exactly one place, its ticket. That's why the summary you pass to `atlas close -s` is **one line**, not a recap: that line lands in Decisions so far, and it's the only thing a future session reads before deciding whether to open the ticket.

## Fog or node

The map is deliberately incomplete: you don't chart what you can't see. Beyond the live nodes lies the fog, the decisions you can feel coming but can't yet phrase, because they hang on questions still open. Settling a node thins the fog ahead of it, and whatever became phrasable graduates into a node, one at a time.

**The test is whether you can state the question now, not whether you can answer it.**

- **A node** when the question is already sharp, even if it's blocked and you can't touch it today.
- **Fog** when you can't yet phrase it that way. Note it with `atlas fog "..."` (or `mutate.fog_add` in a script) and it lands under **Not yet specified**. Don't pre-slice it into node-sized pieces: it's coarser than a node, and a single patch may become three nodes or none.

Fog excludes what's already decided, what's already a live node, and what's out of scope.

## Out of scope isn't fog

Fog only ever gathers **toward** the destination. What lies past it isn't fog that hasn't lifted yet, it's work you have consciously ruled out of this graph. What separates the two is scope, not sharpness.

When a node that already exists turns out to sit past the destination, you neither resolve it nor delete it:

```python
mutate.drop(g, "X03", "past the destination: migrating the historical data is its own effort")
```

`drop` moves it to `out-of-scope`, takes it off the frontier, writes it under **Out of scope** with the reason, and keeps it unblocking whatever waited on it. It never comes back: if the destination gets redrawn, that's a new graph, not a resumption of this one.

## One node per session

Charting the map is one session's work, and no node gets resolved in that same session. While working, you close one node and stop: the next one is the user's choice. Other sessions may work unblocked nodes in parallel, and the shared copy is brought back in line with `atlas-sync`.
