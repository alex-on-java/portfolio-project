---
status: accepted
date: 2026-04-30
decision-makers: [alex-on-java]
---

# Persistence Boundaries and Recovery Model for the Convergence Gate

## Context and Problem Statement

The convergence-checker (see `ADR-019`) accumulates state across cycles: a stability counter, the most recently observed verdict, the timestamp of the first `pending` observation. Three independent parties read or write shared state in the same ephemeral cluster:

- **`pool-ctl`** (in `portfolio-project-cluster-pool`) writes the PR commit SHA and the activation timestamp to `cluster-identity` when a cluster is bound to a PR.
- **The checker** (this branch) reads the PR commit SHA, posts commit statuses, and writes a heartbeat.
- **The watchdog** (a `CronJob` in `portfolio-project-infra`) reads the activation timestamp and the heartbeat to decide whether to escalate to an explicit `failure` status.

The architectural question this ADR settles is where state lives, how restarts and PR-level resets are handled, and which party owns which key on shared `ConfigMap` resources. Getting this wrong has direct merge-gate consequences: a checker that restarts and silently inherits stale state, or two parties writing to the same key, would both produce false-green outcomes.

## Decision Drivers

- The gate's correctness margin lies in the evaluator's ability to refuse premature success. Any persistence path that lets a fresh pod inherit a stale `healthy` count is unsafe.
- Pod restarts on ephemeral clusters happen rarely (Recreate strategy, `replicas=1`), but must be safe.
- `ConfigMap` writes that two parties can mutate independently are a known footgun across this stack (see `LL-0003`).
- Cross-party contracts that are implicit drift; explicit ownership is observable in RBAC and survives across the three repos.

## Considered Options

1. **Persist `ConvergenceState` to a dedicated `ConfigMap`; restore on startup.**
2. **In-memory cycle state, externally observable liveness only via a heartbeat `ConfigMap`.**
3. **Persist state via a CRD with a `status` subresource owned by the checker.**

## Decision Outcome

**Option 2 — in-memory cycle state with a heartbeat-only `ConfigMap`**, with four reinforcing properties:

### 3.1 SHA-mismatch as the reset signal

The checker reads `cluster-identity.prCommitSha` each cycle. A change in the SHA discards in-memory state and starts the counter from zero. This makes "new PR commit" the single canonical reset event in the system.

### 3.2 Pod restart structurally identical to SHA-change reset

A fresh pod starts with empty in-memory state. Combined with §3.1, the recovery path on pod restart is the same code path as on commit-SHA change — there is no second reset mechanism. The Deployment uses `Recreate` with `replicas=1`, so two checkers never observe each other's intermediate state. The trade-off: `first_pending_at` (the anchor for the safety timeout) resets on restart, extending the timeout window by up to one duration. This is acceptable because (a) explicit failures are reported immediately, independent of the timeout; (b) restarts on ephemeral clusters with `replicas=1` are rare.

### 3.3 Heartbeat ConfigMap is liveness-only, not state

`gitops-convergence-heartbeat` carries a single key (`lastHeartbeatAt`). Its consumer is the watchdog, not the checker. The checker never reads its own heartbeat back — it is a one-way liveness signal that exists solely to give the watchdog something to observe, completing the two-layer fail-safe described in `ADR-019` §2.3.

### 3.4 Three-party ConfigMap contract with disjoint reader/writer ownership

| Key | Writer | Reader |
|---|---|---|
| `cluster-identity.prCommitSha` | `pool-ctl` | checker |
| `cluster-identity.argocdNamespace` | (set during cluster bootstrap; outside this repo) | checker |
| `cluster-identity.activationTimestamp` | `pool-ctl` | watchdog |
| `gitops-convergence-heartbeat.lastHeartbeatAt` | checker | watchdog |

The checker explicitly does not read `activationTimestamp` — that key is the watchdog's grace-period anchor only. Disjoint ownership makes the cross-party contract observable in RBAC: the checker's Role on `kargo-shared-resources` is `get`-only on `cluster-identity`; the watchdog's Role (in `portfolio-project-infra`) covers `activationTimestamp` and the heartbeat. There is no shared-mutable key in the system.

### Consequences

- **Good**: the recovery model has exactly one code path; pod restart cannot diverge from commit-SHA change.
- **Good**: cross-party RBAC is verifiable from manifests alone — no implicit contracts.
- **Good**: no migration concern when the state shape evolves; the in-memory shape is internal.
- **Bad**: long ephemeral clusters that restart late in their lifecycle absorb up to one safety-timeout duration of additional waiting before the timeout fires.
- **Bad**: the disjoint-ownership rule is a discipline that the next agent must learn and respect; an agent that adds a fifth party reading or writing one of these keys silently regresses the model. This ADR is the durable record of the rule.

## Pros and Cons of the Options

### Persisted state in a dedicated ConfigMap

- **Good**: pod restarts pick up where the previous instance left off; no extra timeout absorption.
- **Bad**: a restart that occurs after a misclassification persists the misclassification forward. The reset path becomes a second concept that must stay consistent with SHA-mismatch reset; in practice the two diverge.
- **Bad**: a second writer (e.g., a mistaken `kubectl patch` during operations) silently corrupts the counter.
- **Bad**: state shape evolution requires migration logic for in-flight clusters — a non-trivial safety surface for a feature whose entire point is bounded operation.

### In-memory state + heartbeat-only ConfigMap

See **Decision Outcome** above.

### State via a checker-owned CRD with status subresource

- **Good**: K8s-native ownership semantics; explicit observability via `kubectl get`.
- **Good**: API-server-side `status` subresource separation prevents accidental field collisions.
- **Bad**: defining a new CRD for a single-cluster, single-instance liveness-state use case is disproportionate; the CRD lifecycle (versioning, cleanup, RBAC) becomes part of the gate's surface area.
- **Bad**: requires generated clients or unstructured access — adding scaffolding for a problem in-memory state already solves.

## More Information

- `ADR-019` — the gate design that this recovery model supports.
- `ADR-023` — `managedFieldsManagers` for cooperative writes on the heartbeat `ConfigMap`.
- `LL-0003` — `Warehouse`/`Stage` perpetual OutOfSync from undeclared field defaults; the same class of footgun the disjoint-ownership rule is designed to avoid.
