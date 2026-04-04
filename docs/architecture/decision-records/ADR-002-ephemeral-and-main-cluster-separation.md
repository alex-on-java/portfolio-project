---
status: accepted
date: 2026-04-04
decision-makers: [alex-on-java]
---

# Use Base/Overlays Pattern for Ephemeral and Main Cluster Separation

## Context and Problem Statement

The PR-based development workflow allocates one ephemeral GKE cluster per PR for isolated testing. A permanent ("main") cluster hosts long-lived environments. The same GitOps manifests (ArgoCD bootstrap, Kargo pipeline, workload definitions) must work on both cluster types, but behavior differs: ephemeral clusters need auto-promotion through all stages including prd, fast polling, and safe teardown without hanging finalizers. The main cluster needs a manual prd promotion gate and standard polling intervals.

## Decision Drivers

- Safe ephemeral cluster teardown: no hanging finalizers blocking deletion
- Auto-promote all stages on ephemeral for fast feedback; manual prd gate on main
- Shared manifest base: changes to pipeline structure apply to both cluster types
- Per-cluster runtime values (branch prefix, target revision) without build-time coupling

## Considered Options

1. Base/overlays pattern with environment-aware patches
2. Separate manifest trees per cluster type
3. Helm values per cluster type

## Decision Outcome

**Option 1: Base/overlays pattern with environment-aware patches.**

Kustomize base defines the full pipeline. The ephemeral overlay patches: strips Application finalizers (addressing both sources: controller auto-add via `preserveResourcesOnDeletion` and template propagation via empty `finalizers: []`), widens auto-promotion to all stages (empty `matchLabels: {}`), and sets 30s polling. The main overlay preserves 180s polling and selective auto-promotion. Every Application in the bootstrap — operators (Kargo, Argo Rollouts), shared resources (analysis-templates), and workloads — is defined as an ArgoCD ApplicationSet with a cluster generator. Each ApplicationSet resolves `{{metadata.annotations.target-revision}}` from the in-cluster ArgoCD secret, which is patched to the PR branch during activation. This is not optional: the `gitops/` directory exists only on PR branches, not on `main`, so any static `targetRevision: HEAD` reference resolves to a tree that lacks the entire GitOps manifest structure. Kargo ClusterPromotionTask reads `sharedConfigMap('cluster-identity')` for dynamic branch targeting.

### Consequences

- **Good**: ~90% manifest sharing between cluster types. Only the overlay patches and `kargo-config` ApplicationSet path differ.
- **Good**: finalizer stripping addresses both independent sources (Application controller auto-add AND ApplicationSet template propagation), a subtlety documented in ArgoCD GitHub issues but not the main docs.
- **Good**: wave ordering (-100, 0, 100, 200, 300) resolves CRD dependency timing naturally. `kargo-config` at wave 300 with `SkipDryRunOnMissingResource` and infinite retry handles the race where Kargo CRDs from wave 0 are not ready yet.
- **Good**: `sharedConfigMap('cluster-identity')` in ClusterPromotionTask makes promotion target branches dynamic without hardcoding cluster identity.
- **Bad**: overlay patches use JSON patch (`op: add/replace`) which is more fragile than strategic merge patches. A schema change in a patched resource requires updating the patch path.
- **Neutral**: the main overlay is currently a placeholder (`resources: []`). The pattern is validated on ephemeral but not yet exercised for main.

## Pros and Cons of the Options

### Base/Overlays Pattern with Environment-Aware Patches

See **Decision Outcome** above.

### Separate Manifest Trees per Cluster Type

- Good: maximum flexibility, each tree can diverge freely.
- Bad: duplicates ~90% of content, changes must be applied twice.
- Bad: drift between trees is inevitable and hard to detect.
- Bad: violates DRY at the 10x scale.

### Helm Values per Cluster Type

- Good: single chart, conditional logic via values.
- Bad: mixing Kustomize (for workload overlays) with Helm (for cluster variance) adds conceptual overhead.
- Bad: Helm conditionals are harder to review than Kustomize patches. `{{- if .Values.ephemeral }}` blocks obscure the final manifest.
- Bad: Kustomize components and Helm templating do not compose cleanly.
