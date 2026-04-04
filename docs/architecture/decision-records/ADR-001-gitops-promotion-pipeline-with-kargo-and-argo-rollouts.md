---
status: accepted
date: 2026-04-04
decision-makers: [alex-on-java]
---

# Use Kargo and Argo Rollouts for the GitOps Promotion Pipeline

## Context and Problem Statement

The portfolio project needs a progressive delivery pipeline built from scratch. The pipeline must support multi-environment promotion (dev, stg, prd), automated and policy-gated promotion, blue-green deployments, and operation across both ephemeral and permanent clusters. ArgoCD is already established as the GitOps engine for managing Kubernetes workloads.

## Decision Drivers

- Auditable, policy-driven promotion gates: dev auto-promotes, prd requires manual approval
- Cryptographic immutability: image digests over mutable tags
- DRY manifests: adding a new application should not require duplicating pipeline structure
- Operators managed by ArgoCD (not Terraform `helm_release`): GitOps all the way down
- No lock-commits: CI writing image refs to a PR branch creates commit noise and race conditions

## Considered Options

1. Kargo + Argo Rollouts + Kustomize components
2. Flux + Flagger
3. ArgoCD Image Updater + manual promotion

## Decision Outcome

**Option 1: Kargo + Argo Rollouts + Kustomize components.**

Kargo orchestrates promotion through stages, Argo Rollouts provides blue-green/canary deployment strategy, and the Kustomize component pattern provides DRY pipeline templates. ArgoCD ApplicationSets with a cluster generator handle multi-cluster targeting. A Warehouse subscribes to the image registry, and stages chain linearly: dev (direct from warehouse), stg (from dev), prd (from stg).

### Consequences

- **Good**: the Kustomize component pattern enables reusable pipeline templates. A base defines Warehouse + 3 Stages with PLACEHOLDERs, an `app-core` component injects per-app values via ConfigMap replacements, and per-app directories provide only a ConfigMap and compose base + components. Adding a new application is one directory, zero duplication.
- **Good**: Kargo stage branches hold rendered manifests per environment, avoiding lock-commits on the source branch and eliminating race conditions between CI and promotion.
- **Good**: digests (not tags) in image references provide cryptographic immutability: the exact image bytes are pinned.
- **Good**: ArgoCD ApplicationSets with the cluster generator pattern scale to multiple clusters without duplicating YAML. Per-cluster values (like `targetRevision`) come from cluster annotations at runtime, not build-time static values.
- **Bad**: Kargo is a newer tool with a smaller community than Flux. Fewer Stack Overflow answers, more reliance on Akuity documentation and source code.
- **Bad**: three layers of indirection (Kargo promotes, ArgoCD syncs, Argo Rollouts executes) increase debugging complexity.
- **Neutral**: wave ordering in ArgoCD bootstrap (-100 namespaces, -50 cert-manager, 0 operators, 100 analysis-templates, 200 workloads, 300 kargo-config) is required to handle CRD dependency timing.

## Pros and Cons of the Options

### Kargo + Argo Rollouts + Kustomize Components

See **Decision Outcome** above.

### Flux + Flagger

- Good: Flux is mature, well-documented, and CNCF graduated.
- Good: Flagger supports canary, blue-green, and A/B testing.
- Bad: Flux ImageUpdateAutomation writes lock-commits to the source branch, creating commit noise and potential race conditions.
- Bad: no native concept of "promotion stages" with policy gates. Would require custom scripting to approximate Kargo's stage chaining.
- Bad: would require replacing ArgoCD, which is already established as the GitOps engine.

### ArgoCD Image Updater + Manual Promotion

- Good: stays within the ArgoCD ecosystem, minimal new tooling.
- Good: simple mental model where ArgoCD handles everything.
- Bad: no automated cross-environment promotion. Manual PR or script per environment.
- Bad: Image Updater is limited to tag-based detection, no digest-native workflow.
- Bad: scales poorly at 10x applications, where manual promotion becomes a bottleneck.
