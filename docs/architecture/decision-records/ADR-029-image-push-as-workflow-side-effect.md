---
status: accepted
date: 2026-05-26
decision-makers: [alex-on-java]
---

# Image Push as a Workflow Side Effect, Not an Nx Target

## Context and Problem

[ADR-026](ADR-026-image-build-ci-strategy.md) modeled image building and publishing as two Nx targets, `build-image` and `publish-image`, with the workflow invoking `nx run <project>:publish-image` to push to GHCR. The two-target shape was load-bearing: building and pushing ran in separate workflow jobs so that the pre-publish boundary could interpose between them.

After [ADR-028](ADR-028-pr-ci-with-two-aggregators-and-per-project-ci-target.md) moved cross-project safety into a workflow-level `pre-publish-gate`, the `publish-image` Nx target became hollow. Its command degenerated to a single `docker push` against an image the workflow had already restored into the runner's daemon through `actions/upload-artifact` and `docker load`. From a local shell, `pnpm exec nx run <project>:publish-image` suggested a supported project-owned publish path. That path no longer existed: the target read workflow-prepared runner state that a developer did not have locally.

The build/push split itself was correct and remained so. Two properties of the pipeline depend on it.

The split creates the workflow seam where the pre-publish gate sits. With a combined `buildx --push`, a successful build is also a successful push and nothing can interpose. Splitting them lets a failure anywhere, including in another project's lint, test, or repository-wide checks, stop this project's push.

Building is also the slow step of the per-project pipeline. Keeping `build-image` inside the per-project `ci` target lets it run in parallel with `lint` and `test` under Nx's internal scheduler. Pushing is fast, runs once per project after the gate, and does not need to share the critical path with static analysis.

## Decision Drivers

- An Nx target should express project-owned, locally-runnable work. A target whose semantics depend on workflow-specific state is misleading as a project command.
- The build/push split must remain. The seam between them is where cross-project safety lives and where build/push parallelism with lint and test becomes possible.
- The local-CI command surface (per [ADR-024](ADR-024-nx-as-monorepo-project-graph-and-task-runner.md)) should stay honest. `nx run <project>:ci` covers what a developer can verify locally; remote publishing has no local equivalent and should not be made to look like one.

## Decision

`publish-image` is removed as an Nx target. Every `project.json` that previously declared it no longer does, and the matching `targetDefaults.publish-image` entry in `nx.json` is removed.

`build-image` remains an Nx target with `--load` (per [LL-0040](../../lessons-learned/LL-0040-buildx-build-succeeds-but-image-missing-from-daemon.md)). It runs inside the per-project `ci` target alongside `lint` and `test` where those exist.

Image push is owned by `.github/workflows/ci-pr.yml`. After `pre-publish-gate` reports success, a publish-matrix job downloads the per-project image artifact, runs `docker load`, and runs `docker push "ghcr.io/${GITHUB_REPOSITORY_OWNER}/${PROJECT}:${IMAGE_TAG}"` directly. No Nx call sits in the publish job; consequently the job also has no checkout step and no `setup-nx` step.

Image handoff between the build job and the publish job uses `docker save` to a tarball, an `actions/upload-artifact` upload keyed by project name, and a matching `docker load` in the publish job. These mechanics live in workflow YAML, not in `project.json`. Tarball semantics exist only because GitHub Actions runners do not share Docker daemons; the project graph should not carry that CI-runner concern.

## Options Considered

- **Keep `publish-image` as a thin Nx target wrapping `docker push`.** First shape during this work.
- **Remove `publish-image`; the workflow runs `docker push` directly.** Chosen.

## Option Analysis

Keeping `publish-image` as a thin Nx wrapper preserved a uniform `nx run <project>:<verb>` surface but lied about it. The target's command was a `docker push` against an image identity the project does not own (the registry, the owner login, the tag). It ran against an image already present in the daemon by a workflow step the project does not see. A developer running it from a local shell either failed at the fail-fast `${IMAGE_TAG:?…}` guard (no image present locally, no tag set) or pushed to GHCR with deliberate intent. Neither path matches the project-level command shape an Nx target implies.

Removing the target tightens the project contract. `build-image` becomes the project's declaration that an image is ready for PR-triggered publication; the workflow decides when to publish and pushes directly. The local-CI command symmetry from ADR-024 still holds for what it should cover: `nx run <project>:ci` runs everything a developer can run locally. Publishing has no local equivalent and now has no local-looking surface.

A combined `buildx --push` would have collapsed build and publish into one Nx command, removing the workflow seam and the per-project parallelism gains. Both pipeline properties depend on the split; the option does not survive the drivers.

## Consequences

- **Good**: the project contract is honest. A project's Nx targets are commands a developer can run locally; remote publishing is not pretending to be one.
- **Good**: the build/push seam stays where the pre-publish-gate enforcement requires it, and `build-image` keeps running parallel with `lint` and `test`.
- **Good**: the publish job has no Nx dependency, no checkout, and no `setup-nx`. The job is one `docker login`, one `download-artifact`, one `docker load`, one `docker push`.
- **Bad**: a developer who wants to manually publish an image now writes `docker push` directly, without the Nx-mediated tag and registry inputs the removed target provided. In practice this changes little, because manual publish is not a supported workflow, but the removed convenience is real.
- **Neutral**: `build-image` retains the asymmetric tag policy from ADR-026 (`${IMAGE_TAG:-$(git rev-parse HEAD)}`). The fail-fast `${IMAGE_TAG:?…}` guard that lived in the removed `publish-image` target no longer has a target to live in. The workflow's publish job sets `IMAGE_TAG` explicitly from `github.event.pull_request.head.sha` (per [LL-0036](../../lessons-learned/LL-0036-pr-image-tag-absent-from-branch-history.md)), and a missing assignment manifests as a workflow error rather than a target-level shell guard.

## Related Records

- [ADR-024](ADR-024-nx-as-monorepo-project-graph-and-task-runner.md): establishes the principle that project targets are commands a developer can run locally, which this ADR enforces.
- [ADR-026](ADR-026-image-build-ci-strategy.md): the prior shape that included `publish-image` as a target. The shape it captured for image building and tag handling continues to apply; the `publish-image` target portion is removed by the present ADR.
- [ADR-028](ADR-028-pr-ci-with-two-aggregators-and-per-project-ci-target.md): the workflow-graph location of the pre-publish boundary this ADR's role split serves.
- [LL-0036](../../lessons-learned/LL-0036-pr-image-tag-absent-from-branch-history.md): image tag must come from `pull_request.head.sha`, not `github.sha`.
- [LL-0040](../../lessons-learned/LL-0040-buildx-build-succeeds-but-image-missing-from-daemon.md): `build-image` must use `--load` for a separate push step to find the image.
