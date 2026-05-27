---
status: accepted
date: 2026-05-26
decision-makers: [alex-on-java]
supersedes: [ADR-026]
---

# PR CI with Two Aggregators and a Per-Project `ci` Target

## Context and Problem

[ADR-026](ADR-026-image-build-ci-strategy.md) introduced an affected-driven matrix with a single `alls-green` aggregator. Three properties of that shape did not survive a second wave of work in this repository.

First, the matrix fanned out per Nx target (`lint`, `test`, `build` as separate matrices). Adding a project type meant adding another matrix in the workflow, a new entry to consider in branch protection, and a new `SKIP` entry in the pre-commit configuration. The CI surface grew with every project type, not only with every new project.

Second, a single aggregator cannot simultaneously gate image publish and observe its result. Image publish must wait on a green aggregator so that no broken image reaches GHCR (Kargo watches GHCR directly and treats every new image as freight). The required-check aggregator must also run *after* publish so that a failed push fails the merge gate. The two roles are mutually exclusive at one node.

Third, an early Nx-level attempt to gate publish per project (chaining `publish-image.dependsOn: [lint, test, build-image]` on each app) was not enough. Cross-project failures (one project's lint failing while another's publish proceeded) had no expression inside a per-project `dependsOn`. Repository-wide checks that were not naturally scoped to one project (immutable-history enforcement, generic static checks) had no place in that model at all. The workflow graph permitted the unsafe trace: an image could be published on a PR whose repository-wide checks were red.

The intuitive monorepo mental model (a red required CI gate means no image was published on this PR) did not hold. Documentation could not reconcile the gap because the graph itself permitted the unsafe trace.

## Decision Drivers

- The safety property that a red required check prevents image publication must be a property of the CI graph, not a property of human attention to a red check.
- Adding a project must be a single-file write. New project types must not force workflow edits, branch-protection edits, or pre-commit `SKIP` edits.
- The required-check aggregator must observe every upstream verdict, including the publish step that side-effects on GHCR. Empty-matrix legitimate skips must remain the only tolerated skip path.
- Repository-wide guards that almost never fire (immutable history, generic static checks) should run in parallel with affected detection, not on its critical path.

## Decision

PR CI uses two aggregators with distinct roles.

**`pre-publish-gate`** decides whether to publish. It runs `re-actors/alls-green` with `if: always()`, `permissions: {}`, and `needs:` covering every pre-publish job: the affected-detection job, the generic static checks job, and the per-project `ci` matrix. Its `allowed-skips` covers only the `ci` matrix (the empty-affected-set path).

**`build-status`** decides whether to merge. It also runs `re-actors/alls-green` with `if: always()` and `permissions: {}`, and its `needs:` lists every job in the workflow, including `pre-publish-gate`, the publish job, and the artifact-cleanup job. Its `allowed-skips` covers only the jobs whose skip is produced by an empty matrix.

Per-project Nx targets express the per-project static-analysis and build contract. Each `project.json` declares a `ci` target whose `dependsOn` lists what that project owns. A Python service declares `ci.dependsOn: [lint, test, build-image]`; a static-content app declares `ci.dependsOn: [build-image]`; a manifest project declares `ci.dependsOn: [lint]`. The CI workflow fans out one runner per affected project and runs `nx run <project>:ci` in that runner. `ci` is workspace-uncached (`targetDefaults.ci.cache: false` in `nx.json`); the orchestrator must not mask an uncached sub-target behind a cache hit.

The publish job runs after `pre-publish-gate` succeeds. The downstream cross-repo dispatch job carries the explicit `if: always() && needs.build-status.result == 'success'` guard from [LL-0047](../../lessons-learned/LL-0047-downstream-job-silently-skipped-after-green-aggregator.md).

This replaces ADR-026's single-aggregator shape.

## Options Considered

- **Three per-target matrices (`lint`, `test`, `build`) under one aggregator.** Implemented during an earlier iteration of this work.
- **Per-project Nx-level gate (`publish-image.dependsOn` extended on each app).** Implemented during a later iteration of the same work.
- **One canonical `ci` target per project, fan-out by project, two aggregators.** Chosen.

## Option Analysis

The three-matrix shape did not scale per project type. Every target type that an Nx project might own added four things: a CI matrix, an aggregator `needs:` entry, an `allowed-skips` entry, and a pre-commit `SKIP` directive. The cost grew with target types times projects. The shape also duplicated work on the critical path: any iteration that gated publish on prior lint and test re-ran those steps inside the build job, because Nx remote cache is not configured here.

The per-project Nx-level gate failed for reasons that no per-project mechanism could close. It scoped publish to *that* project's lint and test only, so one project's failed lint did not block another project's publish. Repository-wide checks that are not naturally scoped to one Nx project (the immutable-history guard, the generic static-checks job) had no place in the gate at all. Both gaps were observable in the workflow graph: a publish path could proceed without all repository-wide checks being green.

The canonical `ci` target absorbs the per-project static-analysis contract inside Nx, where it belongs. Each project declares one target; CI fans out one matrix entry per project. Cross-project gating moves to the workflow-graph layer (`pre-publish-gate`), where it can express the safety property the per-project model could not: all pre-publish work succeeded across all affected projects, and every repository-wide guard passed. Adding a project is a single-file write: declare the project's targets in `project.json`, declare which of them belong to `ci.dependsOn`, and the workflow picks the project up through affected detection without any workflow YAML touch.

Two aggregators rather than one resolves the role conflict directly. `pre-publish-gate` runs before publish and decides whether to publish; `build-status` runs after publish and decides whether to merge. Both satisfy the five load-bearing aggregator properties from [LL-0038](../../lessons-learned/LL-0038-required-check-green-despite-failed-upstream-job.md).

## Consequences

- **Good**: the safety property that a red required check prevents image publication is a graph property of the workflow.
- **Good**: adding a project does not touch workflow YAML, branch protection, or pre-commit configuration.
- **Good**: the immutable-history guard and the generic static-checks job run in parallel with affected detection. A guard that almost never fires no longer serializes the common path.
- **Good**: the per-project `ci` target gives Nx one project-level command for everything that project owes. Local development uses the same surface (`pnpm exec nx run <project>:ci`) the workflow uses.
- **Bad**: the merge-gate aggregator now lists more upstream jobs in `needs:` and tolerates more legitimate skip paths in `allowed-skips`. The coupling rule from LL-0038 holds unchanged: every job not in `allowed-skips` must be in `needs:`, and every skip path covered by `allowed-skips` must have a documented matrix-empty cause.
- **Neutral**: the merge-gate aggregator's name `build-status` was preserved across the redesign, so branch protection did not need to change. The name carries no special semantic in the new shape.

## Postponed Effort

- Nx remote cache. `nx affected` recomputes across runners because no remote cache is wired up. Configuring one would erase the cross-runner recomputation cost without changing the shape decided here.
- Renaming the merge-gate aggregator job. The current name was preserved for branch-protection continuity, not because it best describes the new role.

## Related Records

- [ADR-026](ADR-026-image-build-ci-strategy.md): superseded by this record. The image-tag asymmetry (`${IMAGE_TAG:-…}` for build, fail-fast `:?` for publish) and the buildx-cache division of labor recorded there remain in force; the aggregator topology does not.
- [ADR-024](ADR-024-nx-as-monorepo-project-graph-and-task-runner.md): establishes the project graph this CI shape consumes.
- [ADR-025](ADR-025-python-project-linting-routed-through-nx.md): Python project linting routed through Nx; the per-project `ci` target absorbs the surface ADR-025 introduced.
- [LL-0038](../../lessons-learned/LL-0038-required-check-green-despite-failed-upstream-job.md): the load-bearing aggregator properties that both aggregators here rely on.
- [LL-0046](../../lessons-learned/LL-0046-job-skipped-despite-explicit-needs-result-check.md) and [LL-0047](../../lessons-learned/LL-0047-downstream-job-silently-skipped-after-green-aggregator.md): the implicit `success() &&` walk past an aggregator, and the explicit `if: always() && needs.<X>.result == 'success'` pattern every downstream job uses.
