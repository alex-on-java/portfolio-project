# LL-0046: GitHub Actions Auto-Prepends `success() &&` Against the Transitive `needs:` Graph

**Summary**: GitHub Actions auto-prepends `success() &&` to any job-level `if:` expression that lacks a status-check function (`always()`, `cancelled()`, `failure()`, `success()`). Its implicit `success()` evaluates against the transitive `needs:` graph rather than direct dependencies. An explicit `needs.X.result == 'success'` check therefore combines with this stricter walk via boolean AND. That combined expression returns `false` whenever the runner earlier skipped any ancestor of `X`, regardless of the conclusion of `X` itself.

## What Happened

GitHub silently skipped a job carrying `if: needs.<aggregator>.result == 'success'` on PRs whose aggregator reported `success`. Adding `always() &&` to the front of the same `if:` made the same job run on the same PR shape. The result-check expression remained identical across both runs.

## Root Cause

GitHub Actions auto-prepends `success() &&` to a job-level `if:` whenever the expression lacks a status-check function. The implicit `success()` evaluates the transitive `needs:` graph, not just direct dependencies. Any skipped job in that graph returns `false` from the implicit check. That `false` propagates through the AND, defeating the explicit gate even when the explicit gate alone would return `true`.

Official documentation at `docs.github.com/en/actions` omits this behavior. External references describe it as a long-standing quirk: GitHub community discussion #45058, `actions/runner` issues #491 and #2205.

## Resolution

Place a status-check function in the `if:` to suppress the auto-prepended `success() &&`. The minimal idiom that gates on a single result and nothing else relies on the `always()` token doing the load-bearing work:

```yaml
if: always() && needs.<job>.result == 'success'
```

An earlier branch tried the narrower form (`if: needs.<job>.result == 'success'`) and found it insufficient on docs-only PRs. Only the form with `always() &&` ran the dependent job.

## How to Detect

GitHub silently skips a job whose `if:` references only direct `needs:` results, on PRs where the runner earlier skipped some upstream that the job depends on transitively, not directly. The Actions tab shows the job conclusion as `skipped` with no error. Reading the workflow file confirms the `if:` lacks any of `always()`, `cancelled()`, `failure()`, `success()`.
