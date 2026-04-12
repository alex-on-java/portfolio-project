---
status: accepted
date: 2026-04-11
decision-makers: [alex-on-java]
---

# Use Gateway API Exposure with Promotion-Time Hostname Injection

## Context and Problem Statement

The web workload needed internet exposure across ephemeral environments while keeping workload overlays reusable. Hardcoded hostnames in source overlays would couple manifests to specific PR or cluster prefixes and break promotion portability.

The project also needs a routing contract that remains stable even if the underlying Gateway controller changes over time.

## Decision Drivers

- Keep workload overlays cluster-agnostic and promotion-friendly
- Support ephemeral prefix variation without source-branch rewrites
- Use a routing API that is portable across Gateway implementations
- Keep DNS/TLS hostnames deterministic at promotion time

## Considered Options

1. Gateway API with hostname placeholders replaced during promotion
2. Ingress resources with static hostnames in overlays
3. Hardcoded per-environment hostnames in source overlays

## Decision Outcome

**Option 1: Gateway API with promotion-time hostname injection.**

Workload overlays keep route hostnames as placeholders. During promotion, Kargo updates hostnames using cluster identity values (prefix/domain) before rendering stage manifests. Gateway API is the stable traffic contract; controller-specific differences are isolated away from workload routes.

### Consequences

- **Good**: source overlays stay reusable across ephemeral clusters and stages.
- **Good**: rendered stage output contains concrete hostnames, improving traceability.
- **Good**: routing semantics stay portable as long as Gateway API support exists.
- **Bad**: promotion task complexity increases because hostname updates are now part of rendering.
- **Neutral**: correctness depends on cluster identity metadata being present and accurate.

## Pros and Cons of the Options

### Gateway API + Promotion-Time Hostname Injection

See **Decision Outcome** above.

### Ingress + Static Hostnames

- Good: simple manifests at first glance.
- Good: broad operational familiarity.
- Bad: less aligned with the project direction around Gateway API abstractions.
- Bad: static hostnames do not handle ephemeral prefix variability cleanly.

### Hardcoded Hostnames in Source Overlays

- Good: no promotion-time mutation required.
- Bad: not reusable across PR clusters with varying prefixes.
- Bad: creates repeated manifest edits for operational context changes.
- Bad: increases risk of stale or mismatched DNS/TLS wiring.
