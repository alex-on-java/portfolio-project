# LL-0010: GitHub App token defaults to current repository scope

## Summary

`actions/create-github-app-token` scopes the generated installation token to the current repository only. Cross-repo dispatch fails silently with a 404 unless the target repository is explicitly added via the `repositories` parameter.

## What happened

The CI workflow dispatched a `repository_dispatch` event to the `portfolio-project-cluster-pool` repo. The dispatch step returned a 404 error despite the GitHub App having the correct permissions configured in its settings.

## Root cause

The `actions/create-github-app-token` action generates an installation token with a default scope limited to the repository where the workflow runs. Even if the GitHub App itself is installed on multiple repositories, the token only grants access to the current one unless explicitly widened. The 404 is misleading — it looks like the target repo doesn't exist, but the actual problem is insufficient token scope.

## Resolution

Added the `repositories` parameter to the composite action wrapping `create-github-app-token`:

```yaml
with:
  app-id: ${{ inputs.app-id }}
  private-key: ${{ inputs.private-key }}
  repositories: portfolio-project-cluster-pool
```

## How to detect

If a cross-repo dispatch returns 404 and the target repo definitely exists, check the token scope. Use the GitHub API to inspect the token: `GET /installation/token` response includes the `repositories` array showing which repos the token can access.
