---
status: accepted
date: 2026-05-26
decision-makers: [alex-on-java]
---

# CI Artifact Cleanup as Hygiene, Decoupled from PR Quality

## Context and Problem

The PR CI pipeline writes intermediate artifacts. ADR-029's image-handoff design in [ADR-029](ADR-029-image-push-as-workflow-side-effect.md) uses `actions/upload-artifact` to ship per-project image tarballs from the build job to the publish job. Any future job may upload an artifact for similar handoff or diagnostic reasons. GitHub Actions retains workflow-run artifacts for a finite period; without active cleanup, every PR push accumulates a logical artifact bucket keyed by `GITHUB_RUN_ID` and waits for retention to reap it.

The earlier cleanup job carried four overlapping defects, each undermining the guarantee it claimed to provide.

It filtered artifacts by an `image-` name prefix. Any artifact that did not match the prefix was invisible to cleanup, even though every artifact in a run shares the same retention surface.

Its listing call lived inside a bash process substitution. Process substitution does not propagate the inner command's exit status under `set -Eeuo pipefail`. A failing listing call produced an empty pipe; the deletion loop iterated zero times; the step exited 0; nothing was reaped and nothing was reported.

It was both a member of the merge-gate aggregator's `needs:` set and an entry in its `allowed-skips`. The step itself emitted per-artifact warnings and exited 0 (best-effort semantics), but the workflow graph declared it a must-succeed dependency of the merge gate. The two layers contradicted each other.

Its `if:` guard depended on a `needs.changes.outputs.publish_matrix != '[]'` comparison. When the upstream `changes` job was skipped for any reason, that output behaved as empty in expression context, so `'' != '[]'` evaluated to `true`. The guard let cleanup proceed exactly when its producer had never run.

The combined behavior gave neither reliable cleanup nor reliable reporting. Cleanup could silently no-op while the merge gate treated it as passed, and a real systemic failure (token expired, GH Artifacts API outage, workflow regression) produced no actionable signal.

## Decision Drivers

- Cleanup is repository hygiene, not a PR-quality signal. A cleanup failure has nothing to do with whether the PR should merge.
- Every artifact attached to the workflow run must be in scope, regardless of which job uploaded it.
- A systemic cleanup failure must produce a visible, deduplicated signal that does not spam a tracking surface.
- The cleanup job should not couple to the changing set of artifact-producing jobs. A new producer should not require a corresponding edit of the cleanup graph anchor.

## Decision

The cleanup job runs once at the end of every PR pipeline, anchored to the merge-gate aggregator with `if: always()`. Its `needs:` lists only the merge-gate aggregator. It is not a member of `build-status.needs`, and it does not appear in `allowed-skips`.

The job reaps every artifact attached to the current `GITHUB_RUN_ID` via the GitHub Artifacts REST API. There is no name-prefix filter.

The listing call is a plain `$(...)` assignment, so a failed list aborts the step under `set -Eeuo pipefail`. Per-artifact deletion failures emit a `::warning::` line each; if any per-artifact failure occurs, the step emits a final `::error::` summary and exits non-zero.

A second step runs `if: failure()` on the same job. It searches for an open issue with the fixed title `CI artifact cleanup failed`; if one exists, it posts a follow-up comment, otherwise it opens a new issue. The job declares `issues: write` in its own permissions block alongside the existing `contents: read` and `actions: write`. The assignee resolves via expression fallback `${{ vars.CLEANUP_FAILURE_ASSIGNEE || github.repository_owner }}`.

The `gh issue` invocations in this checkout-less job pass `--repo "$GITHUB_REPOSITORY"` explicitly. Without it, `gh issue` shells out to `git remote -v` to resolve `owner/repo` and fails outside a working tree.

## Options Considered

- **Single job with `issues: write`, dedup-by-title issue surface.** Chosen.
- **Two-job split: a cleanup job without `issues:` permission, followed by an issue-creator job scoped to `issues: write` only.** Recommended during deliberation.

## Option Analysis

The two-job split gives a narrower permission boundary per job: a deletion-only job needs `actions: write` but not `issues: write`, and an issue-only job needs the inverse. The trade-off is a second job in the workflow graph for a token scope that, in practice, carries no exploit surface worth segregating. The action authoring the API call is a first-party shell script in this repository; the added job adds review surface and graph edges without proportional safety benefit.

The single-job shape colocates the deletion step and the failure-handler step in one runner under a single permissions block. The failure handler is `if: failure()` on the deletion step, so it runs only when there is something to report. This shape is simpler to read, simpler to grant permissions for, and matches the actual blast-radius assessment.

Anchoring cleanup to the merge-gate aggregator rather than to the producer set is a separate coupling decision. Listing every artifact-producing job in `cleanup.needs:` would grow the cleanup graph edge with every new producer. Anchoring to `build-status` expresses the condition cleanup needs: the pipeline reached a terminal verdict. Because `build-status` already inherits the producer jobs through transitive `needs:`, the cleanup graph edge does not need to grow alongside the producer list. It also removes a class of cross-domain naming confusion: an Nx target named `ci` and a workflow job named `ci` read ambiguously in a literal `needs: [ci]` line. The precondition is that `build-status` itself never reaches `skipped`; this holds because `build-status` carries `if: always()` and always reaches a terminal `success` or `failure`.

GitHub does not deduplicate issues natively, so the job deduplicates by fixed title. Without that check, a systemic cleanup failure would file one issue per PR push and saturate the tracking surface. The mechanism is included partly as a working example of a production-hygiene shape worth demonstrating in this repository, not only because immediate scale demands it.

The assignee fallback `vars.CLEANUP_FAILURE_ASSIGNEE || github.repository_owner` guards a specific failure mode. If the repository is ever transferred to a GitHub organization, `github.repository_owner` resolves to the org login, which is not a valid issue assignee. The repository variable lets that case be retargeted without editing workflow YAML.

## Consequences

- **Good**: 100% artifact reaping per run. There is no name-prefix filter to forget; every upload is in scope.
- **Good**: cleanup failures route to a deduplicated tracking issue. The first failure opens an issue; subsequent failures comment on it. The signal is visible and bounded.
- **Good**: the merge gate is not polluted by infrastructure-hygiene noise. A cleanup outage does not block PR merges; GitHub's artifact retention is the safety net while the issue is being addressed.
- **Good**: every PR, including docs-only PRs whose pipelines produce no artifacts, runs the cleanup job and exercises its REST API path. The job becomes a continuous canary for token expiry or for changes to the artifact API surface.
- **Bad**: an end-of-pipeline job runs on every PR. The cost is one short-lived runner per PR (about one second in the empty-list case). For docs-only PRs the cleanup job is the only job in the tail; for image-producing PRs it adds a small wall-clock tail.
- **Bad**: a single shared tracking issue can grow long if a real outage persists across many PRs. The mitigation is that a single comment thread is easier to scan than a flood of issues, and the issue is closed once the underlying cause is resolved.
- **Neutral**: the assignee is reassignable at any time by setting the repository variable `CLEANUP_FAILURE_ASSIGNEE`; the workflow file does not need to change.

## Related Records

- [ADR-028](ADR-028-pr-ci-with-two-aggregators-and-per-project-ci-target.md): defines `build-status` as the merge-gate aggregator this cleanup job anchors to.
- [ADR-029](ADR-029-image-push-as-workflow-side-effect.md): defines the image-artifact handoff this cleanup primarily reaps.
- [LL-0038](../../lessons-learned/LL-0038-required-check-green-despite-failed-upstream-job.md): the load-bearing aggregator properties that make `build-status` a safe anchor (notably `if: always()` on the aggregator itself, so it always reaches a terminal status).
- [LL-0047](../../lessons-learned/LL-0047-downstream-job-silently-skipped-after-green-aggregator.md): the explicit `if: always()` pattern on downstream jobs; the cleanup job uses `if: always()` because it must run after either a successful or failed pipeline.
