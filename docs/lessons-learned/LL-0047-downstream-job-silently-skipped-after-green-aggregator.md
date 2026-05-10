# LL-0047: Downstream Job Silently Skipped After Aggregator Tolerates an Upstream Skip

**Summary**: A safe-merge-gate aggregator (such as `re-actors/alls-green`) does not isolate downstream jobs from its ancestors. Any job whose only `needs:` is the aggregator still inherits every skip that `allowed-skips` tolerated. The auto-prepended `success() &&` reaches past the aggregator into those ancestors during evaluation. GitHub therefore silently skips a downstream job on every PR where `allowed-skips` covered a real upstream skip. This break appears only as a missing side effect, never as a red check.

## What Happened

`dispatch-pr-push` listed only the safe-merge-gate aggregator `build-status` in its `needs:`. The job fires the cross-repo `pr-push` `repository_dispatch` to `portfolio-project-cluster-pool` and reports the "Ephemeral Cluster" commit status. On PRs with an empty affected publish-image matrix (docs-only or infra-only changes):

1. `Detect affected projects` returned `[]`.
2. The matrix-empty `if:` skipped `Build & publish image`.
3. `build-status` reported `success` because its `re-actors/alls-green` step declares `allowed-skips: build`.
4. That implicit `success()` walk reached the skipped `Build` and short-circuited the gate of `dispatch-pr-push` to `false`.

No `pr-push` event reached `portfolio-project-cluster-pool`, the cluster-pool repository created no ephemeral cluster, and the "Ephemeral Cluster" commit status never appeared on the head SHA. Every observable surface read as "not yet dispatched."

## Root Cause

LL-0046 captures the underlying behavior. GitHub Actions auto-prepends `success() &&` to a job-level `if:` lacking a status-check function. That implicit `success()` walks the transitive `needs:` graph. For a job downstream of an aggregator, the walk passes through the aggregator and reaches every job the aggregator tolerated skipping. The `allowed-skips` of the aggregator does not protect downstream jobs; it only protects the verdict the aggregator itself publishes.

The aggregator slot and the downstream-of-aggregator slot put `always()` to parallel but distinct uses. For the aggregator slot ([LL-0038](LL-0038-required-check-green-despite-failed-upstream-job.md), `build-status`), `if: always()` lets the aggregator run after an upstream skip and publish a verdict. Without that token, the merge gate disappears silently. By contrast, the downstream-of-aggregator slot (this LL, `dispatch-pr-push`) carries `if: always() && needs.<aggregator>.result == 'success'`. This guard gates the job on the verdict of the aggregator alone, not on the transitive `needs:` graph the aggregator already adjudicated. Removing that token lets the side effect disappear silently.

## Resolution

Every job that depends on the verdict of the safe-merge-gate aggregator carries an explicit `if:` containing both a status-check function and a result check:

```yaml
some-downstream-job:
  needs: build-status
  if: always() && needs.build-status.result == 'success'
```

The bare `if:` form (without `${{ }}`) matches the convention `build-status` itself uses in `.github/workflows/ci-pr.yml`. `actionlint` and `zizmor` accept both forms.

## How to Detect

Diagnose this on PRs where some upstream reaches the `skipped` conclusion through a legitimate matrix-empty path. A downstream job then reaches `skipped` with no error despite the aggregator reporting `success`. Its expected side effect (a dispatched event, a deployment, a status post) goes missing on the head SHA. Reading the workflow file shows the `if:` of the downstream job references only `needs.<aggregator>.result == 'success'` without a status-check function, or has no `if:` at all.
