# LL-0068: Skipped Job Outputs Evaluate as Empty String, Not as Absent

**Summary**: When a GitHub Actions job reaches the `skipped` conclusion, its outputs are not null or absent in downstream expressions. They evaluate as empty string. An `if:` expression that compares an output against a specific value, such as `!= '[]'`, silently admits the skipped case because `'' != '[]'` is `true`. A guard intended to run a job only when its upstream produced a non-empty result instead runs when the upstream never ran at all.

## What Happened

The `cleanup-image-artifacts` job in `.github/workflows/ci-pr.yml` carried this guard:

```yaml
if: always() && needs.changes.outputs.publish_matrix != '[]'
```

The intent was to run cleanup only when at least one image had been built. When `changes` ran normally and emitted `[]` (no affected publish projects), the guard correctly evaluated to `false` and cleanup was skipped. When `changes` itself was skipped because one of its `needs:` jobs failed, `needs.changes.outputs.publish_matrix` evaluated to empty string. The expression `'' != '[]'` is `true`, so cleanup proceeded at exactly the moment its producer had never run. The guard admitted the opposite of its intended boundary.

## Root Cause

GitHub Actions represents a skipped job's outputs as empty string in the expression context. The outputs are not null, not absent, and not a sentinel distinct from `''`. Any expression that compares an output against a specific value silently treats the skipped case as a mismatch. The value `''` does not equal `'[]'`, `'false'`, `'none'`, or most other guard targets an author might choose, so the mismatch evaluates to `true` and the downstream job runs.

This is distinct from [LL-0038](LL-0038-required-check-green-despite-failed-upstream-job.md), which covers the merge-gate surface where GitHub's required-check evaluator treats `skipped` as `success`. This entry covers the expression-evaluation surface inside a workflow's `if:` field. The two failure modes operate on different layers but produce the same class of result: a guard that admits a state the author intended to exclude.

## Resolution

The `cleanup-image-artifacts` job was redesigned to avoid reading outputs from a potentially-skipped job. In the revised workflow (commit `2da7ab3`), cleanup anchors to `build-status` with `if: always()` and collects every artifact for the run regardless of what was built. The job no longer gates on the publish matrix, so the skipped-output problem does not arise.

For workflows that must read outputs from an upstream job, the safe pattern is to check the producer's conclusion before comparing its output:

```yaml
if: needs.changes.result == 'success' && needs.changes.outputs.publish_matrix != '[]'
```

The `result == 'success'` check excludes the skipped case before the output comparison runs. A skipped `changes` job yields `needs.changes.result == 'skipped'`, so the first operand is `false` and short-circuit evaluation never reaches the output comparison.

## How to Detect

Search the workflow for `needs.<job>.outputs.<name>` comparisons inside job-level `if:` expressions. For each reference, trace whether the upstream job can reach `skipped`: it can if it has its own `needs:` chain, an `if:` condition, or any dependency that can fail or skip. The symptom is a downstream job running (or being blocked) on PRs where the upstream never executed. The Actions tab shows the upstream job as `skipped` while the downstream job ran, even though the guard appeared to restrict execution to the non-empty output case.

## Adoption Rule

Before comparing a job output against any value, guard with `needs.<job>.result == 'success'`. Treat every output from a potentially-skipped job as unreliable until the result check confirms the producer ran. The structural check is: for each `needs.<job>.outputs.<name>` reference in an `if:` field, confirm the `if:` also contains `needs.<job>.result == 'success'` as a short-circuit guard before the output comparison.
