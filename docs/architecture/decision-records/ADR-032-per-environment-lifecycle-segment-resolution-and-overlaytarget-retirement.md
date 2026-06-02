---
status: accepted
date: 2026-06-01
decision-makers: [alex-on-java]
---

# Per-Environment Lifecycle Segment Resolution and `overlayTarget` Retirement

## Context and Problem

Overlay selection in this repository was once encoded along two cluster-sourced axes held in the `cluster-identity` ConfigMap: `overlayTarget` (a deploy-target dimension with values `cloud` and a latent, never-built `local`) and `clusterLifecycle` (`ephemeral` or `main`). The two axes were physically nested only in one place — `convergence-checker`, whose `promote-platform-app` task built `overlays/${{ overlayTarget }}/${{ clusterLifecycle }}` and resolved to `overlays/cloud/ephemeral`.

That two-axis shape was deliberate when it was introduced. Commit `54147a6` used `overlayTarget/clusterLifecycle` as a fail-loud guard for `convergence-checker`, and infra commit `d8b8252` added `clusterLifecycle` as a non-null cluster lifecycle invariant. The design was sound for the system that existed then.

The system has since changed. ADR-022 moved `web-app` to a workload-scoped `targetSegment` and left `convergence-checker` as the only remaining consumer of `overlayTarget`. That produced two divergent overlay conventions — `overlays/any/<env>` for the migrated workload and `overlays/cloud/ephemeral` for the platform workload — and left `overlayTarget` as a single-valued residual axis whose `cloud` level asserts a choice that never varies and whose `local` value has no directory, conditional, or manifest behind it.

The migrated `targetSegment` model also had a narrower limitation. It expressed exactly one segment for every environment of a workload. It could not say that `dev` and `stg` are common while `prd` is lifecycle-sensitive without hard-coding that rule for all workloads at once.

## Decision Drivers

- Overlay selection should be honest: a dimension that does not vary should not occupy a path level.
- Whether and how a workload subdivides by lifecycle is a property of the workload, so the choice belongs in the workload's own configuration rather than in a cluster-wide selector.
- A workload should differentiate per environment without being forced into a full lifecycle × environment folder cross-product when only some environments differ.
- Knowledge of which lifecycles currently exist must stay centralized in cluster identity and infra, not be copied into workload directories or app vars.
- Dynamic Kargo expression evaluation belongs in promotion step config, where the functions are evaluated, not in ordinary Kubernetes resource fields where it would persist as a literal (LL-0009).

## Decision

`overlayTarget` is retired. It was a single-valued cluster-wide deploy-target selector with no current `local` target, so it asserted a dimension that never varied. `clusterLifecycle` is kept: it is real cluster identity, owned by infra, and remains the value that distinguishes an ephemeral cluster from a main one.

`convergence-checker` collapses from `overlays/cloud/ephemeral` to `overlays/ephemeral`. Its `promote-platform-app` task no longer reads cluster identity for path construction; it takes a required `targetSegment` var, and the `convergence-checker` Stage supplies the literal `targetSegment: ephemeral`.

For workloads, a workload owns its default segment through `targetSegment` and declares which environments are lifecycle-sensitive through a second workload-owned field, `lifecycleSegmentEnvs`. The field is a comma-separated set of environment names whose segment resolves from `cluster-identity.clusterLifecycle` instead of from the default `targetSegment`. Its value is `none`, a single environment, or a comma-separated combination without spaces such as `dev,stg` or `stg,prd`. The workload declares environment sensitivity, not lifecycle values; workload app vars do not contain `ephemeral`, `main`, or `sharedConfigMap(...)`.

The shared `promote-kustomize-app` task resolves the segment inside its promotion step `config.path` values with a single nested-ternary expression: when `lifecycleSegmentEnvs` is still the `PLACEHOLDER` sentinel the segment resolves to `PLACEHOLDER`; otherwise, for an environment in the declared set the segment is `sharedConfigMap('cluster-identity').clusterLifecycle`, and for any other environment it is `vars.targetSegment`. The `PLACEHOLDER` sentinel is preserved on purpose, and it fails loudly at one of two layers. Each workload Stage base sets `lifecycleSegmentEnvs: PLACEHOLDER`, and the `app-core` Kustomize replacement overwrites it from the workload's `data.lifecycleSegmentEnvs`. If `app-vars.yaml` omits that key, the replacement source is missing and the Kustomize render fails at build time, before any manifest is produced. If the sentinel instead survives unreplaced, every environment resolves to `overlays/PLACEHOLDER/<env>` and the promotion fails at the filesystem layer. Neither path silently falls back to `targetSegment`.

For this change, `web-app` uses `targetSegment: any` and `lifecycleSegmentEnvs: prd`. Its `dev` and `stg` stay under `overlays/any`, and `prd` resolves to `overlays/ephemeral/prd` or `overlays/main/prd` from the current cluster lifecycle.

## Options Considered

- Remove `clusterLifecycle` entirely along with `overlayTarget`.
- Hard-code `vars.env == 'prd'` lifecycle sensitivity in the shared workload task.
- Add separate `{dev,stg,prd}SegmentSource` fields, one per environment.
- Put the `clusterLifecycle` lookup into a `targetSegment` Stage var, Warehouse spec, or `app-vars.yaml` instead of the promotion step config.
- Make every `web-app` environment lifecycle-specific now.
- Declare which environments are lifecycle-sensitive through one workload-owned environment set resolved in promotion step config.

## Option Analysis

Removing `clusterLifecycle` was rejected because lifecycle remains a real cluster identity value. Target architecture shapes where lifecycle affects resource identity still need it, and infra re-encodes the same lifecycle into the ArgoCD cluster Secret surfaces and bootstrap path selection. Only `overlayTarget` is fake; `clusterLifecycle` is load-bearing.

Hard-coding `vars.env == 'prd'` was rejected because it serves only the current `web-app` need. It cannot express a lifecycle-specific `stg`, a lifecycle-specific `dev,stg`, or a fully lifecycle-specific workload without further global edits.

Per-environment `*SegmentSource` fields were rejected as verbose and poorly scaling. One environment set captures the same decision more compactly and reads as a single workload statement.

Placing the `clusterLifecycle` lookup in a Stage var, Warehouse spec, or `app-vars.yaml` was rejected because Kargo expressions in ordinary CRD specs can persist as literal text in live resources (LL-0009). Lifecycle lookup belongs inside promotion step config, where the expression is evaluated during promotion.

Making every `web-app` environment lifecycle-specific was rejected because the current task only needs `prd`. `dev` and `stg` should stay common until a real target reason splits them.

The chosen environment-set option keeps lifecycle knowledge centralized in cluster identity, keeps the workload's declaration local and minimal, and reuses the existing `PLACEHOLDER` fail-loud convention from ADR-022.

## Consequences

- Good: overlay selection no longer carries a phantom `cloud` level, and both promotion tasks share one single-segment convention.
- Good: a workload differentiates per environment by editing its own `app-vars.yaml`, without a six-folder lifecycle × environment cross-product and without touching shared Stage bases.
- Good: lifecycle knowledge stays in `cluster-identity`; target-agnostic environments remain zero-touch as the system grows.
- Good: a missing or unsubstituted `lifecycleSegmentEnvs` fails loudly — at Kustomize render time when the `app-vars.yaml` key is absent, or at `overlays/PLACEHOLDER/<env>` when the sentinel survives unreplaced — rather than silently resolving to the default segment.
- Bad: the segment path is now a nested-ternary expression repeated across four promotion step path consumers, and all four must stay identical. The expression must be quoted in YAML because its `: ` would otherwise break parsing before Kargo evaluates it.
- Neutral: `web-app overlays/ephemeral/prd` and `overlays/main/prd` are seeded from the former `overlays/any/prd` and are byte-identical for now. The real lifecycle-specific `prd` difference is expected in a later task.

## Postponed Effort

- Introducing the real source-backed `web-app prd` manifest difference between `overlays/ephemeral/prd` and `overlays/main/prd`.
- Policy enforcement for valid `lifecycleSegmentEnvs` values and overlay topology.
- Replacing the repeated segment-resolution expression. The same nested-ternary `path` expression is duplicated across all four `promote-kustomize-app` path consumers, and every copy must stay identical. This section is to be rewritten once we come up with a better solution.

## More Information

This decision was verified only by static source-tree checks: Kustomize renders of the affected overlays, content and path searches confirming `overlayTarget` is gone from active app manifests while `clusterLifecycle`, `targetSegment`, and `lifecycleSegmentEnvs` remain where intended, and a confirmation that the same quoted segment expression appears in exactly the four `promote-kustomize-app` path consumers.

Static renders prove source-tree consistency only; they do not prove Kargo promotion behavior. The exact expression shape — a quoted promotion-step path with a nested ternary, `split(...)`, `in`, and `sharedConfigMap('cluster-identity').clusterLifecycle` — was verified live on the pinned Kargo chart against an ephemeral cluster: all `promote-kustomize-app` and `promote-platform-app` promotions succeeded, with `web-app dev` and `web-app stg` resolving to `overlays/any/{dev,stg}`, `web-app prd` resolving to `overlays/ephemeral/prd` via `clusterLifecycle`, and `convergence-checker` to `overlays/ephemeral`, with no expression-evaluation errors and the convergence gate reporting all resources healthy. Two acceptance checks remain deferred. `cluster-identity` carrying no `overlayTarget` is observable on the next ephemeral bootstrap: the verification cluster predated the infra change that retires the key, so the key was still present (but inert, with no consumer) at verification time. Main-cluster proof for `overlays/main/prd` remains deferred because main is operationally unexercised; it must not be claimed until a main-cluster or controlled Kargo promotion shows the resolution.

## Related Records

- ADR-022 — the workload-scoped `targetSegment` and `PLACEHOLDER` sentinel this decision extends from one segment per workload to per-environment lifecycle sensitivity.
- ADR-002 — the ephemeral and main cluster separation that `clusterLifecycle` continues to encode.
- LL-0009 — why dynamic Kargo expressions stay in promotion step config rather than ordinary resource fields.
- LL-0035 — why Kargo overlay migrations must be safe at the git layer.
- LL-0026 — why ArgoCD `Synced+Healthy` is counted only after the corresponding stage branch is populated.
