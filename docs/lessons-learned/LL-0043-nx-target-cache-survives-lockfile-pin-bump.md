# LL-0043: Nx Target Inputs Must Include Lockfiles for Cache Hashing

## Summary

Nx targets declared with `cache: true` invalidate based on the file set listed in `inputs`. When a dependency-pin change lives only in a lockfile (`uv.lock`, `pnpm-lock.yaml`) and the lockfile is absent from that set, the cache key does not move. A pin bump can therefore produce a green CI result against a stale cached artefact, with no error and no log line. Source globs and `pyproject.toml` alone are insufficient, because `uv lock` rewrites pins without touching either; the lockfile must be in every cached target that runs through a package manager.

## What Happened

In `apps/platform/convergence-checker`, the `lint` and `test` targets declared inputs as `src/**/*.py`, `tests/**/*.py`, `pyproject.toml`, and `.python-version`. That set covers the human-edited surface but omits `uv.lock`. On the same project, `build-image` did include `uv.lock`. A pin bump performed via `uv lock` (no source or `pyproject.toml` change) therefore produced a different cache key for `build-image` but the same cache key for `lint` and `test`. CI replayed the prior cached `lint` and `test` outcomes and reported `success`, despite the resolved dependency set having changed under the targets.

`tools/k8s-validation` exhibited the same shape: `lint` omitted `uv.lock`; `validate-gitops` already included it.

## Root Cause

Nx hashes the contents of the input files declared on a target into the cache key. Files outside the declared set are invisible to the hash by construction. A lockfile is the canonical place where pin resolutions are recorded: `uv lock` and `pnpm install --lockfile-only` mutate the lockfile without mutating `pyproject.toml` or `package.json`. Targets that run `uv run --frozen poe lint` read the lockfile at execution time. When the lockfile is not declared as an input, the runtime dependency and the cache-key dependency disagree.

The failure mode is silent. There is no error, no warning, no log line; the cache hit is indistinguishable from a legitimately-skipped run. Detection requires either reading the resolved input set or comparing cache keys across two runs that differ only in the lockfile.

## Resolution

The fix adds the project-local `uv.lock` to the inputs of every cached target that runs through `uv`. In `apps/platform/convergence-checker/project.json`, `lint` and `test` now hash `{projectRoot}/uv.lock`. For `tools/k8s-validation/project.json`, `lint` now hashes `{projectRoot}/uv.lock`; `validate-gitops` already declared it.

Each target keeps its declared inputs explicit and local to the project, matching the existing inline-inputs pattern. Per [ADR-024](../architecture/decision-records/ADR-024-nx-as-monorepo-project-graph-and-task-runner.md), inputs stay inline until a third project shares the same shape, at which point they factor into `nx.json` `namedInputs`.

## Adoption Rule

Every cached target that resolves dependencies through a package manager must declare the corresponding lockfile in its `inputs`. Concretely:

- `uv` → `{projectRoot}/uv.lock`
- `pnpm` → `{projectRoot}/pnpm-lock.yaml` (or the workspace lockfile when one lands)
- `npm` → `{projectRoot}/package-lock.json`
- `cargo` → `{projectRoot}/Cargo.lock`
- `go` → `{projectRoot}/go.sum`

The manifest file (`pyproject.toml`, `package.json`) belongs in `inputs` for the same reasons but does not substitute for the lockfile. Resolved versions live in the lockfile; a resolution change without a manifest change is the exact case this LL is about.

## How to Detect

Run `pnpm exec nx run <project>:<target> --verbose`, which prints the resolved input set Nx hashed for the cache key. Inspect it directly: every package-manager-driven target should list a lockfile.

A second check: bump a pin via `uv lock` (or `pnpm install --lockfile-only`) without editing source or the manifest, then run the cached target twice. If the second run reports `[local cache]` against unchanged inputs, the lockfile is missing from the input set.

The same reasoning applies to any cached target whose execution reads files outside its declared inputs. Lockfiles are the most common case; other examples include shared workspace configuration (`mise.toml` for tool versions, `.python-version` for the interpreter pin) and any sibling-project artefact consumed at runtime.
