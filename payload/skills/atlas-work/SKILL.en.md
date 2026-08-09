---
name: atlas-work
description: Works a node of this project's Atlas graph, from picking off the frontier to closing it. Use it when the user asks to move the work forward, to take the next task, or names a node of the graph.
---

# Working a node

The graph says what's up for grabs right now. One node per session, from claim to close. If this project's contract isn't already in your context, `atlas how-to` prints it along with the commands, the mutations and the paths.

## 1. Get your bearings

```sh
python3 .atlas/atlas status
```

Also read the active graph's map, `.atlas/graphs/<slug>/map.md`: the Destination says where this is going, the Notes say the standing preferences, the Decisions made say what's already been decided and from which node, close or reasoned release. No need to open closed tickets: the map is the index, you zoom in only on what you actually need.

If `status` flags orphan or stalled locks, sort them out before claiming anything else. With several nodes up for grabs at once, `atlas next` ranks them by impact (how many they unlock, how much path is left), as a suggestion.

## 2. Choose, claim, and read the context

The user names the node. If they don't, check `atlas next` or take the first one on the frontier.

```sh
python3 .atlas/atlas take <ID>
```

`take` claims the node and prints its card (branch, type, mode, status), question, blockers' answers, and the fog that names it, in the same step — the same package `atlas brief <ID>` gives, without rebuilding it by hand from ticket after ticket.

**Claim before reading, not after.** That's why `take` exists instead of `show` followed by `claim`: the claim exists so a parallel session skips this node, and one taken at the end has protected nothing.

If the claim is refused because this identity already holds one, close or release that one first. Don't reach for `--force` out of habit.

## 3. Stop if the node says HITL

The line under the title, printed by `take`, says branch, type, mode, and status.

- **AFK**: you work it alone. You write the answer.
- **HITL**: the answer gets built by talking with the user. Bring the question, one at a time, and wait. Answering on their behalf is the fastest way to make the graph pointless.

For `grilling` nodes use the `grilling` and `domain-modeling` skills, for `prototype` ones the `prototype` skill, for `research` ones the `research` skill, if installed. The map's Notes may name others.

## 4. Work, and leave a trail in the ticket

The ticket is `.atlas/graphs/<slug>/tickets/<ID>.md`. Write from **Work** downwards: everything above the `<!-- /atlas:auto -->` comment descends from the graph and rewrites itself, so fixing it by hand is wasted effort. While working, note in **Work** the alternatives you discarded and links to the artifacts produced. At the end, fill in **Answer**: it's the only thing `close` checks, and it's for whoever arrives after you.

If something comes up that would deserve a node of its own, **don't create it**. Note it down, addressed to a node if it concerns one:

```sh
python3 .atlas/atlas fog "what came up, in one line" --for <ID>
```

and propose it to the user once the node is done. The graph's shape changes only through a mutation script, never on impulse in the middle of other work. To turn one into a node there's a ready example at `.atlas/scripts/000-promote-fog.py`: fill in the entry's index and the node's fields, then run it with `atlas exec`.

## 5. Close it

```sh
python3 .atlas/atlas close <ID> -s "the one-line summary"
```

To leave a rough order of magnitude for what it cost (calls, tokens, time), add `-c/--costo "..."`. You don't have to list the files you produced: inside a git repository `close` works them out on its own, from what you touched since you claimed the node. If you're working in parallel with other nodes, this deduction skips and you must declare the artifacts with `--artefatti path/one path/two`. `--artefatti` with no arguments leaves the field empty. In the ticket, the **Non-canonical choices**, **Declared debt**, and **Authorizations received** sub-sections under Answer are optional: use them when there's actually something to say, leave them empty otherwise.

The summary lands on its own in `map.md` under Decisions made, and the dashboard regenerates. If `close` refuses because the Answer is empty, write it: it's not an obstacle to route around with `--force`.

**One node per session, even when one more is still up for grabs.** Once the node is closed, stop and report what was decided and what opened up. The next node is the user's choice, not the session's inertia.
