---
status: accepted
date: 2026-05-08
decision-makers: [alex-on-java]
---

# Image Build CI Strategy: Affected-Driven Matrix with `alls-green` Aggregator

## Context and Problem Statement

The pre-Nx CI shape had three holes that compound under growth:

1. The `web-app` build ran unconditionally; the `convergence-checker` build was path-filtered. Asymmetric trigger policies become a maintenance liability as more apps are added.
2. `dispatch-pr-push` only `needs: build` (the web-app job), not the convergence-checker job. A failed convergence-checker image build did not fail-close the merge gate; the deployment notifier could fire on a broken build.
3. The required-checks list on `master` named `build / build` and `build-convergence-checker` directly. Adding an app meant editing branch protection. Fails the 10× litmus.

[ADR-024](ADR-024-nx-as-monorepo-project-graph-and-task-runner.md) introduces the Nx project graph. This ADR addresses the follow-up question: given that graph, what is the right CI shape for image builds? The shape must drive matrix membership from the graph (not a YAML allow-list), keep branch protection static across project additions, fail-close in every cascade-skip scenario, and preserve local-vs-CI build symmetry.

A subsidiary question is image-tag handling. The contract for `nx run <project>:build-image` and `:publish-image` must work in two places. Locally, developers expect a sensible default tag. In CI, the tag is the commit under test. Both call sites must use the same command shape.

## Decision Drivers

- **Affected-driven matrix with a stable aggregator check.** Branch protection must point at one check that does not rename as projects are added.
- **Per-project parallelism in CI, not single-runner sequential.** At two apps the cost difference is small; at ten, sequential builds in one runner are a multi-minute regression.
- **Fail-closed across every cascade-skip path.** GitHub treats `skipped` ≡ `success` for required-check evaluation; a job that does not run because its `needs:` failed reports as `skipped`. The aggregator must not let any silent-skip sneak past.
- **Honest cache contract for image builds.** The Nx caching contract is "side-effect-free." Image builds are side-effecting: the artefact lives in the docker daemon and in GHCR, not in `.nx/cache`. A "cache hit" that leaves no image behind must not be permitted.
- **Recovery from cold builds without lying.** Buildx layer cache via GHA is the right primitive for image-build recovery; Nx caching is the right primitive for deterministic file→file work. Each tool covers its own surface.
- **Local-CI symmetry.** The same `nx run <project>:build-image` command must work both locally and in CI. Local invocations pass no GHA cache flags; CI invocations pass `--cache-from type=gha`. The target definition does not fork.
- **Fail-fast on accidental remote pushes.** `publish-image` must not silently use a fallback tag. A missing `IMAGE_TAG` is a configuration error, not a default.

## Considered Options

### Matrix-vs-Aggregator Question

A. **Matrix + `alls-green` aggregator.** The `changes` job emits a JSON matrix from `nx show projects --affected --withTarget=publish-image --json`. The `build` job fans out one runner per affected app. A `build-status` job aggregates via `re-actors/alls-green` with `allowed-skips: build`.

B. **Single-runner `nx run-many --parallel=N`.** Drop the matrix and the aggregator. One `build` job runs all affected publishes inside one runner. The job name is static, so branch protection pins to it directly.

### Image-Tag Question

C. `${IMAGE_TAG:-$(git rev-parse HEAD)}` for both `build-image` and `publish-image`.

D. **`${IMAGE_TAG:-$(git rev-parse HEAD)}` for `build-image`, `${IMAGE_TAG:?…}` for `publish-image`.** Defaults convenient locally for build, fail-fast for publish.

E. Always require explicit `IMAGE_TAG`; no fallback anywhere.

## Decision Outcome

**Options A and D.** Affected-driven matrix with `alls-green` aggregator; asymmetric image-tag policy (default-fallback for `build-image`, fail-fast for `publish-image`).

### Workflow Shape

`.github/workflows/ci-pr.yml` now has these jobs in this dependency chain:

1. `permanent-history-artefacts`: unchanged from previous shape.
2. `changes` (`needs: permanent-history-artefacts`): uses the `setup-nx` composite action; runs `pnpm exec nx show projects --affected --withTarget=publish-image --json`; pipes through `jq empty` for malformed-output defence; emits `outputs.matrix`.
3. `lint` (`needs: permanent-history-artefacts`): runs `prek run --all-files`, which routes Python lint through `nx affected -t lint` (per ADR-025).
4. `test` (`needs: permanent-history-artefacts`): runs `pnpm exec nx affected -t test`. Closes the convergence-checker test gap.
5. `build` matrix (`needs: changes`, `if: needs.changes.outputs.matrix != '[]'`): `fail-fast: false`. Each matrix entry is one project per affected app. The job sets `IMAGE_TAG: ${{ github.event.pull_request.head.sha }}` and per-project `BUILDX_CACHE_ARGS`, then runs `nx run "$APP":publish-image` with the project name passed via env var (zizmor template-injection mitigation).
6. `build-status` (`needs: [permanent-history-artefacts, changes, lint, test, build]`, `if: always()`, `permissions: {}`): a single step running `re-actors/alls-green`. The step passes `jobs: ${{ toJSON(needs) }}` and `allowed-skips: build`. **The single required check for this repository's PR CI workflow.**
7. `dispatch-pr-push` (`needs: build-status`): rewired from `needs: build`. Now correctly fail-closes on convergence-checker (closes hole #2 from Context).

The reusable workflow `.github/workflows/reusable-build-push.yml` and the inline `build-convergence-checker` job are deleted.

### Why `changes`, `lint`, `test`, and `permanent-history-artefacts` Are All in `build-status: needs:`

The GitHub `skipped` ≡ `success` semantics mean any job that cascades to skipped due to a `needs:` failure becomes invisible to the aggregator unless explicitly listed. With `allowed-skips: build`, the aggregator legitimately ignores `build` skips (the no-affected-app case). Every other upstream job (`changes`, `lint`, `test`, `permanent-history-artefacts`) must appear in `needs:` of `build-status`, so that a cascade-skip surfaces as a missing-success rather than a clean skip. This is the load-bearing fail-closed mechanic. `allowed-skips` is intentionally narrow (`build` only). A `changes` failure (for example, the Nx command itself erroring, or `jq empty` rejecting malformed JSON) cannot be laundered through a skipped `build` into a green aggregator.

`alls-green` requires no permissions. `build-status` declares `permissions: {}` explicitly. A compromise of the action surface has zero blast radius beyond reporting a wrong check status, and the empty-permissions declaration is itself a reviewable safety statement.

`re-actors/alls-green`'s `contains(needs.*.result, 'failure')` check is evaluated at *step* scope. The long-running [actions/runner #1540](https://github.com/actions/runner/issues/1540) bug breaks job-level result aggregation; that does not apply here.

### Nx Caching Off for Image Builds; buildx GHA Cache Provides Recovery

`build-image` and `publish-image` are declared with `cache: false` in `nx.json` `targetDefaults`. The reasoning is direct. A cache hit on a fresh CI runner would skip the build. The image would not exist in the local docker daemon. The `publish-image` push would either fail confusingly or push a stale image. The Nx cache contract is "side-effect-free deterministic outputs"; image builds are not that. See [nx#18783](https://github.com/nrwl/nx/issues/18783) for the upstream discussion.

Recovery comes from the buildx GHA layer cache. The `build-image` target invokes `docker buildx build` with `${BUILDX_CACHE_ARGS:-}`, threading whatever the caller sets. CI sets it per matrix entry:

```
BUILDX_CACHE_ARGS=--cache-from type=gha,scope=<projectName> --cache-to type=gha,mode=max,scope=<projectName>
```

The per-project `scope=<projectName>` keys the cache so concurrent app builds do not fight for the same cache entry. Empirical recovery: ~50–70% typical, up to 80%+ in published benchmarks (HyperDX / Blacksmith). Locally, `BUILDX_CACHE_ARGS` is unset, the substitution expands to nothing, and buildx falls back to its default local cache.

This is the **division of labour** that makes the cache contract honest:

- Nx caches lint and test outputs (deterministic file→file work, declared inputs).
- buildx caches docker layers (already-existing layer-cache primitive, GHA-scoped per project).
- Nx does *not* attempt to cache image artefacts (the contract violation that produces silent-broken-deployments).

### Image-Tag Policy

`build-image` uses `${IMAGE_TAG:-$(git rev-parse HEAD)}`. `${VAR:-default}` falls back when `VAR` is unset *or* empty, so a passed-but-empty `IMAGE_TAG=""` correctly resolves to the current HEAD. Local builds work without ceremony: running `nx run web-app:build-image` from a clean worktree produces an image tagged with the current commit. The local risk of a stale `IMAGE_TAG` from the shell environment results in a misnamed local image, no remote effect.

`publish-image` uses `${IMAGE_TAG:?IMAGE_TAG required for publish-image}`. The `:?` form fails fast on unset *and* empty values. There is no fallback for `publish-image`: a missing tag is a configuration error, not a default. Accidental local `nx run <project>:publish-image` invocations cannot push to GHCR without explicit intent.

CI sets `IMAGE_TAG: ${{ github.event.pull_request.head.sha }}` rather than `${{ github.sha }}`. On `pull_request` events, `github.sha` is the synthetic merge SHA: the PR-head merged into base, not the commit the developer actually pushed. The deployable artefact must be tagged with the head SHA so that the image identity matches what the developer sees in `git log` on their branch.

Failure modes considered:

- (a) Set-but-empty `IMAGE_TAG`: handled by `${VAR:-default}` falling back when empty.
- (b) Stale environment `IMAGE_TAG`: a local-only risk; no remote effect because `publish-image`'s `:?` guard requires deliberate intent.
- (c) Detached HEAD or dirty worktree: `git rev-parse HEAD` returns the commit pointed-at. Dirty changes are not in the tag; appending a `-dirty` suffix would add noise without preventing footguns, and CI never has a dirty tree.
- (d) Mid-rebase: the same shape as (c).

### Consequences

- **Good**: branch protection on `master` lists the static repository-side checks `build-status` and `dispatch-pr-push`, alongside the out-of-scope cluster-pool/convergence checks `Ephemeral Cluster`, `Ephemeral DNS`, and `GitOps Convergence Gate`. Adding an app touches no branch-protection surface.
- **Good**: every cascade-skip is fail-closed. `changes` failure → `build` skipped (allowed) **and** `changes` reports failure to aggregator → `build-status` red. `lint`/`test` failure → `build-status` red. `permanent-history-artefacts` failure → `build-status` red.
- **Good**: per-project parallel runners in CI. At ten apps, builds parallelize across ten runners rather than queue inside one.
- **Good**: image-tag default-fallback for `build-image` makes local development frictionless; fail-fast for `publish-image` removes the silent-stale-push class.
- **Good**: Nx caches the deterministic surface (lint/test); buildx caches layers; neither tool is asked to cache something it cannot honestly track.
- **Bad**: the matrix is dynamic, so per-entry check names are dynamic. Branch protection cannot pin individual matrix entries; the aggregator is the only stable name. `alls-green` is the load-bearing primitive. Its absence (or any rename of the action) requires a coordinated branch-protection update.
- **Bad**: `BUILDX_CACHE_ARGS` is an env-var contract, not a typed parameter. Mistyping the variable name in CI produces a no-cache build that succeeds (slow but green), not an explicit error. Mitigated by per-project scope being part of the contract: a missing flag manifests as a 0% GHA cache hit, observable in build duration regression.
- **Neutral**: per-PR billing for parallel runners is non-zero. Accepted as the cost of preserving 10×-shape parallelism; the alternative (Option B) trades CI cost for future scaling debt.

## Pros and Cons of the Options

### A. Matrix + `alls-green` Aggregator

- Good: per-project parallelism in CI; no future scaling cost as projects are added.
- Good: aggregator name is stable; branch protection static across project additions.
- Good: cascade-skip behaviour is explicit. Every fail path is in `needs:` of `build-status`.
- Bad: dynamic matrix members require an aggregator job; per-entry check names are not pinnable.
- Bad: requires the `alls-green` action and the explicit `allowed-skips` list to be reviewed for correctness.

### B. Single-Runner `nx run-many --parallel=N`

- Good: one job, one name; branch protection pins directly.
- Good: no aggregator action dependency; Nx handles parallelism internally.
- Bad: parallelism bounded by one runner. At ten apps and a 4-core runner, builds serialize beyond the core count.
- Bad: a single-runner failure mode (out-of-disk during builds, network blip during `docker push`) takes all builds with it. There is no per-app isolation.
- Bad: removes the cleanest failure-attribution surface in CI; the multi-job UI shows one job red rather than the specific app.

### C. `${IMAGE_TAG:-$(git rev-parse HEAD)}` for Both Build and Publish

- Good: simplest; one shell idiom.
- Bad: `publish-image` would push to GHCR with the current HEAD SHA whenever `IMAGE_TAG` is unset. Developers running `nx run <project>:publish-image` locally (for any reason) would push to GHCR. The fail-fast property is lost.

### E. Always Require Explicit `IMAGE_TAG`

- Good: most explicit; no defaults to misuse.
- Bad: local `nx run <project>:build-image` becomes ceremony: `IMAGE_TAG=$(git rev-parse HEAD) nx run …` every time. A default that costs nothing remotely (the misnamed-local-image case is harmless) is a frictionless win.

## More Information

- The matrix-vs-aggregator decision is fundamentally a 10× scaling call. At two apps, the simplicity of Option B is genuine; at ten, its sequentialization makes CI a bottleneck. Picking Option A now means the shape does not need to be revisited under growth pressure: the cost of the decision is paid once.
- The four-case image-tag failure-mode enumeration above documents the contract; the asymmetric `:-` / `:?` split is the operational primitive that enforces it. The two are equivalent: the enumeration is the *why*, the substitution forms are the *how*.
- The `IMAGE_TAG: pull_request.head.sha` choice is deliberate over the more commonly seen `github.sha` shortcut: it preserves image-identity ↔ commit-identity matching across the PR lifecycle. The image of a future merge commit would carry its own (different) tag, with no aliasing back to PR builds.
- External actions used in `ci-pr.yml` and `.github/actions/setup-nx/action.yml` are pinned to commit SHAs per [CQP-003](../../code-quality-policies/CQP-003-pin-external-versions.md). This includes `re-actors/alls-green`, `nrwl/nx-set-shas`, `jdx/mise-action`, and every other external action. Floating tag annotations are kept in trailing comments for human readability.
