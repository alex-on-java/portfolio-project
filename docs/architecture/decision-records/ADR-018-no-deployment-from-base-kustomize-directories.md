---
status: accepted
date: 2026-04-17
decision-makers: [alex-on-java]
---

# No Deployment From Base Kustomize Directories (Interim)

## Context and Problem Statement

[ADR-014](ADR-014-crd-handling-in-validation-pipeline.md) anchors the validation engine on a single invariant: the set of manifests validated must faithfully represent what ArgoCD deploys. For a Kustomize layout split into `base/` components and `overlays/<env>/` consumers, honouring that invariant rigorously requires deriving the deployed path set from the live `Application` and `ApplicationSet` resources — resolving generators, template expansions, and chained sources to reach the concrete `spec.source.path` values. That traversal needs bespoke code that does not yet exist.

Meanwhile, `discover_kustomize_overlays()` in `tools/k8s-validation/src/k8s_validator/discovery.py` treats the directory tree as the source of truth and skips any directory named `base`. This is sound only if no `Application`/`ApplicationSet` actually points at a `base/` as a deployment source; today that holds by convention, but nothing in the repository enforces it. A future `ApplicationSet` generator pointed at a `base/` path would deploy it, and the engine would fail to notice — exactly the class of drift ADR-014 was written to prevent.

## Decision Drivers

- ADR-014's invariant must not silently erode while AppSet-aware discovery is still on the TODO list.
- The assumption "no `base/` is used as a deployment source" must be **enforced by tooling**, not left as an unchecked convention.
- Kustomize `base/` directories are reusable components — treating them as deployment units blurs that role and undermines the overlay pattern.
- The project policy location is already standardised ([ADR-013](ADR-013-policy-location-architecture.md)); any mechanism chosen must slot into that split.

## Considered Options

1. **Full AppSet-aware discovery in the validation engine** — derive the deployed path set from live CR specs; skip nothing, validate exactly what ArgoCD resolves to.
2. **No policy; rely on code review** — trust reviewers to catch `Application`/`ApplicationSet` sources pointing at `base/` directories.
3. **Policy enforcing the assumption** — a machine-checkable rule that no `Application`/`ApplicationSet` source may point at a `base/` directory; overlays only.

## Decision Outcome

**Option 3, as an interim measure** until Option 1 is designed and implemented.

The *goal* is settled: no `Application`/`ApplicationSet` spec in the repository may reference a `base/` directory as its deployment source. The *mechanism* for enforcement is deferred to a follow-up discussion. Candidate mechanisms to weigh against each other:

- `conftest` + Rego on `gitops/**/*.yaml` (matches the ADR-013 pre-commit enforcement plane).
- A Kyverno `ClusterPolicy` validating `Application`/`ApplicationSet` resources at admission (runtime plane).
- A bespoke pre-commit script.

The mechanism choice should minimise duplication with existing policy infrastructure and reuse the enforcement plane established by [ADR-013](ADR-013-policy-location-architecture.md) where possible.

### Consequences

- **Good**: `discover_kustomize_overlays()`'s `base/` skip becomes safe by construction once the policy is active — the assumption behind the skip is enforced rather than assumed.
- **Good**: `base/` directories regain their intended role as reusable components, with tooling reinforcing the boundary.
- **Good**: the decision is narrow enough to revisit cheaply once AppSet-aware discovery lands — at that point this ADR becomes a candidate for supersedence.
- **Bad**: until the chosen mechanism ships, the `base/` skip remains an unenforced assumption. The risk window is bounded by the follow-up discussion cadence.
- **Bad**: two artefacts will carry the constraint — the engine's skip logic and the policy — until the engine grows AppSet-aware discovery. Duplication is accepted as temporary.

## Pros and Cons of the Options

### Full AppSet-aware discovery in the engine

- Good: the only option that truly honours ADR-014 without auxiliary policy — validation paths are derived from the actual deployment specs.
- Good: absorbs future generator patterns (matrix, list, cluster) without rule updates.
- Bad: requires non-trivial engineering against ArgoCD's internal model — generator evaluation, templating, source chaining. No existing in-repo scaffolding to build on.
- Bad: not the cheapest next step; delaying the engine's overall shipment to build this now blocks the pre-commit enforcement currently in flight.

### No policy; rely on code review

- Good: zero implementation cost.
- Bad: regression-prone. A single reviewer miss reintroduces silent drift from ADR-014.
- Bad: the convention is invisible to contributors who never encounter the relevant review — the "this `base/` won't be deployed" assumption is load-bearing but unstated.

## More Information

Related decisions:
- [ADR-004](ADR-004-helm-for-external-charts-kustomize-for-first-party-manifests.md) — the Kustomize/Helm split that makes the `base/` + overlay pattern load-bearing.
- [ADR-013](ADR-013-policy-location-architecture.md) — the policy-location split the enforcement mechanism should respect.
- [ADR-014](ADR-014-crd-handling-in-validation-pipeline.md) — the validation invariant this policy protects.
