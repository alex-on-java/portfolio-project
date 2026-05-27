---
status: accepted
date: 2026-05-26
decision-makers: [alex-on-java]
---

# Project Routing for Static Analysis Lives in Nx

## Context and Problem

[ADR-025](ADR-025-python-project-linting-routed-through-nx.md) moved Python-project linting from project-owned `poe` invocations into Nx-affected dispatch through a pre-commit hook. That ADR also kept GitOps manifest validation as a `validate-gitops` target *inside the validator project* (`k8s-validation`), with a separate pre-commit hook (`validate-k8s-manifests`) wired through a per-hook `files:` regex.

The two-hook shape duplicated the project graph. Nx already knows which file belongs to which project; per-target `inputs` in `project.json` already declare each target's cache-key surface. Encoding the same routing a second time in each hook's `files:` regex was redundant and fragile. A missing extension meant the lint never fired; a new project type without a regex update silently fell out. Each new project type also required a coordinated edit of the hook configuration and of the CI `SKIP` directive that suppresses Nx-routed hooks inside the all-files static-analysis run.

GitOps manifest validation also lived under a project that did not own it. The `validate-gitops` target attributed every change under `gitops/` to the validator project (`k8s-validation`). The validator owned only its own Python source; the GitOps manifests were a separate concern in a separate directory.

## Decision Drivers

- Project routing belongs in Nx. A pre-commit hook should delegate file-to-project ownership to the project graph rather than re-encode it.
- Adding a project must not require editing the hook configuration or the CI `SKIP` directive.
- The set of files Nx sees as affecting a project's static analysis should match the project's actual ownership. GitOps manifests are owned by GitOps, not by the validator that implements the checks.

## Decision

A single pre-commit hook (`nx-affected-lint`) handles all project-scoped static analysis. The hook has no `files:` regex; it receives every changed file (subject to a conservative `exclude:` covering paths that no project owns: `docs/`, `.claude/`, `.agents/`, `.github/`). It forwards the changed files to `nx affected -t lint --files=<csv>`, and Nx decides which projects are affected from per-target `inputs`.

`gitops/` is a first-class Nx project. Its `project.json` declares a `lint` target that runs the Kyverno + Kubeconform validators through the `k8s-validation` runner. The project declares `implicitDependencies: [k8s-validation]` so that a change inside the validator's source marks `gitops:lint` as affected. Its `inputs` enumerate every file the target reads: the GitOps manifests under `{projectRoot}/**/*`, the runner's source under `{workspaceRoot}/tools/k8s-validation/`, and `mise.toml` for tool versions.

`implicitDependencies` and `inputs` are both required. `implicitDependencies` controls graph-level affectedness; `inputs` controls cache-key derivation. Neither substitutes for the other.

The previous `validate-gitops` target on the `k8s-validation` project and the previous `validate-k8s-manifests` hook are removed. The CI invocation of the all-files static-analysis run continues to skip the single Nx-routed hook (`SKIP: nx-affected-lint`). The per-project `ci` job from [ADR-028](ADR-028-pr-ci-with-two-aggregators-and-per-project-ci-target.md) covers it through `nx run <project>:ci`.

A new project type adds neither a hook nor a `SKIP` entry. Declaring a `lint` target in the new `project.json` is enough.

## Options Considered

- **Two hooks with per-project-type `files:` regexes.** The prior shape inherited from ADR-025.
- **One hook with no `files:` regex, forwarding all changed files to `nx affected`.** Chosen.

## Option Analysis

Two hooks with `files:` regexes worked for a stable set of project types but did not absorb new ones. Each new type forced a coordinated edit of the hook configuration, the matching CI `SKIP` directive, and, when the project owned a new file extension, the regex itself. The hook configuration tracked the project graph in a second place; the two surfaces drifted.

A single hook with no `files:` regex over-forwards files to `nx affected` and lets Nx do the work it already does. The cost is milliseconds of affected-graph computation on files that no project consumes. The benefit is that the routing surface collapses to a single layer: the project graph. The conservative `exclude:` covers paths that are not part of any project (documentation, agent prompts, GitHub workflow files), where the computation cost would be paid for no possible match.

Promoting `gitops/` to a first-class project resolves a second piece of misattribution. The validator project (`k8s-validation`) owns its Python source; the GitOps manifests are not part of it. With a separate `gitops` project, a manifest change marks `gitops:lint` affected, not the unrelated validator. A validator change still marks `gitops:lint` affected through `implicitDependencies`, preserving the real dependency. The explicit `inputs` list keeps the cache key honest.

## Consequences

- **Good**: adding a project that needs static analysis is a `project.json` write. The hook configuration and the CI workflow do not change.
- **Good**: static-analysis attribution matches actual ownership. Changes under `gitops/` belong to the `gitops` project.
- **Good**: the under-forwarding failure mode (a hook regex missing a file extension and silently dropping a lint) is no longer possible. The hook receives every changed file; Nx decides what is affected.
- **Bad**: the hook now runs `nx affected` for every commit, including commits that touch only paths the `exclude:` did not catch but no project owns. The overhead is bounded by Nx's affected-graph cost and is paid in seconds.
- **Neutral**: the local entry point for the static-analysis surface remains `prek run --all-files`. The choice of `prek` itself is preserved as the status quo rather than locked in by this ADR. Future changes to the local invocation surface (including replacing `prek` with another tool) remain unblocked.

## Related Records

- [ADR-024](ADR-024-nx-as-monorepo-project-graph-and-task-runner.md): Nx as the project graph this hook delegates to.
- [ADR-025](ADR-025-python-project-linting-routed-through-nx.md): the prior Nx-routing decision this ADR refines. The Nx → poe → tool contract and the bridge-script pattern from ADR-025 continue to apply; the hook-side routing is the part this ADR replaces.
- [ADR-028](ADR-028-pr-ci-with-two-aggregators-and-per-project-ci-target.md): the per-project `ci` target whose existence lets the all-files CI run skip the Nx-routed hook without losing coverage.
