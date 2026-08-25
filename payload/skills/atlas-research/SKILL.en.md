---
name: atlas-research
description: Works a `research` node by going to primary sources and writing a document that cites every claim with a link and a date. Use it on the graph's `research` nodes, and whenever something outside this working directory has to be known before deciding from memory.
---

# Answering a research node

A `research` node is AFK: you write the answer yourself, without going through the user. That's exactly why the contract puts the hardest constraint of all four types on it, that **the answer cites sources read just now, with link and date, not remembered**. A model recalls last year's API with the same confidence as yesterday's, and a research node closed on a memory poisons every decision that leans on it.

## 1. Go to the source that owns the fact

Primary sources: the official documentation, the source code, the spec, the first-party API, the project's changelog. Not somebody's write-up of them. Every claim is followed back to whoever actually owns it, and when the chain stops at a blog post, that's a lead, not a source.

If the reading is long you can hand it to a background agent and keep going meanwhile, but the claim and the Answer stay with this session: whoever claimed the node is who answers.

## 2. Write the document

A markdown file, wherever the project already keeps notes like these. If there's no convention, put it somewhere sensible and say where in the Answer.

Every claim carries its link and the **date you read it**, in ISO form. The date isn't bureaucracy: a documentation page shifts under your feet, and six months from now the only way to know whether what you wrote still holds is knowing when it held.

Three cases to write down rather than smooth over:

- **The sources contradict each other.** Report both, say which one you went with and why. Choosing silently hides the very information that was needed.
- **The answer isn't there.** Declare the partial coverage: what you found, what you didn't, where you looked. A declared gap is a result; a gap filled by intuition is damage.
- **The version matters.** Version number next to the fact, every time the fact depends on it.

## 3. Close

The ticket's Answer is the **summary with the load-bearing links**, not the document pasted in: the document is the artifact, and it lives in one place only. Someone reading the ticket has to understand what was found and which decisions are now possible, without opening the file.

```sh
atlas close <ID> -s "the API does support batching, but not past 100 items" --artefatti docs/research-batch-api.md
```

If something surfaces while reading that would deserve a node of its own, don't create it: `atlas fog "..." --for <ID>` and put it to the user when the node closes.
