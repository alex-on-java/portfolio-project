---
status: accepted
date: 2026-07-01
decision-makers: [alex-on-java]
supersedes: [ADR-015]
---

# Per-Session Generated CRD Schema Directories

## Context and Problem

ADR-015 chose to clean `.cache/generated-crd-schemas/` before each schema generation run. That protected the coverage gate from stale schema files. If a CRD source disappeared from `settings.yaml`, the next run deleted the old output and forced the missing schema to surface.

That lifecycle had a different failure mode. The output directory was shared mutable generated state under the repository. Two validation sessions could overlap: one run might generate schemas and hand that path to kubeconform while another run deleted and recreated the same directory. A downstream failure would look like a kubeconform or schema problem, but the real cause would be the validation runner deleting shared state that another process was still using.

The validation suite needs both properties. It must reject stale generated CRD schemas, and it must be safe when local terminals, pre-commit hooks, CI jobs, or agents run validation at the same time.

## Decision Drivers

- Stale generated schemas must not satisfy the coverage gate.
- Validation checks can run concurrently and must produce reliable evidence.
- Generated CRD schemas are per-run output, not a long-lived version-keyed cache.
- Version-keyed download caches should remain shared because they are immutable enough for this workflow and expensive to fetch repeatedly.
- The pytest orchestration model from ADR-016 should keep owning per-session paths and pass them to downstream validators.

## Decision

Generated CRD schemas use a caller-provided per-session output directory. A pytest fixture creates a session temporary directory with `tmp_path_factory.mktemp("crd-schemas")` and passes that path to `generate_all_schemas(...)`. The generator no longer reads `settings.schemas.output_dir`, and `settings.yaml` no longer declares a generated CRD schema output path.

Stale-schema protection moves from deleting a shared directory to rejecting a non-empty caller-provided directory. `generate_all_schemas(...)` creates the directory if needed, then raises if any entry already exists. A run therefore starts from an empty output directory without deleting state that another run may still be reading.

The version-keyed caches stay shared:
- `.cache/helm-charts/`
- `.cache/release-assets/`
- `.cache/k8s-schemas/`

Those directories cache downloaded inputs by chart, release, or Kubernetes version. They are not the generated CRD schema output handed to kubeconform for one validation session.

## Options Considered

1. Keep cleaning the shared `.cache/generated-crd-schemas/` directory.
   That preserved freshness but made overlapping runs unsafe, and the design assumed one validation run at a time. That assumption is too weak for local agent sessions and pre-commit workflows, where repeated or parallel checks are normal.

2. Use a per-session generated schema directory with an empty-directory precondition.
   This preserves freshness without cross-run deletion. The caller gives the generator an empty path, and the generator refuses to append to existing contents. That keeps the ADR-015 stale-schema protection while changing the ownership of the generated output.

3. Keep the shared directory and add locking around generation and validation.
   Locking would avoid deletion races only if every reader and writer held the same lock for the whole lifetime of the downstream kubeconform read. That adds coordination to the validation path and makes the generated directory look like durable shared state. The simpler model is to make the generated output private to one pytest session.

## Consequences

### Good

- Concurrent validation runs no longer delete generated CRD schemas from another run.
- Stale schema protection remains explicit. A non-empty output directory is an error instead of a place where old and new schemas can mix.
- `settings.yaml` no longer exposes a repository-local generated output path that future callers might treat as durable state.
- The design follows ADR-016: pytest owns session lifecycle, and validators consume paths from fixtures.

### Neutral

- Each validation session regenerates CRD schemas into its own temporary directory.
- The project already accepted (ADR-014) regeneration cost as small relative to the rendering and validation pipeline.
- Shared download caches remain in the repository cache tree. This decision changes only the generated CRD schema output and leaves version-keyed download inputs untouched.

## Related Records

- [ADR-014](ADR-014-crd-handling-in-validation-pipeline.md)
- [ADR-015](ADR-015-schema-lifecycle.md)
- [ADR-016](ADR-016-pytest-as-orchestration-for-k8s-validation.md)
