---
name: atlas-tactical-grilling
description: A three-phase operational grilling on a narrow task, usually about code: first the agent establishes on its own what the code already answers, then it brings the user a declared number of structured questions (twelve by default), then it merges the two into a plan to be confirmed. Use it on narrow `grilling` nodes and whenever the user asks to be grilled before a change.
---

# Grilling a narrow task

Use it when the open choices are few, they live in code you can read right now, and the session has to end with a plan you can execute. If the decision is structural instead and constrains many others, the right skill is `atlas-strategic-grilling`, which has neither phases nor a budget and runs until the tree has been walked.

Three phases, in this order, and the second one doesn't start before the first is done.

## Before you start: declare the budget

Questions to the user are **twelve** by default. Before opening phase 2, announce how many you'll ask, and wait: that's where the user changes it, saying "make it five" or "go up to twenty". On a tiny task, propose a lower number yourself instead of padding the count.

The budget is a ceiling, not a quota. If the real questions run out at six, you stop at six: inventing six more to reach twelve is the fastest way to lose the user's trust in the method. If they run out while choices are still open, say so and ask to widen it.

## Phase 1 — Reconnaissance on your own

Before asking anything, go and look. Read the code the task touches, the tests guarding it, the conventions already in force in neighbouring files, the written constraints (the project's `CLAUDE.md`, the Atlas contract, the Answers of the blocking nodes, the map's Notes).

**A fact that lives in the code is never a question.** Asking the user what a function is called, whether a test exists, or which library is already in use burns one of the budgeted questions and says you didn't look.

The phase ends when you have two lists, and you show them:

- **Established**: what you found, in short lines, with file and line. It's the ground the questions will stand on, and the user has to be able to correct it right away if you read it wrong.
- **Open**: the decisions still to make, ordered with the ones that constrain others first. An answer given early prunes whole branches and hands you back budget.

## Phase 2 — The questions

**One question per call.** `AskUserQuestion` takes up to four at once, and that's not how it's used here: the answer to one reshapes the next, and four answers given in a block are four answers nobody thought about.

Every question has four parts, in this order:

1. **Context**: what you saw that raises the question. One or two concrete lines, with the file if it helps.
2. **Reasoning**: why the choice isn't obvious, and what changes downstream depending on how it goes.
3. **The question**, stated plainly.
4. **The recommendation**: what you'd do and why. It isn't a courtesy, it's the part that makes the answer fast: correcting a proposal costs far less than filling a blank page.

How they map onto the fields:

- `question` carries all four parts. Don't leave the context in the chat text before the call: the history keeps the bare question, and the user re-reads something that no longer makes sense.
- `header` is the subject of the choice in twelve characters, not the question abbreviated.
- Options put the consequence of picking them in `description`, not a paraphrase of the label. The recommended one comes first, with `(recommended)` at the end of its label.

**The normal shape is yes or no**, two options, because with the recommendation already written the user only has to confirm or refuse it. Multiple choice is for when the choice really is between different alternatives, and then one rule doesn't bend: **every option has to be viable.** No option there to pad the count, none written badly on purpose so the recommended one wins. If you can't write the third option in a way you'd defend, then there are two options.

As you go:

- If an answer makes queued questions pointless, drop them and say so instead of asking them anyway.
- If an answer opens one you hadn't planned, queue it and say the count has changed.
- If you realise a question could have been settled by reading the code, don't ask it: go back to phase 1 for a moment.
- Don't answer on the user's behalf. Silence isn't consent, and "I'll go with the recommendation unless you say otherwise" is not an answer received.

## Phase 3 — The synthesis

Put the two halves back together, what you established on your own in phase 1 and what the user decided in phase 2, into a single plan: what gets done, in what order, and what was deliberately left out. Each decision the user made is cited together with the question it answered, so a reader can tell what was decided from what you inferred from the code.

**Don't execute before the user confirms the synthesis.** Answers to individual questions are not agreement on the plan: the user declares that, on the whole plan, once.

In an Atlas node: phase 1's lists and phase 2's rejected alternatives go under **Work**, the confirmed plan under **Answer**, and whatever you settled on your own without asking goes under **Non-canonical choices**. If something surfaces during the grilling that would deserve a node of its own, don't create it: note it with `atlas fog "..." --for <ID>` and put it to the user when the node closes.
