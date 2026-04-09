---
name: pr-verification
description: |
  Verify end-to-end deployment health.
  Triggers when asked to verify a deployment, check if changes are live, confirm the pipeline completed, or validate the PR environment. Also must be loaded after pushing to a feature branch.
user-invocable: false
---

The deployment pipeline runs in sequential layers. Check each in order — stop and report
if a layer fails, since downstream checks are meaningless without the upstream layer being green.

## Layer 1 — CI

Use `gh run list` to find the latest run for this PR's branch. Both jobs must succeed:
- `build` — Docker image built and pushed to GHCR
- `dispatch-pr-push` — cluster-pool notified

If either job failed, report which one and stop. Do not proceed to cluster checks.

## Layer 2 — Cluster

Check the `Ephemeral Cluster` commit status using:
`gh api repos/alex-on-java/portfolio-project/commits/$(git rev-parse HEAD)/status --jq '.statuses[] | select(.context == "Ephemeral Cluster") | .description'`

If the status won't become "Cluster provisioned" within a minute:
- Use `/loop 15m` to wait for cluster to be provisioned from scratch. Use `date` to detect, how many minutes actually passed.
- **Always cancel the loop cron after these 15 minutes.** A forgotten loop wakes up periodically and reports stale status while you are already working on a fix.
- If cluster is not provisioned, invoke `cluster-troubleshooting`.

## Layer 3 — Platform (ArgoCD)

Read `references/platform-checks.md` for what to check and what green looks like.

If any ArgoCD application is degraded → invoke `argocd-troubleshooting`.

## Layer 4 — Delivery (Kargo)

Read `references/delivery-checks.md` for what to check and what green looks like.

If the promotion pipeline is stuck or stages are not verified → invoke `kargo-troubleshooting`.

## Layer 5 — Application

Read `references/app-checks.md` for what to check and what green looks like.

If any Rollout is degraded or pods are failing → invoke `app-troubleshooting`.

## Final Consistency Check

When all layers are individually green, confirm end-to-end consistency:
- The freight ID reported by all Kargo stages must be the same
- The image digest in running pods must match the freight's image digest
- The git commit recorded in the freight must be from the PR branch

All green and consistent → report success with a brief summary of what was verified.
