---
status: accepted
date: 2026-04-30
decision-makers: [alex-on-java]
---

# `managedFieldsManagers` for Cooperative ConfigMap Writes

## Context and Problem Statement

The convergence-checker (see `ADR-019`) writes the `gitops-convergence-heartbeat` `ConfigMap` from inside the cluster on every cycle. The same `ConfigMap` is also reconciled from Git by ArgoCD: the `kustomization.yaml` declares the manifest, ArgoCD owns deployment, and `selfHeal` reverts any state that diverges from Git. Without an explicit ownership rule, ArgoCD's `selfHeal` reverts every checker write within the next reconciliation pass, breaking the heartbeat (and therefore the watchdog's view of liveness).

This is the cooperative-write case `ADR-009` anticipates: a controller writes one part of a resource, ArgoCD reconciles other parts. The architectural question this ADR settles is **how** the cooperative-write boundary is encoded — not whether an exception to ADR-009 is warranted (it is, the heartbeat field cannot be source-converged), but which mechanism encodes the boundary minimally and explicitly.

## Decision Drivers

- **`ADR-009` alignment:** any exception must be scoped narrowly and explicitly justified, not blanket-suppressed.
- **Positive ownership over passive suppression:** the rule should declare *who owns* the divergence, not *which paths to ignore*.
- **Minimum config surface:** the more switches are involved (ServerSideApply, ServerSideDiff, RespectIgnoreDifferences), the more places future agents must reason about.
- **Verifiable on the actual target:** the choice must be tested against the live ArgoCD version actually running in ephemeral clusters, not against documented behavior.

## Considered Options

1. **Path-based `ignoreDifferences` with `jsonPointers: [/data]`** — blanket suppression of any drift under the `/data` field of the `ConfigMap`.
2. **Field-manager-scoped `ignoreDifferences` with `managedFieldsManagers: [convergence-checker]`** — positive ownership declaration: ArgoCD ignores fields whose managed-field manager matches the named controller.
3. **Server-Side Apply stack** — checker writes via SSA; AppSet sets `RespectIgnoreDifferences=true`, `ServerSideDiff` enabled in compare-options, and SSA-aware ignore rules.
4. **Replace the resource type** — model heartbeat as a CR with a `status` subresource owned by the checker.

## Decision Outcome

**Option 2 — `ignoreDifferences[].managedFieldsManagers: [convergence-checker]`**, with two reinforcing properties:

### 5.1 The field-manager rule alone is the minimum config

A live PoC against the ephemeral PR-16 cluster confirmed that none of `ServerSideDiff`, `ServerSideApply`, `RespectIgnoreDifferences`, or SSA writes from the checker are required for `selfHeal` drift suppression in this case. The minimal configuration is the `managedFieldsManagers` rule on the AppSet, paired with a client-side patch from the checker that carries the `field_manager` parameter. Adding any of the other switches makes the rule no more correct and adds surface area for future confusion (see `LL-0032`).

### 5.2 The field manager name is plumbed via the environment, not via `settings.toml`

`CONVERGENCE_CHECKER_FIELD_MANAGER_NAME` is set on the `Deployment` and consumed by the checker as `settings.field_manager_name`. There is no default in `settings.toml`. A missing env var crashes the pod loudly at startup with an `AttributeError` from Dynaconf — not silently writing under a fallback manager name (which would silently break the AppSet's ignore rule).

The string `convergence-checker` lives in two places: the `Deployment`'s env var and the AppSet's `managedFieldsManagers` entry. They are a contract; if they disagree, drift suppression breaks. This is recorded explicitly here and in the heartbeat-write code path; the source of truth surface is intentionally narrow (two GitOps files), and Python is value-agnostic so the contract can move when needed.

### Consequences

- **Good**: positive ownership semantics — the AppSet manifest reads as "this controller owns this resource's writes," not "ignore drift in /data regardless of who wrote it."
- **Good**: minimal config surface — one rule on the AppSet, one env var on the Deployment, one `field_manager` kwarg on the patch. No SSA, no compare-options, no `RespectIgnoreDifferences`.
- **Good**: aligns with `ADR-009` ("scope ignores to the smallest possible target") through field-manager semantics rather than path-globbing.
- **Bad**: the field manager name is a contract across two manifests. A rename in one place silently breaks drift suppression — every checker write would be reverted by `selfHeal` again. Mitigated by the env-var-only convention (no `settings.toml` default) so a misconfigured Deployment crashes loud, but not eliminated.

## Pros and Cons of the Options

### Path-based `ignoreDifferences` with `jsonPointers: [/data]`

- **Good**: trivially obvious — the path is the rule.
- **Bad**: blanket-suppresses drift in `/data` regardless of writer. An external mutation under `/data` (e.g., a misconfigured `kubectl patch` during operations) is also silently ignored.
- **Bad**: contradicts `ADR-009` directly: the suppression is path-shaped and writer-blind, not "narrowly scoped and explicitly justified."

### Field-manager-scoped `ignoreDifferences`

See **Decision Outcome** above.

### Server-Side Apply stack

- **Good**: K8s-native field ownership semantics; the most "correct" answer in the abstract.
- **Bad**: empirically unnecessary for this case (verified on the live ArgoCD version). Adding it adds operational surface — `RespectIgnoreDifferences` flag, `ServerSideDiff` compare-options switch, SSA writes from the checker — for no observable behavioral benefit.
- **Bad**: every additional switch is one more place a future agent reasons about when investigating drift behavior; the minimum-config rule (Decision §5.1) is a stronger position than "all of the above and they all matter."

### Replace the resource type with a CR

- **Good**: native `status` subresource separation gives the checker a write surface ArgoCD does not reconcile.
- **Bad**: defining a CRD for a single-cluster, single-key liveness signal is disproportionate; CRD lifecycle (versioning, RBAC, cleanup) becomes part of the gate's surface.

## More Information

- `ADR-009` — the parent rule: prefer source fixes and ServerSideDiff over `RespectIgnoreDifferences`. This ADR records its concrete application to cooperative ConfigMap writes.
- `ADR-021` — the persistence model that defines `gitops-convergence-heartbeat` as a one-way liveness signal (the resource this ADR governs).
- `LL-0032` — the empirical finding that the field-manager rule alone suffices, recorded as the lesson separate from the decision.
- `LL-0016` — `ServerSideDiff` placement quirk that motivates the "verify on the actual target" driver here.
