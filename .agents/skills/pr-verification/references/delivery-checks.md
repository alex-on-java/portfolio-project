# Delivery Checks — Kargo

Kargo drives the promotion pipeline: it detects new images, creates Freight,
and promotes through stages by committing to stage branches and triggering ArgoCD syncs.

## What Should Be Green

**Warehouse**: status should show the latest detected image. The image tag (commit SHA format)
should match the commit SHA from the CI run.

**Stages** (`-n portfolio-project`): all three stages (dev, stg, prd) should show:
- Ready: True
- Healthy: True
- Verified: True

Note: dev and stg run an HTTP health check for verification; prd does not (on ephemeral clusters,
prd auto-promotes but skips verification).

**Promotions**: the promotion for each stage should be in `Succeeded` phase. A promotion still
in `Running` phase is healthy — it's in progress, not stuck. Only investigate if phase is `Failed`
or no promotion exists for the latest freight.

**Freight consistency**: all three stages must reference the same freight ID. The freight's image
digest must match what the CI run pushed.

## Stage Branches

Kargo creates and manages stage branches: `stage/{branch-prefix}/{app}-{env}`.
Each branch contains a single pre-rendered manifest file (not a kustomize overlay tree).
The latest commit on each branch should be authored by Kargo, with a message like:
`Promote {branch-prefix}/{stage}: {app} {image-tag}`

If a stage branch is absent or its latest commit predates the expected image, the promotion
has not run yet or has not reached that stage.

## Promotion Cascade

dev promotes first (directly from warehouse), then stg promotes (from dev), then prd (from stg).
On ephemeral clusters all three auto-promote. On main clusters, prd requires manual promotion.
A stalled middle stage blocks all downstream stages.
