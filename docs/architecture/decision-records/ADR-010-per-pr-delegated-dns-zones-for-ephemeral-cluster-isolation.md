---
status: accepted
date: 2026-04-14
decision-makers: [alex-on-java]
---

# Per-PR Delegated DNS Zones for Ephemeral Cluster Isolation

## Context and Problem Statement

DNS is a shared mutable surface across ephemeral PR clusters. ExternalDNS in each cluster writes records to a single shared Cloud DNS zone under a common `txtOwnerId`. Stale records survive cluster replacement and route traffic to dead IPs. Parallel PRs share the same managed zone with no ownership boundary — record collisions are possible when multiple PRs are active.

The existing TXT-owner partitioning within a shared zone works for low concurrency but becomes a coordination liability at scale (10× litmus test: 2 PRs → fine, 20 PRs → fragile).

## Decision Drivers

- DNS lifecycle must be tied to PR scope — creation on claim, deletion on release
- Zone-level isolation provides the cleanest boundary for concurrent PRs
- ExternalDNS and cert-manager must be scoped without relying on undocumented side effects
- Cluster recreation within the same PR should reuse the zone, not churn it
- Cloud DNS quota (10,000 zones/project) permits per-PR zones at any realistic scale

## Considered Options

1. Per-PR delegated child zones with Terraform-managed lifecycle
2. Shared zone with improved TXT-owner partitioning
3. Separate GCP project per PR
4. Imperative `gcloud` for zone lifecycle management
5. DNS delete as a separate fire-and-forget workflow

## Decision Outcome

**Option 1: Per-PR delegated child zones** (`pr-N.portfolio-project.buyanov.de`) under the existing parent zone, with Terraform lifecycle triggered by claim/release events.

Scoping controls in this repository:
- ExternalDNS: `domainFilters` narrowed to child zone, `--zone-id-filter` pins to the specific managed zone by name, `txtOwnerId` set to `branch-prefix` for per-PR ownership
- cert-manager: `hostedZoneName` set on ClusterIssuer via ApplicationSet kustomize patch to scope DNS01 challenges to the child zone
- Managed zone name uses full-length deterministic format (`pr-N-portfolio-project-buyanov-de`) to avoid `--zone-id-filter` suffix collisions at scale (`pr-4` would otherwise also match `pr-40`)

### Consequences

- **Good**: each PR environment gets an isolated DNS management surface — no cross-PR record interference.
- **Good**: zone lifecycle is deterministic from PR number — activation can set annotations without waiting for DNS workflow completion.
- **Good**: `force_destroy = true` on the Terraform zone resource auto-drains records before deletion.
- **Bad**: adds a Terraform root and workflow dispatch to the cluster lifecycle — more moving parts.
- **Neutral**: DNS orphans from brutal-delete scenarios are accepted debt until a janitor phase.

## Pros and Cons of the Options

### Per-PR Delegated Child Zones

See **Decision Outcome** above.

### Shared Zone with Improved TXT-Owner Partitioning

- Good: no additional Cloud DNS resources needed.
- Good: simpler infrastructure — no zone creation/deletion workflow.
- Bad: still a shared mutable surface; `--zone-id-filter` on a single zone provides no record-level isolation.
- Bad: fails the 10× litmus test — concurrent PRs compete for the same zone's records.

### Separate GCP Project per PR

- Good: strongest possible isolation boundary.
- Bad: operationally too heavy — project lifecycle, IAM, billing all need management per PR.
- Bad: disproportionate to the problem being solved.

### Imperative `gcloud` for Zone Lifecycle

- Good: simpler initial implementation.
- Bad: no idempotency guarantees — requires manual state tracking.
- Bad: `force_destroy` equivalent (drain all records before delete) must be implemented manually.
- Bad: inconsistent with the existing Terraform-based infrastructure pattern.

### DNS Delete as Separate Fire-and-Forget Workflow

- Good: decouples DNS cleanup from cluster destroy.
- Bad: ordering matters — ExternalDNS must be gone before zone deletion, or it recreates records during cleanup. Separate workflow cannot guarantee this sequencing.
