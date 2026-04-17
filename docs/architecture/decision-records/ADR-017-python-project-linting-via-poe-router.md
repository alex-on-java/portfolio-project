---
status: accepted
date: 2026-04-17
decision-makers: [alex-on-java]
---

# Python Project Linting via Project-Owned poe Tasks Dispatched by a Pre-Commit Router

## Context and Problem Statement

Python linters split into two families. Syntax-only linters (ruff) succeed inside pre-commit's per-hook isolated venv — they read files as text, without needing the project's import graph. Typed linters (mypy, pylint) fail there: they must resolve `import k8s_validator.foo` against the project's actual package layout, which the isolated venv does not contain. Patching this with `additional_dependencies: [-e ./tools/k8s-validation, pyyaml, dynaconf, pytest]` reintroduces every project's dependencies into `.pre-commit-config.yaml` — a second source of truth for the pin set, updated out of band with `uv.lock` and unversioned in practice (`pyyaml` rather than `pyyaml==6.0.3`).

A second Python project is expected in the near term. The `additional_dependencies` approach scales linearly with (Python projects × linters), and so does the pin-freshness hazard.

## Decision Drivers

- **Project policy: exact `==X.Y.Z` pins for every external dependency.** `additional_dependencies` creates a second place to declare those pins, which drifts from `uv.lock`.
- **10× scalability across multiple Python projects.** Per-project hook blocks grow linearly; adding a linter is a YAML edit in every block. The architecture must absorb the second project with zero `.pre-commit-config.yaml` edits.
- **Complete-result DX.** Every linter must run every time. Every project's result must be surfaced. Silent skips — the class that produced [LL-0020](../../lessons-learned/LL-0020-kyverno-rule-name-maxlength-silent-failure.md) — are unacceptable.
- **Machine-enforceable pin hygiene.** The pin policy must be verifiable via conftest, not left to human review.

## Considered Options

1. Keep per-hook isolated venvs; add `-e ./tools/k8s-validation` and runtime deps to each hook's `additional_dependencies`.
2. One dedicated pre-commit hook block per Python project, each invoking that project's linters explicitly.
3. A single pre-commit router hook that dispatches to each project's own `uv run --frozen poe lint` task.

## Decision Outcome

**Option 3: router + project-owned `poe` tasks.**

Each Python project owns its lint commands in `[tool.poe.tasks]`. The pre-commit layer has one `lint-python-projects` hook wired to `.pre-commit-scripts/lint-python-projects`. The router walks each staged file up to its nearest-ancestor `pyproject.toml`, deduplicates the set, and runs `uv run --frozen poe lint` in each project directory in parallel.

Two invariants enforce the complete-result guarantee:

- `poe lint` is declared as a sequence with `ignore_fail = "return_non_zero"`, not the default `sequence` (which aborts on first failure). Every linter runs every time.
- The router wraps every `wait -n -p finished` call in `if ...; then ...; else ...; fi`, preventing `set -e` from exiting the dispatch loop on the first failing child. Every project's exit code is captured; every project's log is printed in deterministic project order.

A third, independent guardrail — the new `pyproject_pinning.rego` conftest rule — makes the pin policy machine-checkable: ranged specifiers, multi-clause specifiers, inline comments, and direct-URL requirements are all rejected by a unit-tested regex.

### Consequences

- **Good**: dependency declarations live in exactly one place per project (`pyproject.toml`/`uv.lock`), and the pin-policy conftest rule watches that one place.
- **Good**: adding a Python project requires zero `.pre-commit-config.yaml` edits — the router discovers it via its `pyproject.toml`.
- **Good**: adding a linter (e.g., future `kube-linter`) is a single atomic edit — a new entry in `[tool.poe.tasks]` appended to the `lint` sequence of one project. No pre-commit touch.
- **Good**: parallelism across projects uses `wait -n -p` (bash ≥ 5.1); per-child exit codes and PID attribution are direct, no filesystem round-trips or marker files.
- **Good**: signal exits propagate unchanged — Ctrl-C produces exit 130, not lint-failure 1.
- **Bad**: the router script carries load-bearing idioms (the `if`-wrapped `wait -n -p`, arithmetic that avoids zero-crossing pitfalls with `set -e`, PID-to-index mapping). Mitigated by explicit invariants in the script and by the negative-path verification steps in the implementing commit message.
- **Bad**: `[[tool.mypy.overrides]] module = "dynaconf" ignore_missing_imports = true` is module-wide. Missing-stub errors for every `dynaconf.*` import are silenced, not only the specific import site. Accepted because the current import footprint is one line and `types-dynaconf` does not exist on PyPI; revisit when either condition changes.
- **Neutral**: the router depends on bash ≥ 5.1. A version guard aborts early with a clear message on older shells (notably macOS's default `/bin/bash` 3.2).

## Pros and Cons of the Options

### Per-hook isolated venvs with `additional_dependencies`

- Good: no new scripts; uses pre-commit's built-in per-hook dependency management.
- Bad: duplicates every runtime and dev dependency across `additional_dependencies` — a second source of truth that drifts from `uv.lock`.
- Bad: in practice the duplicated entries are unversioned; pinning them to `==` would require hand-copying the full resolved set on every bump.
- Bad: fails the 10× litmus test — each new Python project multiplies YAML entries; each new linter multiplies hook blocks.

### One hook block per project

- Good: explicit; each project's linters are visible in `.pre-commit-config.yaml`.
- Good: no new script; parallelism is delegated to pre-commit's built-in scheduler.
- Bad: linear YAML growth across both dimensions (projects × linters). Every combination is a manual edit.
- Bad: the pin-duplication hazard from option 1 persists whenever a linter needs runtime imports.

## More Information

The router's load-bearing idioms — `if wait -n -p finished; then ... else ... fi`, arithmetic that avoids zero-crossing under `set -e`, the bash ≥ 5.1 version guard — are documented by the invariants in the script itself and exercised by the verification steps recorded in the implementing commit message. Deviations from those idioms are expected to re-introduce the silent-skip class of bug captured by LL-0020.
