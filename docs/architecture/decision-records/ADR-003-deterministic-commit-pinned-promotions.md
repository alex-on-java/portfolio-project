---
status: accepted
date: 2026-04-04
decision-makers: [alex-on-java]
---

# Use Image+Git Warehouse for Deterministic Commit-Pinned Promotions

## Context and Problem Statement

With an image-only Warehouse subscription, Kargo creates freight containing just an image digest. When the ClusterPromotionTask runs `git-clone` with a branch checkout, it gets whatever HEAD is at that moment. The same freight promoted at different times (or retried) could clone different manifests: the promotion is non-deterministic. This was discovered after the initial pipeline was operational, when the same freight produced different rendered manifests depending on when the promotion step executed.

## Decision Drivers

- Promotion reproducibility: same freight must always produce the same rendered output
- Auditability: each promotion should be traceable to both an image AND a manifest commit
- Works uniformly on both ephemeral and main clusters
- Does not create commit noise on the source branch

## Considered Options

1. Image+git Warehouse with `commitFrom()`
2. Image-only Warehouse with branch checkout
3. Lock-commits (CI writes image refs to PR branch)

## Decision Outcome

**Option 1: Image+git Warehouse with `commitFrom()`.**

A git subscription is added to the Warehouse alongside the image subscription. The Warehouse creates freight containing both an image digest and a git commit SHA. The ClusterPromotionTask uses `commitFrom(vars.gitRepoURL).ID` to check out the exact commit that was part of the freight. An `includePaths` filter on the git subscription prevents unrelated file changes from creating spurious freight.

### Consequences

- **Good**: each freight is an (image-digest, commit-SHA) pair, fully deterministic. Retrying a promotion for the same freight always produces the same output.
- **Good**: `commitFrom()` works uniformly on both main and ephemeral clusters with no special-casing needed.
- **Good**: `includePaths: [gitops/apps/workloads/web-app]` ensures only changes to the relevant manifest path trigger new freight, preventing unrelated commits (docs, CI config) from creating promotion noise.
- **Bad**: `sharedConfigMap()` expressions are not available in Warehouse specs (Warehouse is a static K8s resource, not a Kargo promotion step). The Warehouse git subscription branch must be patched externally via ArgoCD kustomize inline patches at the ApplicationSet level.
- **Neutral**: existing in-flight freight created before the git subscription was added will lack a commit SHA, causing `commitFrom()` to fail. These must be abandoned to let the Warehouse create new freight with both subscriptions.

## Pros and Cons of the Options

### Image+Git Warehouse with `commitFrom()`

See **Decision Outcome** above.

### Image-Only Warehouse with Branch Checkout

- Good: simpler Warehouse configuration with one subscription instead of two.
- Good: no dependency on git commit tracking.
- Bad: non-deterministic. Same freight, different promotion times, different manifests.
- Bad: retry of a failed promotion may produce different output than the original attempt.
- Bad: no audit trail linking a promotion to a specific manifest version.

### Lock-Commits (CI Writes Image Refs to PR Branch)

- Good: explicit approach where the image ref is committed directly in the source.
- Bad: creates commit noise on the PR branch, every image build adds a commit.
- Bad: race condition between CI pushing the lock-commit and other PR pushes.
- Bad: Kargo stage branches already serve this purpose (rendered manifests committed per promotion), so lock-commits duplicate the mechanism.
