# LL-0004: Kustomize set-image Silently Creates Phantom Entries

**Summary**: The `kustomize-set-image` step's `name` field matches against container image references in Kubernetes manifests (e.g., `ghcr.io/owner/app` in a Rollout's container spec), NOT against `images[].name` in `kustomization.yaml`. A mismatch creates a phantom image entry silently — no error is raised.

## What happened

After a Kargo promotion, the dev pod was stuck in `InvalidImageName` (the placeholder digest was never replaced), while stg and prd stages were stuck at `NoFreight`. The promotion step reported success.

## Root cause

The ClusterPromotionTask's `kustomize-set-image` step used `name: web-app` (the appName variable), but the overlay `kustomization.yaml` declares images with `name: ghcr.io/alex-on-java/web-app`, matching the container image reference in the Rollout manifest. The mismatch caused kustomize to:

1. Create a phantom image entry for `web-app` (matching no container)
2. Leave the real `ghcr.io/alex-on-java/web-app` entry untouched at `newTag: "sha256:placeholder"`

The promotion step reported success because kustomize-set-image does not validate that the name matched an actual container.

## Resolution

Changed the ClusterPromotionTask from `name: ${{ vars.appName }}` to `name: ${{ vars.imageRepo }}`, matching the full image reference used in both the Rollout container spec and the overlay kustomization.

## How to detect

After a promotion, check the rendered output for duplicate image entries or unchanged placeholder digests. `kustomize build` on the overlay and grep for `sha256:placeholder`.
