# LL-0035: Kargo migrations must be made safe at the git layer — cluster-side gating (ProjectConfig pause, RBAC patches) is reverted by ArgoCD selfHeal faster than a Promotion can land

## Summary

A natural reflex when migrating Kargo resources (CPT path expressions, Stage promotion templates, Warehouse subscriptions) is to gate the migration with cluster-side controls — pausing auto-promotion via a `ProjectConfig.promotionPolicies[].stageSelector` patch, applying temporary RBAC restrictions, or annotating Stages to suppress their reconciliation. In a GitOps-managed Kargo install, those controls are owned by ArgoCD: any cluster-side patch is reverted by `selfHeal` within seconds — typically faster than a Promotion can land, and certainly faster than the migration's intended dwell window. Migrations must therefore be designed to be safe at the git layer, with no cluster-side gating step. The general shape is a multi-phase additive migration where each commit is behavior-neutral within ArgoCD's sync window.

## What happened

The targetSegment migration (replacing `${{ sharedConfigMap('cluster-identity').overlayTarget }}` with `${{ vars.targetSegment }}` in the shared `promote-kustomize-app` `ClusterPromotionTask` — see `ADR-022`) was first drafted as a single commit. The plan included an operator step: before pushing the change, patch the project's `ProjectConfig.promotionPolicies[0].stageSelector` to disable auto-promotion, push the change, wait for ArgoCD to sync, then restore the policy. The intention was a familiar deploy/cutover pattern: pause traffic, change the thing, resume traffic.

Two findings sank the cluster-side approach:

1. **selfHeal reverted the patches within seconds.** The `kargo-config` `Application` is owned by the parent `ApplicationSet` template and reconciled with `selfHeal: true`. Any `kubectl patch` on the cluster-side `ProjectConfig` was reverted within the next reconciliation pass — observed in single-digit seconds. A Promotion takes longer to plan, schedule, and execute than the patch survives. The pause was theoretical; in practice, auto-promotion was never actually paused.
2. **`stageSelector: {}` matches every Stage including `prd`.** The ephemeral cluster's `ProjectConfig` carries an empty selector — semantically "all Stages." A drain-through-`dev`-`stg` recommendation could not contain stale-Freight risk on `prd` because `prd` was selected too. The cluster-side gating shape was unsafe even if `selfHeal` had not reverted it.

The migration was redesigned as a 3-phase additive shape, with no cluster-side step (see `ADR-022` for the resulting shape).

## Root cause

ArgoCD's `selfHeal` is the Kubernetes-level mechanism that makes "Git is the source of truth" load-bearing. It works *against* cluster-side mutations by design — that is the point. Any migration step that depends on a cluster-side mutation surviving long enough to be useful is fighting selfHeal, and selfHeal wins. The reconciliation cadence is configurable but typically faster than any deliberate human-operator-driven step.

The same pattern applies to:

- `kubectl scale` on a `Deployment` reconciled by ArgoCD — reverted.
- `kubectl annotate` on a `Stage` to suppress reconciliation — reverted.
- `kubectl patch` on `RoleBinding` to temporarily restrict access — reverted.
- Manual edits to live `ConfigMap` data that ArgoCD reconciles — reverted (this is the same class as `ADR-023`'s cooperative-write problem, except without an `ignoreDifferences` rule the controller's writes lose on every sync).

In each case, the cluster-side action is undone by selfHeal before its intended effect lands.

## Resolution

Design migrations to be safe at the git layer through a multi-phase additive shape. The 3-phase shape used for the targetSegment migration:

1. **Phase 1 (additive).** Introduce the new path alongside the old one. Both coexist; existing consumers still resolve to the old path; new consumers (and the migration's eventual cutover) can resolve to either. Behavior-neutral within ArgoCD's sync window.
2. **Phase 2 (cutover).** Switch consumers to reference the new path. The old path still exists. Both Freights reference paths that exist on the source — fresh Freight finds the new path, stale Freight (pre-Phase-1 source SHA) still finds the old path.
3. **Phase 3 (cleanup).** Remove the old path. Pre-condition: every Stage has produced at least one post-Phase-2 successful Promotion, so no in-flight Freight references the old path.

Each phase is a single commit. Each commit is independently revertable. No cluster-side step exists at any phase boundary.

The 3-phase shape composes with deterministic Freight pinning (`ADR-003`): every Freight pins to a specific source-manifest commit SHA, so an explicit one-time drain check before Phase 2 — `git merge-base --is-ancestor` against each Freight's `.commits[0].id` — verifies that no in-flight Freight predates Phase 1. This is the only operator-side step in the migration; it is bounded, single-action, and has a deterministic completion criterion.

## How to detect

Symptoms that a migration design is reaching for cluster-side gating:

- A step in the migration plan reads "before pushing X, patch Y in the cluster."
- The plan distinguishes a "pause" period from "resume" — implying cluster-side state will be temporarily different from Git.
- The migration is single-commit and depends on operator coordination during the sync window.

When designing any migration touching ArgoCD-managed resources:

- The git layer is the only durable layer. If a step's safety depends on cluster-side state, redesign the step to encode the safety in the git layer through additive shape.
- Multi-phase additive migrations are the default shape. Each phase is a single commit, behavior-neutral within ArgoCD's sync window. The shape eliminates sync-skew races (CPT-vs-Stage, fresh-Freight against old CPT, stale-Freight against new CPT) that single-commit migrations would expose.
- Drain checks (verifying that all in-flight state references the new path before cleanup) belong at the git layer too — `git merge-base --is-ancestor` against deterministic commit pins (`ADR-003`) is the canonical pattern.

The principle generalizes beyond Kargo: any migration in a GitOps-managed system must be safe at the git layer because the git layer is the only one that survives selfHeal.
