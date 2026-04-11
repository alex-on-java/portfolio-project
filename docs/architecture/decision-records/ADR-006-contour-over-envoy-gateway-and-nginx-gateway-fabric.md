---
status: accepted
date: 2026-04-11
decision-makers: [alex-on-java]
---

# Choose Contour over Envoy Gateway and NGINX Gateway Fabric for Ephemeral Clusters

## Context and Problem Statement

The project needed one Gateway API implementation for ephemeral environments that remains reliable under cluster policy constraints and does not require long-lived workaround layering.

The decision space included three viable controllers: Contour, Envoy Gateway, and NGINX Gateway Fabric.

## Decision Drivers

- Fresh-cluster reliability for PR environments
- Minimize permanent workaround burden in GitOps definitions
- Keep existing Gateway/HTTPRoute contract stable
- Reduce control-plane failure modes tied to CRD install behavior
- Keep operational behavior predictable during repeated bootstrap/teardown cycles

## Considered Options

1. Contour
2. Envoy Gateway
3. NGINX Gateway Fabric

## Decision Outcome

**Option 1: Contour.**

Contour is selected as the ephemeral Gateway API controller because it provides the best trade-off for this repository: stable Gateway API behavior, clean GitOps integration, and lower ongoing workaround burden compared to alternatives.

### Consequences

- **Good**: avoids the CRD-management friction and workaround layering pressure that made the Envoy path high-maintenance in this context.
- **Good**: keeps the workload/edge resource model on standard Gateway API objects.
- **Good**: aligns with the project principle of fixing root causes rather than committing permanent workaround machinery.
- **Bad**: introduces controller migration and controller-specific tuning work.
- **Neutral**: future upgrades still require compatibility checks for available Gateway API kinds in target clusters.

## Pros and Cons of the Options

### Contour

See **Decision Outcome** above.

### Envoy Gateway

- Good: mature data-plane ecosystem and broad familiarity.
- Good: can be made operational with additional controls.
- Bad: in this environment, required workaround layering around chart/CRD behavior increased maintenance burden.
- Bad: reconciliation and recovery complexity rose due to coupling between policy constraints and chart behavior.

### NGINX Gateway Fabric

- Good: viable Gateway API controller option with active ecosystem.
- Good: could satisfy baseline routing requirements.
- Bad: no clear net benefit over Contour for this repository's constraints.
- Bad: switching cost remained while still requiring controller-specific operational tuning.
