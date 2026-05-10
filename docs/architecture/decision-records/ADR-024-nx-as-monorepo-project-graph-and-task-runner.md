---
status: accepted
date: 2026-05-08
decision-makers: [alex-on-java]
---

# Adopt Nx as the Monorepo Project Graph and Task Runner

## Context and Problem Statement

Two image-building apps (`apps/frontend/web-app`, `apps/platform/convergence-checker`) and one local Python tool (`tools/k8s-validation`) live in the repository. Stated growth trajectory: "significantly more apps, plus shared libs once infra is established." The current CI shape is a duplicated `build / build` + `build-convergence-checker` pair, hardcoded in `.github/workflows/`. Adding a new app means a CI YAML edit *and* a branch-protection edit (the required-checks list expands by one). That pair fails the 10× litmus: at ten apps, every "checkout → buildx → login → build-push" stanza is duplicated ten times, and every required-check rename is a manual branch-protection PATCH.

A second class of duplication lives between local and CI. Developers run `uv run pytest` and `docker build` ad-hoc, by reading the Dockerfile path; CI runs the same commands via separate workflow files. There is no single command shape that works in both.

Two structural debts compound. First, `.pre-commit-scripts/lint-python-projects` is a 90-line bash router (the artefact of [ADR-017](ADR-017-python-project-linting-via-poe-router.md)) that exists only because, at the time, the repo had no project graph and task runner. Second, the `build / build` + `build-convergence-checker` required-checks pair forces a branch-protection edit on every app addition.

A project graph and task runner solves all of these at once: it becomes the source of truth for which projects exist and drives `nx affected` for CI gating. It exposes uniform local commands, can absorb the lint router, and lets branch protection pin a single aggregator check that does not change as projects are added.

## Decision Drivers

- **10× scalability across more apps and shared libs.** Adding a project must be a single `project.json` write, with no CI YAML or branch-protection edits.
- **Local-CI command symmetry.** Developers and CI must invoke the same target by the same name (`nx run <project>:<target>`), so the local debug loop matches the CI failure mode.
- **Cross-project dependency edges (forward-looking).** Once shared libs exist, build-then-publish ordering must be expressible in the graph (`dependsOn`), not re-encoded in CI YAML.
- **Cacheability where it earns its keep.** Lint and test outputs are deterministic file→file work; image builds are not. The runner must allow per-target opt-in caching and not lie about side-effecting targets.
- **Complete-result developer experience (DX) inherited from ADR-017.** The result of every project must be surfaced even when one fails; silent skips are unacceptable (the LL-0020 class).
- **Project policy: explicit over implicit.** Targets, inputs, and pin sets are deliberate choices, not framework defaults.

## Considered Options

1. Stay with the current shape: duplicated jobs, hardcoded app lists, a custom bash lint router.
2. A `.github/build-apps.yml` catalog feeding `dorny/paths-filter` to drive a CI-only matrix.
3. **Adopt Nx as project graph and task runner**, with every target shelling out via `nx:run-commands` (no language plugins).
4. Adopt Nx with language plugins (`@nx/python`, `@nx/docker`, eventual `@nx/js`).

## Decision Outcome

**Option 3: Nx as project graph and task runner only, every target via `nx:run-commands`.**

Three day-one projects:

- `apps/frontend/web-app`: `build-image`, `publish-image`.
- `apps/platform/convergence-checker`: `lint`, `test`, `build-image`, `publish-image`.
- `tools/k8s-validation`: `lint`, `validate-gitops`. (No image; not deployed; still a Python project that needs linting.)

Project names match the directory leaf (`web-app`, `convergence-checker`, `k8s-validation`); no `@scope/...` prefixes, no path-style names. `dependsOn` between projects is empty on day one (no shared lib yet).

The shape is deliberately minimal:

- **No Nx language plugins.** Every target shells out to the underlying tool (`uv`, `poe`, `docker buildx`, `pytest`). Nx provides discovery, `affected` resolution, parallelism, and caching, not language-aware compilation. Revisit when a real frontend project lands.
- **No `namedInputs` in `nx.json`.** Inputs are declared inline in each `project.json`. Factor into `namedInputs` when a third project shares the same input shape; until then, the cost of the abstraction (a second place to grep) exceeds the benefit.
- **No `pnpm-workspace.yaml`.** Added the day a TS package needs it, not earlier. Placeholder files for hypothetical future state are out of policy.
- **`nxBail: false`** in `nx.json`. Preserves the complete-result invariant inherited from ADR-017; every project's target runs even when one fails.
- **`targetDefaults` cache policy.** `lint`, `test`, `validate-gitops` → `cache: true` (deterministic file→file work). `build-image`, `publish-image` → `cache: false` (the artefact lives in the docker daemon and in GHCR; Nx cannot honestly track that). The empirical cache hit on lint/test pays for Nx. Image-build recovery is covered by the buildx GHA cache (see ADR-026), without Nx caching at all.

Tooling pins:

- `mise.toml` adds `node = "v24.13.1"`, `pnpm = "10.30.1"`, and `prek = "0.3.13"` mirroring `~/.config/mise/config.toml`. Because mise requires concrete values, we mirror global; bumping the local pin is coupled to bumping global, and the `prek` pin gives CI exact parity with the local pre-commit binary.
- Root `package.json` declares one devDep: `"nx": "22.7.1"` (exact-pinned per [CQP-003](../../code-quality-policies/CQP-003-pin-external-versions.md)).
- The conftest TOML pin policy is extended to also cover `package.json`. Implementation introduces a parallel `policies/conftest/npm_dependency_pinning.rego` (with its own unit tests) and a separate `conftest-json` prek hook. The split exists because the TOML and JSON parsers in conftest are mutually exclusive within a single rule set. Adding the policy is a deliberate choice: an unpinned npm dep would otherwise be the single place in the repo where the pin discipline does not apply.

### Consequences

- **Good**: adding a project is a single `project.json` write. The CI matrix is derived from `nx show projects --affected --withTarget=publish-image --json`. Branch protection points at a static aggregator check (see ADR-026) that does not change as projects come and go.
- **Good**: the same `pnpm exec nx run convergence-checker:test` command works locally and in CI, so failures reproduce at the same terminal.
- **Good**: lint and test outputs are cached. On a branch with one Python file change, `nx affected -t lint` runs lint on one project, not three.
- **Good**: `nxBail: false` carries the complete-result invariant from ADR-017 forward without re-implementation.
- **Good**: future shared libs gain dependency-aware build ordering via `dependsOn` without revisiting this ADR.
- **Bad**: the project now requires `node` and `pnpm` as developer prerequisites. The `mise.toml` pins mitigate this; `mise install` reproduces the exact toolchain.
- **Bad**: a separate npm-pinning conftest policy is a second pin-policy file to keep aligned with the existing TOML one. Both are driven by the same regex shape (exact `==X.Y.Z`-equivalent), with unit tests on each.
- **Neutral**: `nx.json` is intentionally lean; `namedInputs` and `pnpm-workspace.yaml` are deferred until concrete drivers exist. Each will get its own ADR.

## Pros and Cons of the Options

### Stay with the Current Shape

- Good: zero migration cost.
- Bad: every new app demands two CI edits (workflow + branch protection) and a manual entry in the duplicated job set.
- Bad: no path to a uniform local-vs-CI command surface.
- Bad: the bash 5.1 idioms in the lint router remain a maintenance liability; adding a third Python project linearly grows the dispatch logic.

### `.github/build-apps.yml` Catalog Feeding `dorny/paths-filter`

- Good: single source of truth for the CI app list; closes the "hardcoded `DEPLOYABLE_APPS`" anti-pattern.
- Good: no new runtime added to developer machines.
- Bad: the catalog drives CI only; developers still run raw `uv run pytest` and `docker build`. Local-CI symmetry is unsolved.
- Bad: cross-app dependency edges (shared libs) cannot be expressed declaratively; they would have to be re-encoded in CI YAML.
- Bad: at the stated growth trajectory (more apps + shared libs), the YAML catalog grows to encode dependency ordering that the project graph encodes natively.

### Nx with Language Plugins (`@nx/python`, `@nx/docker`)

- Good: richer integrations (e.g., language-aware affected resolution).
- Bad: each plugin is another pinned dependency surface that must be updated in lockstep with the underlying tooling (`uv`, `docker`).
- Bad: language plugins encode opinions that may collide with project-owned `pyproject.toml` / `Dockerfile` decisions, producing a third source of truth.
- Bad: the current stack is Python + nginx-static; the value of plugins is bounded until a real TS frontend lands. Premature commitment.

## More Information

- Inputs are declared inline in each `project.json` rather than factored into `nx.json` `namedInputs`. The placement keeps the input declaration adjacent to the target it gates, so a change to project structure is reviewed in one file rather than two. Factoring into `namedInputs` earns its keep when a third project shares the same input shape; until then, the second place to grep costs more than it saves.
- The conftest TOML/JSON split is a choice between three options (extend the existing rego matcher, widen the hook's `files:` regex, or add a parallel rego policy file). Option three was chosen because conftest applies one parser per rule set, so a single rego matcher across both formats is infeasible without sacrificing unit-test fidelity. A new `npm_dependency_pinning.rego` ships with `npm_dependency_pinning_test.rego` covering all four NPM dependency groups.
- The `prek` mise pin is colocated with the Nx adoption because the prek-routed lint hook now invokes `nx`. CI must run the same prek version the local machine pins; otherwise binary-version skew between local and CI lints reproduces the silent-divergence class the project is structured to avoid.
