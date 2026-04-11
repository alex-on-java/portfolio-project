---
status: accepted
date: 2026-04-11
decision-makers: [alex-on-java]
---

# Use Contour for Ephemeral Clusters and GCP Managed Gateway for Main Cluster

## Context and Problem Statement

The project needed to choose whether ephemeral clusters should use GCP managed Gateway or an in-cluster controller. The choice impacts bootstrap latency, operating cost, and future portability to local cluster environments.

At the same time, the long-term direction for the future main (production) cluster is to use GCP managed Gateway.

## Decision Drivers

- Fast startup and teardown for PR-based ephemeral clusters
- Lower incremental cost for short-lived environments
- Ability to reuse the same edge-controller approach in future local clusters
- Preserve a clear production path for managed infrastructure in the main cluster

## Considered Options

1. Contour for ephemeral, GCP managed Gateway for main
2. GCP managed Gateway for both ephemeral and main
3. Contour for both ephemeral and main

## Decision Outcome

**Option 1: Contour for ephemeral clusters, GCP managed Gateway for main.**

Ephemeral clusters prioritize speed, lower overhead, and local-cluster portability, so Contour is the better fit. The future main cluster prioritizes managed production-grade infrastructure, so GCP managed Gateway remains the intended target there.

### Consequences

- **Good**: ephemeral environments bootstrap faster and avoid managed-gateway overhead/cost for short-lived PR lifecycles.
- **Good**: the same controller family can be reused for future local cluster support.
- **Good**: production path remains aligned with managed GCP infrastructure on the main cluster.
- **Bad**: two runtime gateway implementations exist across environment classes, requiring explicit ownership boundaries and compatibility checks.
- **Neutral**: Gateway API resource contracts remain portable, which reduces migration risk between implementations.

## Pros and Cons of the Options

### Contour for Ephemeral + GCP Managed Gateway for Main

See **Decision Outcome** above.

### GCP Managed Gateway for Both Ephemeral and Main

- Good: single managed implementation across environments.
- Good: reduced controller operations in-cluster.
- Bad: slower startup and higher burden for ephemeral PR clusters.
- Bad: less useful for future local-cluster path where managed GCP gateway is unavailable.

### Contour for Both Ephemeral and Main

- Good: one controller family across all cluster types.
- Good: maximum portability across cloud and local environments.
- Bad: gives up managed-GCP production path desired for the future main cluster.
- Bad: shifts more ongoing controller operations into the production environment.
