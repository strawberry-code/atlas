---
name: atlas-work
description: Works a node of this project's Atlas graph, from picking off the frontier to closing it. Use it when the user asks to move the work forward, to take the next task, or names a node of the graph.
---

# Working a node

The graph says what's up for grabs right now. One node per session, from claim to close.

## 1. Get your bearings

```sh
python3 .atlas/bin/atlas status
```

Also read the active graph's map, `.atlas/graphs/<slug>/map.md`: the Destination says where this is going, the Notes say the standing preferences, the Decisions made say what's already been decided and from which node. No need to open closed tickets: the map is the index, you zoom in only on what you actually need.

If `status` flags orphan locks, sort them out before claiming anything else.

## 2. Choose and claim

The user names the node. If they don't, take the first one on the frontier.

```sh
python3 .atlas/bin/atlas claim <ID>
```

**Claim before working, not after.** The claim exists so a parallel session skips this node, and a claim placed at the end has protected nothing.

If the claim is refused because the session already holds one, close or release that one first. Don't reach for `--force` out of habit.

## 3. Check the node's mode, and stop if it says HITL

```sh
python3 .atlas/bin/atlas show <ID>
```

- **AFK**: you work it alone. You write the answer.
- **HITL**: the answer gets built by talking with the user. Bring the question, one at a time, and wait. Answering on their behalf is the fastest way to make the graph pointless.

For `grilling` nodes use the `grilling` and `domain-modeling` skills, for `prototype` ones the `prototype` skill, for `research` ones the `research` skill, if installed. The map's Notes may name others.

## 4. Work, and leave a trail in the ticket

The ticket is `.atlas/graphs/<slug>/tickets/<ID>.md`. While working, note in **Work** the alternatives you discarded and links to the artifacts produced. At the end, fill in **Answer**: it's the only thing `close` checks, and it's for whoever arrives after you.

If something comes up that would deserve a node of its own, **don't create it**. Note it down:

```sh
python3 .atlas/bin/atlas fog "what came up, in one line"
```

and propose it to the user once the node is done. The graph's shape changes only through a mutation script, never on impulse in the middle of other work.

## 5. Close it

```sh
python3 .atlas/bin/atlas close <ID> -s "the one-line summary"
```

The summary lands on its own in `map.md` under Decisions made, and the dashboard regenerates. If `close` refuses because the Answer is empty, write it: it's not an obstacle to route around with `--force`.

**One node per session, even when one more is still up for grabs.** Once the node is closed, stop and report what was decided and what opened up. The next node is the user's choice, not the session's inertia.
