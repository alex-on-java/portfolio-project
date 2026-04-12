---
status: accepted
date: 2026-04-11
decision-makers: [alex-on-java]
---

# Use Edge-Owned Wildcard TLS and Stage-First Hostname Contract

## Context and Problem Statement

Per-environment cross-namespace certificate references created ownership coupling between workload namespaces and the edge Gateway. This increased rollout coordination overhead and made TLS convergence sensitive to cross-boundary timing.

The edge layer needed a single, explicit TLS ownership model with predictable hostname structure across stages.

## Decision Drivers

- Keep TLS ownership aligned with edge routing ownership
- Reduce cross-namespace authorization coupling for standard traffic paths
- Keep hostname contracts explicit and deterministic per stage
- Improve convergence behavior by co-locating dependent edge resources

## Considered Options

1. Edge-owned wildcard certificate with stage-first hostname contract
2. Continue with per-stage/per-service certificates in workload namespaces
3. Provider-managed certificate path with reduced Git visibility

## Decision Outcome

**Option 1: Edge-owned wildcard TLS + stage-first hostnames.**

A wildcard certificate is owned in the edge namespace and wired directly to the edge Gateway. Hostname structure remains stage-first and deterministic, with promotion-time data driving concrete environment prefixes.

### Consequences

- **Good**: TLS lifecycle is centralized with edge ownership boundaries.
- **Good**: reduces cross-namespace certificate reference complexity for core ingress flow.
- **Good**: keeps route/certificate contracts easier to reason about during promotion and troubleshooting.
- **Bad**: wildcard design introduces dependence on naming contract discipline.
- **Neutral**: non-wildcard exceptions may still require explicit handling paths.

## Pros and Cons of the Options

### Edge-Owned Wildcard TLS + Stage-First Hostnames

See **Decision Outcome** above.

### Per-Stage/Per-Service Certificates in Workload Namespaces

- Good: certificate ownership sits with each workload stage.
- Good: can provide narrow scoping per hostname.
- Bad: increases cross-boundary coupling with shared edge listener configuration.
- Bad: makes convergence sensitive to separate reconciliation streams.

### Provider-Managed Certificate Path

- Good: potentially lower in-cluster certificate management surface.
- Bad: can reduce Git-level visibility of TLS lifecycle decisions.
- Bad: risks portability loss across environments.
