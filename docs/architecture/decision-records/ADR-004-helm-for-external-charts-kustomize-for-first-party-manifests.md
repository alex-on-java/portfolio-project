---
status: accepted
date: 2026-04-11
decision-makers: [alex-on-java]
---

# Use Helm for External Charts and Kustomize for First-Party Manifests

## Context and Problem Statement

This repository deploys both third-party operators and first-party platform/workload resources. Without a clear boundary, chart rendering logic, local patching logic, and ownership lines can become mixed, making upgrades and debugging harder over time.

The project needs a stable and explicit convention that scales with more applications and operators: external software should be consumed as upstream artifacts, while repository-owned manifests should be composed and patched with first-party tooling.

## Decision Drivers

- Keep upstream operator upgrades straightforward and low-maintenance
- Keep first-party manifest ownership explicit and reviewable in Git
- Avoid duplicated rendering mechanisms for repository-owned resources
- Preserve clear operational boundaries between vendor content and local content
- Prevent drift toward mixed templating patterns that are hard to audit
- Preserve vendor chart upgradeability without local inflated-manifest drift

## Considered Options

1. Helm for external charts, Kustomize for first-party manifests
2. Helm for everything
3. Kustomize-only, including `helmCharts`-style chart rendering

## Decision Outcome

**Option 1: Helm for external charts, Kustomize for first-party manifests.**

External operators are installed from upstream Helm chart repositories through ArgoCD ApplicationSets. Repository-owned resources are authored and layered with Kustomize bases/overlays/components.

### Consequences

- **Good**: external operator upgrades remain chart-version driven, close to upstream documentation, and easy to reason about.
- **Good**: first-party resources remain plain Kubernetes manifests plus explicit patches, improving review quality and local ownership.
- **Good**: operational boundaries are clear: chart values configure external software, Kustomize composes local software.
- **Good**: policy conformance can be mechanically verified (for example, no internal `Chart.yaml`, no `helmCharts` in first-party kustomizations).
- **Good**: avoids inflating vendor charts into local manifest trees, which would make upgrades brittle because generated manifests are not guaranteed to stay structurally stable across chart versions.
- **Bad**: two composition mechanisms exist in the repo, so contributors must know when each one is appropriate.
- **Neutral**: rendered stage-branch workloads may be applied from `path: .`, but they are still produced by Kustomize in promotion steps and remain policy-compliant.

## Pros and Cons of the Options

### Helm for External Charts + Kustomize for First-Party Manifests

See **Decision Outcome** above.

### Helm for Everything

- Good: single templating tool across all resources.
- Good: some teams already know Helm workflows well.
- Bad: first-party manifests become chart-shaped even when templating adds little value.
- Bad: reviewability drops when simple overlays become template logic.
- Bad: encourages coupling local manifest evolution to Helm-specific structure.

### Kustomize-Only (Including Chart Rendering via Kustomize)

- Good: one top-level composition tool for all resources.
- Good: local patch workflows remain consistent.
- Bad: vendoring/rendering external charts through Kustomize blurs ownership boundaries.
- Bad: upgrades become harder if generated chart output is treated as repo-owned baseline.
- Bad: external chart troubleshooting becomes less direct versus native Helm consumption.
- Bad: can create hidden complexity around chart rendering lifecycle and upgrade behavior.
