# 0001 - The graph moves to a centralized service

**Status**: **deferred, pending field trial**. Designed and decided 2026-08-26 in a strategic
grilling session, then held back the same day because the alternative it replaces turned out to be
finished and working.

Nothing here is being built yet. The two-speed design (distributed lock over git refs, per-node
merge driver) is implemented and goes into real use first. This ADR is the answer to "what do we
do if that hurts", and the trial below decides whether we ever need it.

**Trial and decision rule.** Two machines, two identities, real work, until 2026-09-09 at the
earliest. The instrument already exists and needs no new code: `merge.py` records `concurrent
close`, `concurrent claim` and `divergent state` into the graph's `conflicts` field, and
`atlas doctor` reports them. Run it after every merge.

Switch to this design if either holds:

- one `concurrent close` on a node that cost more than an hour of work, or
- three `divergent state` or unresolvable merges within the fortnight.

Otherwise the two-speed design stays and this ADR is superseded, not implemented. The numbers were
fixed before any data existed, on purpose. Note the limit: the count measures **frequency**, not
**cost**, and one duplicated hard node can outweigh ten trivial conflicts. Judge accordingly.

## Context

Atlas today is a single zero-dependency executable. The graph is `graph.json` inside the host
repo, tickets are markdown files next to it, and everything travels with git.

That model breaks as soon as two agents on two machines work the same graph. Not because of a
bug: because the design holds **two truths at two speeds**. Coordination (who holds what) must be
instantaneous; work state (what is closed, what the answer says) travels at git speed. A lock that
is fresher than the graph it protects tells the truth about a map that is already stale.

We first tried to fix this without a server: a distributed lock built on custom git refs
(`refs/atlas/claims/*`), leases instead of PID liveness, and a per-node merge driver for
`graph.json`. It works, it is committed, and it still leaves the hole open. When Pedro **closes**
a node and releases the ref, Cristiano's stale graph still says `open` and the ref is gone.
Cristiano takes the node and redoes finished work. The lock cannot protect against that, because
the lock disappears exactly when the work completes.

The alternative is to remove the divergence instead of managing it: one authority, one graph.

## Decision

**1. The graph leaves the repo.** Graphs and tickets live on an Elixir service. Transport is
WebSocket (Phoenix Channels). Being on the BEAM is not incidental: socket monitors give real
distributed liveness, which makes the whole TTL-and-lease apparatus unnecessary. Leases were only
ever a poor substitute for "git cannot tell me who is connected right now".

**2. Both modes ship.** `atlas install --offline` (today's behaviour, unchanged) or
`atlas install --remote=https://…`. The cost is not offering two modes; it is guaranteeing they
behave identically. That obligation is accepted deliberately.

**3. The local mirror is writable offline.** Every action is timestamped and queued. On
reconnection the server decides what conflicts. Read commands always work against the mirror and
declare the age of the data.

**4. Assignment becomes binding in remote mode.** `model.frontier()` today only looks at status
and blockers, it is blind to `owner`, so `atlas next` happily suggests nodes assigned to someone
else. In remote mode the frontier hides other people's nodes, and an offline claim is allowed
**only** on nodes already assigned to you. This is what makes decision 3 safe: exclusivity is
obtained in advance, declared in the graph, so the mirror is not inventing a lock it has no right
to grant. Unassigned nodes still require a synchronous claim.

**5. Authentication is SSH public keys.** Public keys installed on the service by a maintainer,
private keys stay with clients, no new credential to distribute. Since assignment is now a
permission and not a label, identity must be provable. Verified: the Python stdlib cannot sign
asymmetrically and every library that can is a forbidden dependency, but `ssh-keygen -Y sign` /
`-Y verify` does it as a subprocess (298-byte signature, ~7 ms, `allowed_signers` is literally the
list of installed public keys). Windows needs OpenSSH >= 8.0, present by default since 2018.

**6. The repo keeps one file, the mirror lives outside it.** `.atlas/project.json` is versioned
and holds service URL, slug, mode, and the dashboard path, so whoever clones discovers the graph
exists. The mirror sits in `~/.cache/atlas/<slug>/`, outside the repo, because `git clean -xdf`
would otherwise delete the offline queue along with unreconciled work, and because two worktrees
should share one mirror. A gitignored symlink `.atlas/dashboard.html` points at the mirror for
humans with a hundred projects; where symlinks fail the path in `project.json` is the fallback.
JSON, not TOML: `tomllib` is read-only and only exists from 3.11, while Atlas targets 3.10, so
TOML would mean hand-writing both a parser and a serializer.

**7. Mutation scripts run on the server, in a throwaway sandbox.** Sending the resulting state
would be wrong, and sending only the captured operations would be worse than it looks: Atlas
scripts can branch on state (`g.ids()`, `g.node()`, `g.data` are exposed on purpose), so a script
executed client-side freezes a decision taken against yesterday's graph. Running it against the
authoritative state is more correct. The blast radius is contained by executing it in an ephemeral
sandbox holding only that `graph.json`, no network, with a timeout. Worst case is one damaged
graph, never the service.

**8. Rendering happens on the server, and only an event is broadcast.** The server owns the
authoritative graph and is the only party that knows every lock, so it renders. It does not push
HTML: measured on a small graph, `dashboard.html` is 113 KB against 9 KB for `graph.json` and
~20 bytes for a "changed" event. Clients reload from the server, so traffic is paid only when
somebody is actually looking. This is what `serve.py` already does with its EventSource.

**9. Publication state is derived, never stored.** No `artifacts_pushed` flag. Closing writes an
immutable fact, `closedWith: {repo, sha, branch}`. Everything else is a question for git:
`git merge-base --is-ancestor <sha> origin/main` answers in ~17 ms with an unambiguous exit code.
The dashboard shows three states (**closed**, **published**, **integrated**) and stores none of
them. A stored flag lies after a force-push or a deleted branch; a query cannot. Since the service
already hosts git repos, a bare mirror of the project repo answers for every node of every project.

**10. The service owns nothing that is not in a git repo.** One git repo per graph, pushed
asynchronously to a remote after every accepted mutation. Hard rule: indexes, presence, live locks
and render caches must all be rebuildable from the repos alone. Losing them costs nothing, because
sessions reconnect and leases re-establish. Disaster recovery is `git clone` plus `atlas --offline`,
not a restore procedure. This gives back the N copies that the centralized design took away,
without reintroducing divergence, because those copies are backups and not competing authorities.

## Consequences

The incoherence that motivated all of this disappears: there is one authority, so a stale map is
no longer possible for anyone who is online.

Atlas changes category. It stays installable with `curl` in offline mode, but sharing work now
requires somebody to host a service. Two modes must be kept behaviourally identical forever, and
that is the real long-term cost of this decision.

Work already committed becomes obsolete. The git-refs remote lock (`payload/core/remotelock.py`,
`atlascli/remotelock.py`), the lease and heartbeat machinery, and the per-node merge driver all
exist to cure a divergence this design does not produce. Most of the `260825-sync-distribuita`
graph needs to be redrawn.

## Rejected alternatives

**Keeping the git-refs lock** (partially built). Rejected: it guarantees mutual exclusion but not
coherence, and the closed-node hole is structural, not fixable.

**Refusing offline writes** so that no reconciliation is ever needed. Rejected: it turns the remote
mode into a read-only client whenever the network is missing. Binding assignment (decision 4) makes
offline writes safe without giving up the property.

**MCP as the architecture.** MCP is a transport for exposing tools to an agent; it carries no
synchronization and would leave every hard problem intact behind the interface. It stays available
as a way for agents to read tickets, which is what removed the objection that moving tickets off
disk loses grep and editors: an agent has `search` and `read`.

**Per-person tokens** issued by the service. Rejected in favour of SSH keys: no new credential,
existing tooling, an authorization model everybody already understands.

**A boolean "pushed" flag.** Rejected: see decision 9.

**Database-only service state**, faster but recoverable only through a restore procedure.
Rejected: see decision 10.
