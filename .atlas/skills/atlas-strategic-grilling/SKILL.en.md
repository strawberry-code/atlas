---
name: atlas-strategic-grilling
description: Interview the user relentlessly about a plan or design, one question at a time, until you genuinely understand each other. Use it on `grilling` nodes that settle something structural or irreversible (architecture, contract, the shape of an interface, a product call), and whenever the user asks to be grilled on a plan before building it.
---

# Grilling a foundational decision

This is the long grilling, the one for a decision that constrains many others and costs a rewrite when it goes wrong. It has no question budget and no phases: you keep going until the design tree has been walked to its ends. If the node is narrow instead, about code, with a handful of choices to settle in one session, the right skill is `atlas-tactical-grilling`.

## The method

The core is Matt Pocock's `grilling` skill, which Atlas ships so that the `grilling` node type means something on machines where that skill isn't installed.

> Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.
>
> Ask the questions one at a time, waiting for feedback on each question before continuing. Asking multiple questions at once is bewildering.
>
> If a *fact* can be found by exploring the codebase, look it up rather than asking me. The *decisions*, though, are mine — put each one to me and wait for my answer.
>
> Do not enact the plan until I confirm we have reached a shared understanding.

Those four lines hold together end to end. One question at a time buys little if the answer doesn't reshape the next question, and always offering your recommended answer is what separates an interview from a questionnaire: people correct a proposal far faster than they fill a blank page.

## Where it lands, in an Atlas node

A `grilling` node is almost always HITL, and the grilling is its work, not a preliminary. As you go, record in the ticket's **Work** section the alternatives the user rejected and why: that is the part nobody reconstructs later. At the end, under **Answer**, write the decision that was made, not the transcript of the interview.

If the decision produces an artifact (an ADR, a design document, a schema), that artifact has to exist before the node closes: the contract says a `grilling` node is done when the decision is written **and** the artifact it produces exists. For domain vocabulary and ADRs use `atlas-domain-modeling` too.

Whatever surfaces and would deserve a node of its own doesn't become one on impulse: note it with `atlas fog "..." --for <ID>` and put it to the user when the node closes.
