# LL-0066: `gh issue` Subcommands Shell Out to `git remote` Even for Pure REST API Calls

**Summary**: `gh issue list`, `gh issue comment`, and `gh issue create` resolve the owner/repo pair by shelling out to `git remote -v` when no `--repo` flag is passed. Running them outside a working tree aborts before the API call. The sibling `gh api /repos/{owner}/{repo}/…` family has no such dependency. Passing `--repo "$GITHUB_REPOSITORY"` bypasses `git remote` resolution entirely and costs nothing at the call site.

## What Happened

The `cleanup-run-artifacts` job in `.github/workflows/ci-pr.yml` has no `actions/checkout` step by design: it makes only REST API calls via `gh api`. A failure-handler step in that job used `gh issue list`, `gh issue comment`, and `gh issue create` to open or comment on a tracking issue.

On the first real CI run (verification run 26093886791, B1 scenario), the failure handler crashed immediately:

```
failed to run git: fatal: not a git repository
(or any of the parent directories): .git
```

The script ran under `set -e`, so the first `gh issue list` call aborted the entire step. As a result, the dedup-and-report mechanism never executed.

## Root Cause

`gh issue list`, `gh issue comment`, and `gh issue create` resolve owner/repo by shelling out to `git remote -v`. This happens even when no `--repo` flag is passed and the call would otherwise be a pure REST request. Running them outside a working tree aborts before the API call reaches GitHub. Neither `gh --help` nor `gh issue --help` documents this dependency.

`gh api /repos/{owner}/{repo}/…` has no such dependency: it is repo-agnostic at the protocol layer.

## Resolution

Adding `--repo "$GITHUB_REPOSITORY"` to all three `gh issue` invocations fixes the failure. `GITHUB_REPOSITORY` is set automatically by GitHub Actions. The flag bypasses `git remote` resolution entirely.

Three options were considered. Adding `--repo` on each call site (chosen) signals intent explicitly and costs two characters per call. Switching to `gh api /repos/{owner}/{repo}/issues…` loses the heredoc multi-paragraph body ergonomics of `gh issue create --body`. Adding `actions/checkout` to the cleanup job is conceptually wrong: the job has no code dependency, and a 5-10 second checkout tax just so `git remote -v` can answer is waste.

The flag was applied symmetrically to `list`, `comment`, and `create`, even though only `list` was observed to fail, because all three share the same `git remote -v` resolution mechanism.

## How to Detect

Any workflow step that calls `gh issue`, `gh pr`, or `gh repo` subcommands without a preceding `actions/checkout` step is vulnerable. The failure appears as `fatal: not a git repository` in the step log, not as an API or authentication error. On the surface it looks like a filesystem or environment problem rather than a missing flag.

## Adoption Rule

When a CI job uses `gh issue`, `gh pr`, or `gh repo` subcommands without `actions/checkout`, pass `--repo "$GITHUB_REPOSITORY"` on each call. Switching to `gh api` is equally valid. Do not add `actions/checkout` just to satisfy `git remote -v`.

This is the same class of failure as the process-substitution incident from commit `6a61f31`: a silent indirection (`git remote -v`) hides a failure mode behind an unrelated symptom. The common pattern is a CLI tool that resolves context through a subprocess the caller does not expect, and that resolution fails in an environment the caller considered valid.
