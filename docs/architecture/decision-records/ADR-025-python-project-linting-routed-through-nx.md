---
status: accepted
date: 2026-05-08
decision-makers: [alex-on-java]
supersedes: [ADR-017]
---

# Python Project Linting Routed Through Nx (Supersedes ADR-017)

## Context and Problem Statement

[ADR-017](ADR-017-python-project-linting-via-poe-router.md) introduced a custom bash router (`.pre-commit-scripts/lint-python-projects`). It walked staged files up to their nearest-ancestor `pyproject.toml`, deduplicated the project set, and dispatched `uv run --frozen poe lint` in each project directory in parallel. That decision was correct *for its context*: the repo had no graph-aware task runner, and the router's job (project discovery, parallel dispatch, complete-result aggregation) had no off-the-shelf substitute.

The context has now changed. [ADR-024](ADR-024-nx-as-monorepo-project-graph-and-task-runner.md) introduces Nx as the project graph and task runner. Its `affected` resolution, `--parallel` execution, and `nxBail: false` complete-result behaviour cover *exactly* the three jobs the router was built to do. Continuing to maintain the router would mean carrying load-bearing bash idioms for a problem the runtime now solves natively. Those idioms include the `if`-wrapped `wait -n -p` pattern, arithmetic that avoids zero-crossing under `set -e`, and the bash ≥ 5.1 version guard.

This supersession is **a context change, not a flaw in the original decision**. The ADR-017 drivers (exact pin policy, 10× scalability across Python projects, complete-result DX, machine-checkable pin hygiene) remain valid in full. The custom router was the best-available solution before Nx landed in the monorepo, and Nx now provides the same drivers natively at lower carrying cost.

## Decision Drivers

- **The ADR-017 drivers still apply.** Four constraints carry over: exact `==X.Y.Z` pins via `uv.lock`; 10× scalability across Python projects; complete-result DX (the result of every project surfaces even when one fails); and machine-checkable pin hygiene via conftest. Any successor must satisfy all four.
- **Single source of truth for *which* linters run.** The list of linters per project lives in `pyproject.toml` `[tool.poe.tasks]`. The orchestrator must not become a second place to declare "ruff, mypy, pylint, …".
- **Local-CI command symmetry.** The same invocation must work in pre-commit, in `prek run --all-files`, and in the CI `lint` job.
- **Reduced bespoke surface area.** A 90-line bash router with bash-version-pinned idioms is a maintenance liability the day a substitute exists.

## Considered Options

1. Keep ADR-017's bash router unchanged; narrow the scope of Nx to `build-image` / `publish-image` only.
2. Replace `poe` entirely; have the Nx `lint` target call ruff/mypy/pylint directly.
3. **For each project, wrap the `poe lint` task as an Nx target**; rewire the prek hook to a thin shell-out invoking `nx affected -t lint --files=<csv>`.
4. Move CI lint out of prek into a dedicated Nx-driven CI job, parallel to `build`.

## Decision Outcome

**Option 3.** Nx target `lint` calls `uv run --frozen poe lint` per project. The prek hook invokes `nx affected -t lint --files=<csv>` via a thin shell wrapper. `prek run --all-files` remains the CI lint entry.

Each Python project (`convergence-checker`, `k8s-validation`) declares an Nx `lint` target running `uv run --frozen poe lint` from `{projectRoot}`. The contract is **Nx → poe → tool**: Nx owns discovery and parallelism, poe owns the linter sequence, the linter runs as configured in `pyproject.toml`. Adding a linter is a single `[tool.poe.tasks]` edit to one `pyproject.toml`; Nx and prek touch nothing.

A shell wrapper bridges the prek hook to Nx because the Nx `--files` flag wants comma-separated values, not space-separated argv. The wrapper (`.pre-commit-scripts/nx-affected-lint`) is intentionally minimal:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
# trap from project bash-script standards omitted for brevity
[[ $# -eq 0 ]] && exit 0
joined="$1"; shift
for f in "$@"; do joined="${joined},${f}"; done
exec pnpm exec nx affected -t lint --files="$joined"
```

It exists for one reason: to bridge the prek argv convention to the Nx CSV-flag convention. The wrapper disappears the day Nx accepts argv natively (the bridge is mechanically removable; the contract is the Nx target).

The `convergence-checker:test` target follows the same Nx → poe → tool contract. A new `[tool.poe.tasks].test = "pytest"` task is added to `apps/platform/convergence-checker/pyproject.toml`. With this in place, `nx run convergence-checker:test` invokes `uv run --frozen poe test` rather than `pytest` directly. Contract symmetry (every Nx target hits poe, poe hits the tool) is more valuable than saving one process hop.

The `k8s-validation:validate-gitops` target is named `validate-gitops`, **not** `test`: the project is a runner for kubeconform/kyverno over `gitops/**`, not a unit-tested library. Its inputs span two surfaces. First, the runner's source: `src/**`, `validators/**`, `pyproject.toml`, `uv.lock`, `settings.yaml`. Second, workspace-rooted paths: `{workspaceRoot}/gitops/**` and `{workspaceRoot}/mise.toml`, where the latter pins kubeconform and kyverno binaries.

CI invocation: the `lint` workflow job runs `prek run --all-files`, which executes the rewired `lint-python-projects` hook, which shells out to `nx affected -t lint --files=<csv>`. No separate "Nx-driven CI lint job" is added. prek is already the CI lint entry, the hook is now Nx-backed, and Nx caching dedupes repeated runs across the hooks of the lint workflow.

The `validate-k8s-manifests` hook is rewired symmetrically: its `entry` becomes `pnpm exec nx run k8s-validation:validate-gitops`, with `pass_filenames: false`. Because the validator is holistic (it does not consume per-file argv), cache invalidation is driven directly by the declared `inputs` of the `validate-gitops` target: `gitops/**`, validator source, and mise pins.

The bash router (`.pre-commit-scripts/lint-python-projects`) is removed as part of this transition; the prek hook owns the bridge to Nx, and no other call site is left needing the router.

ADR-017 itself is not modified: it remains a permanent-history-artefact recording the decision *as it was made*. The README index is updated to reflect supersession.

### Consequences

- **Good**: the ADR-017 drivers are preserved without the router. Pin policy still lives in `pyproject.toml`/`uv.lock`. 10× scalability still holds: adding a Python project is a `project.json` write plus a `pyproject.toml`. Complete-result is preserved by `nxBail: false`. Hygiene checks are unchanged: conftest still policies `pyproject.toml`, and ADR-024 extends it to `package.json`.
- **Good**: ~90 lines of load-bearing bash deleted. The bash ≥ 5.1 version guard, the `wait -n -p` idioms, and the PID-to-index mapping are all retired with no functional regression.
- **Good**: the convergence-checker test gap in CI is closed by a parallel `test` job (also Nx-driven). Tests existed locally but never ran on PRs; they do now.
- **Good**: the `k8s-validation` project gains lint coverage for the first time, having previously sat outside the bash router's scope or been lint-checked ad-hoc.
- **Bad**: a new shell wrapper (`nx-affected-lint`) exists to bridge prek argv to Nx CSV. It is short, has one reason to change (Nx accepting argv), and follows the project's bash-script standards (`set -Eeuo pipefail`, the canonical trap from CLAUDE.md).
- **Neutral**: lint stays inside prek as the CI entry rather than becoming a dedicated Nx-affected CI job. The existing CI lint shape is a single `prek run --all-files` invocation covering actionlint, zizmor, shellcheck, conftest, and now Nx-backed Python lint. Preserving that symmetry is preferred over a parallel job that would duplicate setup-nx and checkout cost.

## Pros and Cons of the Options

### Keep ADR-017's Router; Narrow Nx to Image Builds Only

- Good: smallest blast radius on the existing lint shape.
- Bad: carries the bash 5.1 idioms forward indefinitely. The ADR-017 drivers (10×, complete-result, pins) are now satisfiable natively, and refusing to take that win is a "we built it ourselves so we keep it" anti-pattern.
- Bad: the YAGNI argument cuts the other way. Two parallel orchestrators (Nx for builds, custom bash for lints) is more complexity, not less.

### Drop poe; Nx Calls ruff/mypy/pylint Directly

- Good: shorter call chain (Nx → tool, no poe hop).
- Bad: makes Nx a second source of truth for *which* linters run per project, defeating the ADR-017 pin discipline. Every linter addition becomes a coordinated edit across `pyproject.toml` and `project.json`.
- Bad: loses the poe `ignore_fail = "return_non_zero"` semantics for in-project linter sequencing. Those semantics would have to be re-encoded as N Nx targets per project.

### Move CI Lint Out of prek into a Dedicated Nx-Affected CI Job

- Good: maximum parallelism on CI (lint matrix per affected project).
- Bad: duplicates checkout and setup-nx setup on every entry; for two Python projects the orchestration cost exceeds the parallelism gain.
- Bad: prek already covers actionlint, zizmor, shellcheck, conftest in one CI step. Carving out only Python lint into a separate job creates two CI lint surfaces with two different invocation shapes.

## More Information

ADR-017 is preserved verbatim. The supersession is recorded by the frontmatter of this ADR (`supersedes: [ADR-017]`) and by an index entry rewrite in `docs/architecture/decision-records/README.md`. The intent is that a future reader can reconstruct the original reasoning without it being rewritten in light of the new context.

The decision applies to the two Python projects that exist on day one (`apps/platform/convergence-checker`, `tools/k8s-validation`). It does not extend Nx to shell-script linting (shellcheck) or YAML linting (actionlint, conftest, kyverno). Those remain inside prek, since they are not per-project work and the per-project framing Nx provides has no value there.
