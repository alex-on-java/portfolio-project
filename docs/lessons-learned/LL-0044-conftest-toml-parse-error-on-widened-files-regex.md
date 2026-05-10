# LL-0044: Conftest Applies One Parser per Rule Set, Precluding Mixed-Format Policies

## Summary

Conftest selects exactly one parser per invocation, and the parsed input shape is fixed before any rego rule runs. A single rego policy directory therefore cannot validate both `*.toml` and `*.json` inputs without sacrificing unit-test fidelity. Extending pin coverage from `pyproject.toml` to `package.json` requires a parallel rego policy file with its own tests and its own hook, not a widened existing rule.

## What Happened

The TOML pin policy in `policies/conftest/pyproject_pinning.rego` enforced exact pinning for `pyproject.toml` dependencies. With the nx adoption recorded in [ADR-024](../architecture/decision-records/ADR-024-nx-as-monorepo-project-graph-and-task-runner.md), `package.json` entered the repo. Pin discipline had to extend with it; otherwise the npm dep would become the single unpinned surface. Two natural-looking extensions present themselves: teach the existing rego matcher to handle both shapes, or widen the `files:` regex of the existing hook. Both fail against the conftest loading model.

## The Three Options and Why Two Fail

1. **Extend `pyproject_pinning.rego` with format-detection logic.** Rejected. Hook configuration selects the parser, not the rule. To unit-test the matcher, one would have to fake both a parsed-TOML and a parsed-JSON input shape under one `package main`. In production the hook still passes a single shape per run. Format detection inside rego is fiction in this architecture.
2. **Widen the `files:` regex of the existing TOML hook to also match `package.json`.** Rejected. A widened regex would feed JSON bytes to the TOML parser, because the parser is fixed by the `--parser` flag (or inferred from extension). Parse errors result, not policy decisions.
3. **Add a parallel rego policy file with its own unit tests, registered as a separate prek hook with `--parser json`.** Chosen. Each format gets its own policy, its own tests, and its own hook. The repo applies this for `package.json` via `policies/conftest/npm_dependency_pinning.rego` plus the `conftest-json` entry in `.pre-commit-config.yaml`.

## Operational Consequence

Pin discipline costs N policy files for N file formats. The repo already carries this cost across YAML, TOML, Dockerfile, and JSON hooks; the `package.json` addition extended an existing pattern rather than introducing a new one. Repos that police multiple formats pay the cost; repos with a single format (only `pyproject.toml`, for example) pay nothing extra.

## Adoption Rule

For each new file format that needs policy coverage:

- Add a parallel rego policy file (`policies/conftest/<format>_<topic>.rego`) with its own `_test.rego` companion.
- Register a separate prek hook with the correct `--parser` flag and a `files:` regex scoped to that format alone.
- Resist widening an existing `files:` regex across formats. The parser, not the rule, decides what shape the rule sees.

## How to Detect

A conftest policy that appears to "skip" a file is being fed the wrong parser. The same is true for a policy that reports parse-time failures on a file newly added to the `files:` regex of a hook. Verify that the `--parser` flag matches every extension the regex admits; if it does not, split the hook.
