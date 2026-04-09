---
name: kargo-troubleshooting
description: |
  Diagnose Kargo promotion pipeline issues.
  Use when freight is not detected, stages are not promoting,
  promotions are failing, or stage branches are not being updated.
user-invocable: false
---

## Architecture Context

Kargo polls for new images and git commits, packages them as Freight, then drives promotions
through stages by running a ClusterPromotionTask: it commits rendered manifests to stage branches
and triggers ArgoCD syncs. On ephemeral clusters, all three stages (dev, stg, prd) auto-promote.

## Diagnostic Approach

Work down the pipeline, starting from the earliest broken point:

**1. Is the warehouse detecting new images?**
Check warehouse status for the last detected image. Compare the image tag (commit SHA format)
against what CI pushed. Polling interval is 30s on ephemeral clusters — detection should happen
within a minute of CI completing. If no image is detected, check whether the image subscription
config points to the correct registry, and verify the image exists in GHCR.

**2. Is Freight being created?**
Freight bundles an image digest + a git commit from the source branch. Kargo requires both
subscriptions to be satisfied before creating Freight. If the warehouse detects the image but
no Freight appears, check whether the git subscription is also polling the correct branch.

**3. Is the stage promoting?**
Check stage status in the `portfolio-project` namespace. A stage not promoting means one of:
- No freight available (upstream stage has not verified yet, for downstream stages)
- Auto-promotion not enabled (check ProjectConfig and stage labels — ephemeral overlay patches
  auto-promote to all stages)
- A promotion is already in `Running` phase for this stage (check `kubectl get promotions`)

**4. Is the promotion failing?**
Inspect the promotion resource YAML for the failed step. The ClusterPromotionTask runs:
`git-clone` → `kustomize-set-image` → `kustomize-build` → `git-push` → `argocd-update`

Common failure points:
- `git-push`: GitHub App credentials expired or misconfigured (Secret in `kargo-shared-resources`)
- `kustomize-build`: overlay path wrong or kustomization file missing on the source branch
- `argocd-update`: ArgoCD app not found or the app lacks `kargo.akuity.io/authorized-stage`
  annotation

**5. Are stage branches updated?**
After a successful promotion, a new commit appears on `stage/{branch-prefix}/{app}-{env}`.
Each stage branch contains a single pre-rendered manifest file (not a kustomize tree).
If the branch exists but the latest commit predates the expected freight, the promotion may
have succeeded for an older freight — confirm the current promotion targets the right freight ID.

**6. Is verification blocking downstream?**
Dev and stg stages run HTTP health check verification after promotion. A stage stuck in
`Verified: False` blocks downstream stages from receiving freight. Check the analysis run
in the `portfolio-project` namespace — the health check Job's logs show whether the curl
succeeded or timed out.

## Escape

Kargo controller logs (`-n kargo`, `kargo-controller`) contain promotion step details and
polling errors. Management-controller logs cover ProjectConfig and auto-promotion policy issues.
The `kargo.akuity.io/argocd-context` annotation on Stage resources identifies the linked
ArgoCD applications.
