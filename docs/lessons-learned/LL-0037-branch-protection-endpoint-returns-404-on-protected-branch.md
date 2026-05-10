# LL-0037: GitHub Branch Protection Has Migrated to the Rulesets API; the Legacy Endpoint Returns a Misleading 404

## Summary

GitHub has moved branch protection from the legacy `/repos/{owner}/{repo}/branches/{branch}/protection` endpoint to the rulesets API at `/repos/{owner}/{repo}/rulesets/{id}`. On a repository whose branch is protected by a ruleset, the legacy endpoint returns `404 Branch not protected` even though protection is fully active. Many runbooks and third-party docs still describe the legacy endpoint as canonical, so the 404 reads as "no protection" when the reality is "protection lives elsewhere."

## What Happened

A migration plan for this repository specified `gh api PATCH /repos/.../branches/master/protection` to update required status checks on `master`. The legacy endpoint returned `404 Branch not protected`. Protection was active nonetheless: pushes to `master` were rejected and PR merges enforced status checks, all under ruleset id `14952354` ("Protect master") in the rulesets API. Replanning the migration around `PUT /repos/.../rulesets/14952354` was necessary because the plan had targeted the wrong API surface.

## Root Cause

GitHub introduced rulesets as a newer mechanism for branch and tag protection. Rulesets and legacy branch protections coexist on the API surface, but the legacy `/branches/{branch}/protection` endpoint reports only legacy-style configurations. A ruleset that targets `master` does not appear there, and the endpoint returns the same `404 Branch not protected` it would return for a genuinely unprotected branch. The response carries no hint that a ruleset is in effect.

## Resolution

Treat rulesets as the default mechanism and the legacy endpoint as a fallback.

To detect which mechanism is in use, query rulesets first:

```bash
gh api /repos/{owner}/{repo}/rulesets
```

If the list contains an entry whose `target` is `branch` and whose conditions match the branch in question, that branch is ruleset-managed. A `404 Branch not protected` from the legacy endpoint, on its own, is not evidence that the branch is unprotected.

To update a ruleset, fetch the full body, mutate the relevant fields, and write it back:

```bash
gh api /repos/{owner}/{repo}/rulesets/{id} > ruleset.json
# edit ruleset.json
gh api --method PUT /repos/{owner}/{repo}/rulesets/{id} --input ruleset.json
```

`PUT /rulesets/{id}` is read-modify-write and replaces the full document; it is not a JSON Patch. Sending a partial body drops the omitted fields. The token also needs the `repo` scope (or the fine-grained `Administration: write` permission), the same level the legacy endpoint required.

## How to Detect

Symptoms that a script or runbook is talking to the wrong protection surface:

- `gh api /repos/.../branches/{branch}/protection` returns `404 Branch not protected`, yet pushes to the branch are rejected and PR merges enforce status checks.
- The Settings page for the repository shows protection rules under "Rulesets" rather than "Branch protection rules."
- A migration script appears to succeed (no 404) but produces no observable change because it is patching a stale legacy object that the UI no longer reads.

## Adoption Rule

Any script or runbook that touches branch protection on this repository must query `/repos/{owner}/{repo}/rulesets` first and identify the ruleset that targets the branch. The legacy `/branches/{branch}/protection` endpoint is a fallback for repositories that have not migrated, not the default. For this repository, `master` is protected by ruleset id `14952354`; updates go through `PUT /repos/{owner}/{repo}/rulesets/14952354` with the full ruleset body.
