# LL-0038: GitHub Required-Status-Check Evaluation Treats `skipped` As `success`

## Summary

The required-status-check evaluator in GitHub branch protection treats a `skipped` job conclusion as equivalent to `success`. A job that does not run because one of its `needs:` failed reports as `skipped`, which silently passes the merge gate. This is the canonical silent-broken-merge-gate class. Every cascade-skip path produces a green required check unless the aggregator job satisfies two coupled constraints. First, it lists every upstream in its `needs:` set. Second, it narrows `allowed-skips` to exactly the jobs whose skip is legitimate.

[ADR-026](../architecture/decision-records/ADR-026-image-build-ci-strategy.md) captures the chosen aggregator for this project (`re-actors/alls-green`) and its `needs:` set. This LL captures the underlying GitHub semantic that forces that choice, and the load-bearing properties any future aggregator must preserve.

## Why a Naive Aggregator Is Unsafe

The cascade-skip path is concrete. Take the current `ci-pr.yml`: `changes` computes the affected matrix; `build` runs only when the matrix is non-empty, with `needs: changes`. Suppose `changes` fails (the `nx show projects` command errors, or `jq empty` rejects malformed JSON). The cascade is:

1. `changes` reports `failure`.
2. `build` does not run; its conclusion is `skipped` (not `failure`) because its `needs:` was not satisfied.
3. A naive aggregator with `if: always()` and a `needs:` set of just `[build]` sees one job, conclusion `skipped`, and reports `success` to the PR check surface.
4. Branch protection accepts the green required check. The PR is mergeable despite a broken upstream.

This shape generalises to `lint`, `test`, and `permanent-history-artefacts`: any of them failing without being listed in the aggregator `needs:` produces a green merge gate. The skip is invisible to an aggregator that did not subscribe to it.

## The Five Load-Bearing Properties of a Safe Aggregator

A required-check aggregator in this repository must satisfy all five. Removing any one re-opens the silent-skip path.

- **Every upstream job appears in `needs:`.** Not just the "interesting" ones. `changes`, `lint`, `test`, `permanent-history-artefacts`, and `build` are all listed in `build-status: needs:` for exactly this reason. Cascade-skips then surface as missing-success entries in the `toJSON(needs)` payload of the aggregator rather than as clean skips.
- **`allowed-skips` is narrowed to legitimately-skippable jobs.** The current value is `allowed-skips: build`, because `build` legitimately skips when the affected matrix is empty (no app changed). Any other value, broader or covering a non-skippable job, launders a real failure as a permitted skip.
- **`if: always()` on the aggregator.** Without it, the aggregator itself inherits the cascade-skip and never runs, leaving the required check missing. A missing required check is *not* a green check, but it is also not a red one; the PR sits in an indeterminate state that some configurations resolve permissively.
- **`permissions: {}` declared explicitly.** `re-actors/alls-green` requires no permissions. An empty declaration documents that fact and bounds the blast radius of any compromise of the action surface to "wrong check status reported," with no token issuance possible.
- **Step-scope failure aggregation.** `re-actors/alls-green` evaluates `contains(needs.*.result, 'failure')` at *step* scope internally. Lifting that expression to *job* scope hits [actions/runner #1540](https://github.com/actions/runner/issues/1540): `needs.*.result` is broken for job-level conditionals. `alls-green` insulates callers from this. A future hand-rolled replacement must keep the expression at step scope.

## Footnote on actions/runner #1540

GitHub has had a job-scope evaluation bug open since 2021 for `contains(needs.*.result, 'failure')`, and the issue is not on a near-term fix path. Practical implication for this repository: any future inline aggregator that does not use `re-actors/alls-green` must compute the verdict inside a step `run:` or `if:`, never in the job-level `if:`. The `alls-green` action does this correctly. A hand-rolled replacement that copies the expression up one level produces a green aggregator under conditions where the step-scope version would correctly report failure.

## Adoption Rule

For any required-check aggregator in this repository or its sibling repos (`portfolio-project-infra`, `portfolio-project-cluster-pool`):

- Use `re-actors/alls-green` pinned to a commit SHA per [CQP-003](../code-quality-policies/CQP-003-pin-external-versions.md). Do not hand-roll the aggregation expression.
- Review the `needs:` set and the `allowed-skips` list together as a single change. They are coupled: every job not in `allowed-skips` must be in `needs:`, and every job in `allowed-skips` must have a documented reason its skip is legitimate.
- Treat `allowed-skips` as a closed list, default empty. Adding an entry requires naming the specific cascade (typically a matrix that is empty under some affected-set computations) and confirming no failure path can produce the same skip conclusion.
- When adding a new upstream job to the workflow, the same PR adds it to the `needs:` of the aggregator. The two lists drift if reviewed separately.

## How to Detect

Symptoms of a regressed aggregator on the required checks of this repository:

- A PR shows a green `build-status` while one of its upstream jobs (`changes`, `lint`, `test`, or `permanent-history-artefacts`) is red or skipped-as-cascade.
- The Actions tab shows the upstream job conclusion is `skipped`, but the developer expects it to have run.
- Branch protection allows merge despite a visibly broken CI run.

The diagnostic is to read the `needs:` of the aggregator job against the full job graph of the workflow. Any upstream job that does not appear in `needs:` is invisible to the merge gate. Likewise, any entry in `allowed-skips` whose skip can be produced by a cascade rather than a legitimate matrix-empty case is a silent-broken-gate vulnerability.
