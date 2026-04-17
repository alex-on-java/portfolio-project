---
status: accepted
date: 2026-04-16
decision-makers: [alex-on-java]
---

# Clean Generated CRD Schemas Before Each Generation Run

## Context and Problem Statement

The CRD schema pipeline generates JSON schemas from Helm charts and release assets into `.cache/generated-crd-schemas/`. When a CRD source is removed (e.g., a chart drops a CRD, or a release entry is deleted from `settings.yaml`), the previously generated schema file persists in the output directory. The coverage gate checks "does a schema file exist for this GVK?" — a stale file satisfies that check, masking the fact that the schema source no longer exists.

This creates a silent regression path: remove a CRD source, the old schema stays, coverage gate passes, and the schema drifts from the actual chart version until something breaks downstream.

## Decision Drivers

- Stale schemas are invisible — no mechanism detects that a schema file no longer corresponds to a configured source
- The coverage gate is the project's primary defense against schema gaps; stale files undermine its reliability
- Generated CRD schemas are cheap to reproduce — the input (cached Helm charts and release assets) is already on disk
- Downloaded assets (`.cache/helm-charts/`, `.cache/release-assets/`, `.cache/k8s-schemas/`) are version-keyed and should NOT be cleaned — they serve a different lifecycle

## Considered Options

1. Clean the generated CRD schema directory before each generation run
2. Smart invalidation by tracking source chart versions and selectively removing outdated files
3. Keep stale files with freshness metadata and timestamp-based checks

## Decision Outcome

**Option 1: Wipe `.cache/generated-crd-schemas/` before each `generate_all_schemas()` run.**

The directory is deleted and recreated on every invocation. This guarantees that only schemas from currently configured sources exist after a run.

A safety guard prevents `shutil.rmtree` from operating outside `.cache/` under the repository root — if `schemas.output_dir` is misconfigured to point elsewhere, the function raises `ValueError` rather than deleting the wrong directory.

### Consequences

- **Good**: stale schemas cannot persist — every run produces exactly the schemas that the current configuration defines.
- **Good**: the coverage gate becomes a reliable signal — if a GVK has no schema, it's genuinely missing, not masked by a leftover file.
- **Good**: the safety guard prevents catastrophic deletion from misconfigured settings — a concrete defense against the class of bug where a settings-derived path feeds `shutil.rmtree`.
- **Bad**: every test run regenerates all CRD schemas even if nothing changed. Cost is negligible at current scale (see benchmarks below).
- **Neutral**: downloaded assets (Helm charts, release assets, K8s schemas) are unaffected — they use a different directory and a different lifecycle (version-keyed, download-once).

### Confirmation

The stale schema cleanup is verified by a test: place a fake schema file in the output directory, run the generation pipeline, confirm the file is gone. The safety guard is verified by temporarily misconfiguring `schemas.output_dir` and confirming `ValueError` is raised.

## Pros and Cons of the Options

### Smart invalidation by tracking source chart versions

- Good: avoids regenerating unchanged schemas.
- Bad: requires a manifest of "what was generated from what" — adds a new state file to maintain.
- Bad: the invalidation logic must account for chart version changes, CRD additions/removals within a chart, and release asset URL changes. Edge cases compound.
- Bad: saves milliseconds on a sub-second operation while adding meaningful complexity.

### Keep stale files with freshness metadata

- Good: preserves cache for unchanged sources.
- Bad: requires timestamp or hash metadata per file — another state tracking mechanism.
- Bad: does not solve the core problem — a stale file with valid metadata still passes the coverage gate if the source was removed.
- Bad: adds complexity without eliminating the failure mode that motivated this decision.

## More Information

### Regeneration Cost Benchmarks

| Scale | CRDs | Schemas | Conversion | Write | Total | Output Size |
|-------|------|---------|------------|-------|-------|-------------|
| Current | 7 | 11 | 24ms | 65ms | 88ms | 3.4MB |
| 10x (realistic mix) | 100 | 157 | 383ms | 1.11s | 1.49s | 56.4MB |
| Worst case (310 large) | 310 | 620 | 2.7s | 12.9s | 15.6s | 560MB |

The 10x realistic scenario completes in 1.5s. Regeneration cost is negligible compared to the `helm template` + `kubectl kustomize` rendering that precedes it in the pipeline.

### Scope of Cleanup

Only `.cache/generated-crd-schemas/` is cleaned. The following directories are explicitly NOT cleaned:

- `.cache/helm-charts/` — downloaded chart tarballs, version-keyed
- `.cache/release-assets/` — downloaded CRD YAML files, version-keyed
- `.cache/k8s-schemas/` — downloaded K8s builtin schemas, version-keyed

These are download caches with a "download once, use forever" lifecycle. Cleaning them would violate the offline-after-initial-setup requirement.
