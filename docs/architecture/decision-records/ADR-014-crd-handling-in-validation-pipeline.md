---
status: accepted
date: 2026-04-16
decision-makers: [alex-on-java]
---

# Exclude CRDs from Rendering, Include for Schema Extraction

## Context and Problem Statement

CRD definitions appear in two contexts within the validation pipeline: as potential documents in rendered Helm output, and as the source material for kubeconform JSON schemas. These contexts have different requirements.

The 3 CRD-bearing Helm charts (cert-manager, argo-rollouts, kargo) store CRD definitions in `templates/`, gated behind values flags. A single `helm template` invocation can either include or exclude them depending on the flags passed. The pipeline must handle both uses deliberately.

## Decision Drivers

- CRD definitions are infrastructure scaffolding — they define API types, not application workloads. Resource-spec policies (Kyverno) don't apply to them, and kubeconform has no schema for CRD definitions themselves
- Including CRDs in rendered output creates an implicit coupling: future validators may misinterpret CRD definitions as resources to validate, producing false positives or confusing results
- The project principle "Including X is harmless" is not a valid justification — absence of harm is not a reason to include; presence of documented value is
- CRD `openAPIV3Schema` definitions are the authoritative source for kubeconform JSON schemas — they must be extracted, but that's a toolchain step, not a validation input

## Considered Options

1. Exclude CRDs from rendering, include via separate invocation for schema extraction
2. Include CRDs in rendering output
3. Single `helm template` invocation serving both rendering and schema extraction

## Decision Outcome

**Option 1: Two separate `helm template` invocations with different purposes.**

- **Rendering** (manifests for validation): `helm template <chart> <path> -f <values>` — standard invocation using project values. The rendered output does include CRDs when the values enable them (cert-manager's `crds.enabled: true`, kargo's `crds.install: true`) because ArgoCD applies rendered manifests directly and relies on the chart to create CRDs at deploy time. `_filter_crds()` in `rendering.py` strips `kind: CustomResourceDefinition` documents before the output feeds Kyverno and kubeconform — the filter is the load-bearing step that keeps CRD definitions out of validators that don't handle them.
- **Schema extraction** (CRD-to-JSON conversion): `helm template --include-crds --set <crd-flags> <chart> <path>` — separate invocation with CRD-enabling flags. The output is parsed for `kind: CustomResourceDefinition`, and each CRD's `openAPIV3Schema` is converted to a kubeconform-compatible JSON schema.

### Consequences

- **Good**: rendering output contains only validatable resources — no CRD definitions that validators would skip or mishandle.
- **Good**: schema extraction is an explicit pipeline stage with its own configuration (`crd_helm_sets` in `settings.yaml`), making the CRD sources visible and auditable.
- **Good**: validation input is the non-CRD subset of what ArgoCD deploys. CRDs are filtered because there are no schemas or policies to validate CRD definitions against; the custom resources that reference those CRDs are validated against schemas extracted upstream from the same `openAPIV3Schema` definitions.
- **Bad**: two `helm template` invocations per CRD-bearing chart instead of one. The performance cost is negligible (cached charts, < 1s total).
- **Neutral**: `_filter_crds()` runs on every rendering invocation and is the primary mechanism that keeps CRDs out of validation input. The design treats rendering and filtering as orthogonal stages — values drive what the chart emits (for ArgoCD's deployment needs), the filter drives what validators see.

## Pros and Cons of the Options

### Include CRDs in rendering output

- Good: simpler implementation — one invocation per chart.
- Bad: CRD definitions in the output are noise. Kyverno skips them (no matching rules), kubeconform skips them (`-skip CustomResourceDefinition`). Their presence adds no validation value.
- Bad: a future contributor adding a validator might not know to skip CRDs, leading to false positives.
- Bad: "including them is harmless" is the exact reasoning pattern the project principles reject.

### Single invocation for both rendering and schema extraction

- Good: fewer subprocess calls.
- Bad: conflates two concerns with different output requirements — rendering needs project values without CRD flags, schema extraction needs CRD flags without project values.
- Bad: the output would need to be split post-hoc (CRDs to schema pipeline, non-CRDs to validators), adding parsing complexity that separate invocations avoid.
