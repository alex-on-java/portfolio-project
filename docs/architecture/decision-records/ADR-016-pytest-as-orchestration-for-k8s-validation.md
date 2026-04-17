---
status: accepted
date: 2026-04-16
decision-makers: [alex-on-java]
---

# pytest as Orchestration Layer for K8s Manifest Validation

## Context and Problem Statement

The K8s validation engine renders all project manifests (Helm charts and Kustomize overlays) and feeds them to independent validators: Kyverno for policy enforcement, kubeconform for schema validation. The orchestration layer must manage three concerns: rendering all manifests once (expensive subprocess calls to `helm template` and `kubectl kustomize`), distributing the output to N validators, and reporting results with enough detail to locate violations.

Which tool should orchestrate this pipeline?

## Decision Drivers

- **10x scalability**: the architecture must handle 10x the current manifest and chart count without redesign. Shell-script orchestration, ad-hoc file scanning, and per-chart manual wiring are rejected on this basis.
- **Render-once semantics**: manifests should be rendered exactly once per run, regardless of how many validators consume them. Rendering is the most expensive step (subprocess calls to Helm and kubectl).
- **N+1 validator extensibility**: adding a new validator (e.g., kube-linter) should require adding one test file, not modifying orchestration logic.
- **CI integration**: the orchestration tool should be a standard CI entry point that requires no custom wrapper scripts.
- **DX**: failure output should identify the specific resource, validator, and rule that failed, without requiring the developer to parse raw CLI output.

## Considered Options

1. pytest with session-scoped fixtures
2. Shell scripts / Makefile
3. Custom Python CLI

## Decision Outcome

**Option 1: pytest with session-scoped fixtures.**

Session-scoped fixtures give natural render-once lifecycle: the rendering fixture runs once per test session, caches the output paths, and every test function (across all validator modules) receives the same rendered manifests. Adding a validator means adding a test file that depends on the rendering fixture — pytest's test discovery handles the rest.

### Consequences

- **Good**: render-once is a natural consequence of session-scoped fixtures, not a manual caching mechanism. The fixture runs once, subsequent consumers get the cached result.
- **Good**: N+1 extensibility via test discovery — a new `<validator>_validator.py` file is automatically picked up without modifying any orchestration code.
- **Good**: pytest is the standard test runner in CI pipelines. `pytest tools/k8s-validation/` is the only command needed — no wrapper scripts, no custom entrypoints.
- **Good**: pytest's assertion introspection and `-v` output provide resource-level failure reporting without custom formatting code.
- **Bad**: pytest is unconventional as a pipeline orchestrator — a developer expecting unit tests may be surprised to find infrastructure rendering in fixtures.
- **Bad**: session-scoped fixtures have ordering constraints (session > module > function) that require understanding pytest's fixture lifecycle.
- **Neutral**: Dynaconf settings integration (chart paths, schema locations, policy paths) works identically in pytest fixtures as in any Python code.

## Pros and Cons of the Options

### Shell scripts / Makefile

- Good: no Python dependency for the orchestration layer.
- Good: familiar to infrastructure engineers.
- Bad: render-once requires explicit temp-directory management and variable passing between scripts.
- Bad: adding a validator means modifying the orchestration script — no automatic discovery.
- Bad: fails the 10x litmus test — at 10x charts and validators, shell scripts become brittle: quoting issues, error handling gaps, and subprocess coordination compound.
- Bad: CI integration requires a wrapper that sets up paths, installs tools, and manages cleanup.

### Custom Python CLI

- Good: full control over rendering lifecycle and output format.
- Good: can be designed for 10x from the start.
- Bad: reimplements what pytest already provides: test discovery, fixture lifecycle, assertion reporting, CI integration.
- Bad: a custom CLI is a maintenance surface that must be tested itself — pytest's test infrastructure is already tested.
- Bad: N+1 extensibility requires building a plugin system, which is what pytest already is.

## More Information

The reasoning behind this decision originates from the feature charter for the K8s validation engine. The feature charter is an ephemeral development artifact — it is injected via hooks during development but is not committed to the repository. This ADR preserves the architectural motivation that would otherwise be lost when the charter is removed.
