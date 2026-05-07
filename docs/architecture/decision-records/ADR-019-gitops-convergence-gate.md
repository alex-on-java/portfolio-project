---
status: accepted
date: 2026-04-30
decision-makers: [alex-on-java]
---

# GitOps Convergence Gate: In-Cluster Health Aggregation as a Required Merge Check

## Context and Problem Statement

After a PR triggers ephemeral cluster provisioning, three status checks confirm pipeline mechanics: `build / build` (code compiles), `dispatch-pr-push` (cluster-pool received the dispatch), and `Ephemeral Cluster` (infrastructure was provisioned). One informational status reports `Ephemeral DNS`. None of them confirm whether ArgoCD Applications reached `Synced+Healthy` or whether Kargo promotions completed.

The observable consequence is silent broken deployments: a misconfigured Helm chart, a wrong sync-wave ordering, or a failed Kargo promotion produces no PR feedback. The PR is mergeable, the bug reaches `master`, and the only contemporaneous detection path is manual inspection of ArgoCD's dashboard across ~15–20 Applications and several Kargo Stages — a step that gets skipped because "it was fine last time."

The convergence gate must close this gap with a single required commit status that reflects sustained health across all dynamically-discovered Applications and Stages, with no silent failure mode.

## Decision Drivers

- A merge gate that passes when the underlying deployment is broken is worse than no gate.
- The application set is actively evolving — any mechanism that requires per-app maintenance silently degrades as new ApplicationSets land.
- The credential that posts commit statuses lives in the cluster as a `Secret`; its blast radius on exposure must be bounded.
- ArgoCD has a documented transient `Synced` window before it detects a fresh mutation; a single observation can be falsely-positive.
- Branch protection in GitHub requires statically-named contexts; per-app dynamic contexts are not addressable.
- Provisioning + reconciliation can take 10+ minutes; a CI-side polling loop is wasteful (billing) and fragile (timeouts), and blurs the CI/CD boundary.

## Considered Options

1. **GitHub Actions workflow polling** — a workflow polls ArgoCD/Kargo APIs from outside the cluster until convergence or timeout, then posts a commit status.
2. **In-cluster checker Deployment** — a small workload runs inside the ephemeral cluster, discovers Applications and Stages via the K8s API, evaluates their health each cycle, and posts an aggregated commit status.
3. **Per-application GitHub Check Runs** — each ArgoCD Application emits its own Check Run via ArgoCD Notifications.

## Decision Outcome

**Option 2 — an in-cluster checker Deployment** — with six non-negotiables that bound the design:

### 2.1 Dynamic discovery only

The checker discovers ArgoCD Applications and Kargo Stages via the K8s API at runtime. No hardcoded application names, no stage lists in config. The 10× framing is direct: a hardcoded list works at 1 ApplicationSet, is a maintenance burden at 10, and is a blocker at 100. Namespace inputs come from explicit sources — ArgoCD namespace from the `cluster-identity` ConfigMap; Kargo namespaces from `Project` CRs at API discovery time — never from "current namespace" defaults.

### 2.2 Single aggregated commit status

The checker posts one commit status under a single fixed context name. Branch protection requires a statically-named context. Per-app Check Runs would require dynamic protection rules that update when ApplicationSets change — moving the burden into branch-protection management.

### 2.3 Two-layer fail-safe

The system is designed so a missing required check blocks merge, and the watchdog provides an explicit `failure` signal as belt-and-suspenders.

If the checker `Deployment` never becomes ready, the commit status never appears — branch protection still blocks the merge. This is the primary safety property: silence is failure. A separate watchdog `CronJob` (in `portfolio-project-infra`) reads the heartbeat ConfigMap; if the heartbeat is stale beyond a grace window, the watchdog posts an explicit `failure` directly to the commit, turning a debugging mystery into an actionable signal. The two layers cover orthogonal failure domains: layer 1 protects against "checker never started"; layer 2 reports "checker started then died."

### 2.4 Sustained-health stability counter

The checker requires the same healthy verdict on N consecutive cycles before declaring convergence. A single "all healthy" snapshot is not sufficient — ArgoCD's transient `Synced` window means a one-shot check can be falsely-positive. The stability counter is bounded so the status description does not grow unboundedly across long-running clusters (see `LL-0033`).

### 2.5 Dedicated, minimally-scoped GitHub App

The convergence gate uses its own GitHub App with `statuses:write` only — not the existing broadly-scoped App used elsewhere. The credential lives in the cluster as a `Secret`; minimizing scope bounds the blast radius if the cluster credential is exposed.

### 2.6 Unit-testable evaluator

The decision matrix that classifies "converging vs. stable vs. broken" lives in a Python application with test coverage, not in shell scripts or inline container commands. The evaluator is the safety-critical path — a misclassification either blocks valid PRs or passes broken ones, and both failure modes erode trust in the gate.

### Consequences

- **Good**: every PR receives a single deterministic merge gate that reflects actual deployment health, scaling without per-app maintenance.
- **Good**: silence-is-failure default + watchdog cover the realistic failure-domain matrix without requiring manual triage.
- **Good**: minimally-scoped credential and in-cluster execution keep both blast radius and CI cost bounded.
- **Bad**: more moving parts than a CI-side check — Deployment, ServiceAccount, two ConfigMaps, App credentials Secret, watchdog CronJob.
- **Bad**: the gate's correctness depends on the evaluator faithfully modeling ArgoCD/Kargo state semantics — a bug in field mappings reports false-green or false-red. Mitigated by `ADR-020`'s integration-test choice and by the cross-references in `LL-0026`/`LL-0027`.

## Pros and Cons of the Options

### GitHub Actions workflow polling

- **Good**: zero in-cluster footprint; runs in the platform layer where most existing CI lives.
- **Bad**: 10+ minute polling consumes GHA minutes for the entire reconciliation duration; large PRs pay disproportionately.
- **Bad**: GHA workflows have a hard wall-clock timeout; long reconciliations can hit it and produce inconclusive results.
- **Bad**: blurs the CI/CD separation — verification of deployment state runs outside the cluster that owns the deployment.

### In-cluster checker Deployment

See **Decision Outcome** above.

### Per-application GitHub Check Runs

- **Good**: granular per-Application visibility; failures point directly at the source.
- **Bad**: branch protection requires statically-named contexts; the protection rules would need to update every time an `ApplicationSet` is added or removed.
- **Bad**: large PRs cause check-list noise; a single Application failure is hard to distinguish from a transient.

## More Information

- `ADR-002` — ephemeral and main cluster separation (the gate is scoped to ephemeral PR clusters).
- `ADR-021` — the persistence and recovery model that supports the in-cluster checker and the cross-party ConfigMap contract.
- `ADR-023` — `managedFieldsManagers` for cooperative writes on the heartbeat ConfigMap.
- `LL-0026`, `LL-0027` — ArgoCD/Kargo status-field reality that shapes the evaluator's actual field mappings.
- `LL-0033` — ArgoCD's transient-Synced window that motivates §2.4's stability counter.
