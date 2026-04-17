---
status: accepted
date: 2026-04-16
decision-makers: [alex-on-java]
---

# Separate Policy Locations by Enforcement Plane

## Context and Problem Statement

The project has two distinct policy enforcement mechanisms: conftest (Rego policies for raw source file validation) and Kyverno (ClusterPolicy CRDs for admission control). Both are "policies," but they operate at different points in the deployment lifecycle — conftest runs in the developer workflow (pre-commit/CI), Kyverno runs in the cluster (admission webhooks).

Where should Kyverno ClusterPolicy manifests live in the repository? The existing `policies/conftest/` directory is the obvious candidate, but ClusterPolicy files are Kubernetes manifests deployed by ArgoCD — they belong in the GitOps tree.

## Decision Drivers

- The convention `gitops/ = deployed by ArgoCD` is established and load-bearing — breaking it creates ambiguity about what ArgoCD manages
- Kustomize's `LoadRestrictionsRootOnly` blocks cross-tree references, but ArgoCD Applications don't need them — they point directly to any repo path
- Kyverno policies will have overlays (audit → enforce) once the operator is deployed — the Kustomize base/overlay pattern requires a dedicated directory tree
- The `policies/` directory at repo root already communicates "developer-workflow tooling" — adding cluster-deployed manifests there contradicts that signal

## Considered Options

1. `gitops/cluster-policies/kyverno/base/` — new directory under the GitOps tree
2. `policies/kyverno/` — alongside `policies/conftest/`
3. `gitops/policies/kyverno/base/` — under GitOps but named `policies`

## Decision Outcome

**Option 1: `gitops/cluster-policies/kyverno/base/`**

Two enforcement planes get two locations. The naming makes the distinction explicit:

- `policies/` (repo root) — developer workflow enforcement. Conftest, pre-commit hooks, CI checks. Never deployed to a cluster.
- `gitops/cluster-policies/` — cluster admission enforcement. Kyverno CRDs, deployed by ArgoCD. Follows the Kustomize base/overlay pattern for environment-specific patches.

### Consequences

- **Good**: preserves the `gitops/ = deployed by ArgoCD` convention — a ClusterPolicy under `gitops/` clearly signals it will reach the cluster.
- **Good**: `cluster-policies` naming distinguishes from the root `policies/` directory without ambiguity.
- **Good**: the Kustomize base/overlay structure is ready for overlays (audit → enforce) when the Kyverno operator is deployed.
- **Bad**: a new top-level directory under `gitops/` — adds one more entry to navigate.
- **Neutral**: the validation engine reads `base/` directly; overlays are a future concern that doesn't affect the current implementation.

## Pros and Cons of the Options

### `policies/kyverno/` at repo root

- Good: co-locates all policies in one directory.
- Bad: breaks the `gitops/ = deployed` convention — ClusterPolicy manifests under `policies/` won't be recognized as ArgoCD-managed.
- Bad: Kustomize base/overlay pattern feels unnatural under a `policies/` tree that currently holds flat Rego files.

### `gitops/policies/kyverno/base/`

- Good: under the GitOps tree, so deployment intent is clear.
- Bad: `gitops/policies/` is ambiguous — a reader might confuse it with the root `policies/` directory or wonder why policies exist in two places with similar names.
