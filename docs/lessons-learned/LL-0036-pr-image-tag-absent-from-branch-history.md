# LL-0036: `github.sha` Resolves to the Synthetic Merge SHA on `pull_request` Events, Not the Head Commit

## Summary

GitHub Actions evaluates `${{ github.sha }}` to the synthetic *merge commit* on `pull_request` events: the PR head merged into base on the `refs/pull/<n>/merge` ref. The commit a developer actually pushed is `${{ github.event.pull_request.head.sha }}`. Any artefact tagged with `github.sha` therefore carries an identifier that does not appear in `git log` on the developer branch.

## Why It Bites

The synthetic merge SHA is a real, valid git object. `git cat-file -e <merge-sha>` succeeds against a checkout of `refs/pull/<n>/merge`; nothing about the value looks wrong. Two failure modes follow.

The *image-identity* mode: a Docker image pushed to GHCR with `IMAGE_TAG=${{ github.sha }}` carries a tag no developer can reproduce locally. Running `git checkout <tag>` on the developer branch fails. That SHA exists only on a ref the runner constructed and discarded. PR commenters and downstream pipelines that trust the invariant "image tag equals commit under test" silently lose it.

The *aliasing* mode: when the PR eventually merges, the post-merge `push` event sees a different `github.sha` (the actual merge commit recorded on `master`, not the synthetic one). Image identity does not chain across the PR lifecycle; the artefact built during PR review and the artefact built post-merge have unrelated tags even though the source state is identical.

The failure is silent because no step errors. Build succeeds, push succeeds, the registry accepts the tag. Mismatch only surfaces when somebody tries to map an image back to a commit and fails.

## Adoption Rule

For any artefact whose identity must match the commit a developer pushed, on `pull_request` events use:

```yaml
env:
  IMAGE_TAG: ${{ github.event.pull_request.head.sha }}
```

`github.sha` is acceptable when the run identity is *meant* to track the merge SHA. Examples: post-merge `push` events on `master`, or CI whose only consumer is the per-commit check display in the GitHub UI. The distinguishing question: would a future reader expect to find this SHA in `git log` on the source branch? If yes, use `pull_request.head.sha`.

The image-publishing workflow for this repository follows the rule; see `.github/workflows/ci-pr.yml` (the `IMAGE_TAG` assignment in the matrix step of the `build` job). [ADR-026](../architecture/decision-records/ADR-026-image-build-ci-strategy.md) records the project decision; this LL captures the underlying platform fact that makes the documented `github.sha` shortcut wrong for PR-time artefact identity.

## Worked Example

A developer pushes commit `aaaa111` to branch `feature/x`. The PR base is `master` at `bbbb222`. GitHub constructs the synthetic merge ref `refs/pull/<n>/merge` containing commit `cccc333` (the result of merging `aaaa111` into `bbbb222`). For the `pull_request` event, `github.sha` resolves to `cccc333` (synthetic, only on `refs/pull/<n>/merge`); `github.event.pull_request.head.sha` resolves to `aaaa111` (the developer push, on `feature/x`).

An image tagged `cccc333` has no preimage on `feature/x`. The same image tagged `aaaa111` round-trips: `git checkout aaaa111` on `feature/x` reproduces the source the image was built from.

## How to Detect

- A PR-built image carries a tag that does not appear in `git log` on the PR branch.
- `git cat-file -t <tag>` succeeds in a fresh clone only after fetching `refs/pull/<n>/merge`; it fails against the PR branch history alone.
- Two consecutive workflow runs on the same head commit produce different image tags because the synthetic merge SHA changed when base advanced.
