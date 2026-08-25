---
name: atlas-domain-modeling
description: Builds and sharpens the domain language while decisions are being made: challenges ambiguous terms, pins them down in a glossary, and records as ADRs only the decisions that are expensive to reverse. Use it alongside the two grilling skills on nodes that decide something, and whenever a project word is used with two different meanings.
---

# Sharpening the domain language

This is an active discipline, not a reading: you challenge terms, invent edge-case scenarios, and write the glossary the moment a word becomes clear. Reading the glossary to learn what things are called is a one-line habit any skill can do; this one is for when you're **changing** the model.

It works in pairs with `atlas-strategic-grilling` and `atlas-tactical-grilling`: the grilling brings the questions, this pins down the words the answer gets written in. Without it, the graph accumulates tickets that say "account" meaning three different things.

The domain glossary has nothing to do with `vocab` in `.atlas/config.json`, which is the harness's vocabulary (types, modes, statuses) and not the project's.

## During the session

**Challenge against the glossary.** When the user uses a term that conflicts with the one already pinned down, say so immediately: "the glossary says *cancellation* is X, but you seem to mean Y: which is it?".

**Sharpen vague language.** Faced with an overloaded term, propose the precise one: "you're saying *account*: do you mean the Customer or the User? Those are different things".

**Bring concrete scenarios.** When relationships between concepts are being discussed, invent the edge case that forces precision about the boundary. That's where wrong models break, not in general definitions.

**Cross-reference with the code.** When the user states how something works, go and see whether the code agrees. If they contradict each other, surface the contradiction right away instead of working around it.

## Where it gets written

**The glossary** lives in a `CONTEXT.md` at the project root, created when the first term is resolved and updated on the spot, never batched up at the end of a session. An entry is the term, one or two sentences saying **what it is**, not what it does, and the synonyms to avoid:

```md
**Order**:
A customer's request, from cart to delivery.
_Avoid_: purchase, transaction
```

Only terms specific to this domain. General programming concepts don't belong, however much the project uses them. `CONTEXT.md` is a glossary and nothing else: not a spec, not a scratch pad, and not a home for implementation decisions.

**An ADR** is offered only when all three hold: the decision is **hard to reverse**, it's **surprising without the context** (a year from now someone will wonder why), and it's the result of a **real trade-off**, with genuine alternatives that were rejected. If one is missing, the ADR isn't worth it. A single paragraph in `docs/adr/NNNN-slug.md` will do, numbered after the existing ones: what matters is that the decision is on record along with its reason, not that the document has every section.

## How it lands in the node

The words pinned down and the ADRs written are artifacts of the node, and get declared when it closes:

```sh
atlas close <ID> -s "Order and Shipment are two distinct entities" --artefatti CONTEXT.md docs/adr/0003-order-and-shipment.md
```

If a preference about language should hold for the whole graph and not just this node, its place is the map's Notes, with `mutate.note_add` inside a mutation script.
