---
name: atlas-prototype
description: Builds a throwaway prototype that answers a `prototype` node's question: a minimal TUI to feel whether a state model holds up, or interface variants to look at side by side. Use it on the graph's `prototype` nodes, and whenever the user wants to react to something concrete instead of a description.
---

# Prototyping to answer a node

A prototype is **throwaway code that answers a question**. The question decides the shape, and it's already written: it's the node's question, the one `atlas take <ID>` printed for you. A prototype that answers a different question is wasted, however good it looks.

A `prototype` node is HITL. The artifact is there to raise the resolution of the conversation, not to replace it: you build it, you put it in front of the user, you listen to the reaction.

## Pick the branch

- **"Does this logic, this state model, hold up?"** → the *logic* branch: a tiny TUI that pushes the state machine through the cases that are hard to reason about on paper.
- **"What should it look like?"** → the *interface* branch: several radically different variants on the same route, switchable on the fly.

Getting the branch wrong throws away the whole prototype. If the node's question is ambiguous and the user isn't reachable, choose from the surrounding code (a backend module points at logic, a page or a component at interface) and state the assumption under **Work**.

### The logic branch

Isolate whatever answers the question behind a small, pure interface that could be lifted out and dropped into the real code: a reducer `(state, action) -> state`, an explicit state machine, a handful of pure functions. No I/O and no terminal code in there. The TUI around it is throwaway, the module isn't, and that's what makes the prototype useful past its own lifetime.

The TUI redraws the whole frame on every action instead of appending lines: current state first, one field per line, then the available keys at the bottom. The user should see one stable screen, not a growing scrollback.

### The interface branch

Three variants by default, five at most: past that they stop being different and start being noise. Mount them **inside a page that already exists**, switched by a URL parameter, and keep the real data, the real permissions, the real density. A new empty route is a vacuum where every variant looks fine, and it hides exactly the problems a populated page would expose. Only if there genuinely is no page that could host them, create a throwaway route following the routing convention already in use, named so anyone can see it's a prototype.

## The rules that apply to both

1. **Throwaway from day one, and marked as such.** Put it next to where the real code will go, so the context is obvious, but name it so nobody mistakes it for production.
2. **One command to run it**, whatever the project already uses. The user has to be able to start it without thinking.
3. **No persistence.** State lives in memory: persistence is what the prototype is checking, not something it should lean on.
4. **No polish.** No tests, no abstractions, no error handling beyond what it takes to make it run.
5. **Surface the state.** After every action, or on every variant switch, render everything that changed.

## How the node closes

The contract says a `prototype` node is done when **the artifact can be looked at** and the ticket says **what was learned and what was discarded**. Both together: a prototype handed over without a verdict leaves the next person with the same doubt as before.

Under **Work**, note the variants you discarded and why. Under **Answer**, write the decision the prototype made possible, not the chronicle of how you built it. When closing, declare the files:

```sh
atlas close <ID> -s "variant B holds up, the other two don't" --artefatti prototypes/settings-variants.tsx
```

The validated decision goes into the real code as its own piece of work, which is not this node. The prototype stays where it is, declared among the artifacts; if it clutters the main branch, move it to a throwaway branch and cite that in the Answer.
