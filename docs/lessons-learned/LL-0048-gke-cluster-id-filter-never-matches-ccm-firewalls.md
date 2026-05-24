# LL-0048: `gcloud value(id)` Returns a Different Cluster ID Than CCM Stamps onto Firewalls

## Summary

GKE exposes two unrelated cluster identifiers. `gcloud container clusters describe --format='value(id)'` returns a 64-character API-resource UUID. In-cluster cloud-controller-manager stamps a different 16-character hex short ID into firewall names (`k8s-<short>-node-http-hc`) and into firewall descriptions (`{"kubernetes.io/cluster-id":"<short>"}`). That short ID is neither a prefix nor a substring of the long one. A filter that interpolates the `value(id)` output into a `description~kubernetes.io/cluster-id.*<id>` expression therefore matches zero firewalls on every cluster.

## What Happened

The destroy workflow at `.github/workflows/cluster-lifecycle.yml` carried a sweep step that resolved the cluster identifier with `gcloud container clusters describe --format='value(id)'` and then ran:

```bash
gcloud compute firewall-rules list \
  --filter="description~'kubernetes.io/cluster-id.*${CLUSTER_UID}'" \
  --format='value(name)' \
  | xargs -r gcloud compute firewall-rules delete
```

The step had `continue-on-error: true`, no `set -x`, no `set -Eeuo pipefail`, and `xargs -r` no-ops on empty input. Every observable surface read as success. Thirty days of CI history recorded zero `firewalls.delete` audit-log events from any CI service account, so the step had never deleted a firewall.

Two consecutive destroy runs against clusters that hosted a `projectcontour/contour-envoy` LoadBalancer Service then both failed at the network-destroy step on an orphan firewall: `k8s-12b2bb6d095edd54-node-http-hc` and `k8s-55ee3474fb65f5de-node-http-hc`. A live `describe` against a fresh cluster recorded the discrepancy directly:

> Cluster `value(id)` = `2f230d50b6e74514a69a4adead5065376b2ecaab80224604b0594dea05d614ba` (64 chars). Short cluster-id in firewall names = `6092493700879eb8` (16 chars). Confirmed different.

A CCM-managed firewall on that same cluster carried `description={"kubernetes.io/cluster-id":"6092493700879eb8"}`. The filter the workflow built referenced the 64-character UUID, which appears nowhere in any CCM artefact.

## Root Cause

Kubernetes cloud-provider-gcp and the GKE API-resource layer mint cluster identifiers independently. The API resource records a long UUID, surfaced by `gcloud` proto as `Cluster.id` and documented as "Output only. Unique id for the cluster." Inside the cluster, cloud-controller-manager mints a separate 16-character hex value. It stamps that value into the names of cluster-scoped firewalls (`k8s-<short>-node-http-hc`) and emits it as the value of a `kubernetes.io/cluster-id` JSON entry in the firewall description.

Each identifier is documented truthfully in isolation. Neither side documents the existence of the other, so a reader who reaches for "the cluster ID" lands on whichever surface they consulted first. The original sweep step authored its filter against the GKE API surface (`gcloud value(id)`). It then matched against artefacts created on the CCM surface; the two surfaces share a noun and nothing else.

A secondary identifier collision exists nearby and is worth keeping straight. The GKE node-pool firewall names embed an 8-character hash that *is* the first 8 hex digits of the long `value(id)` (above: `gke-...-2f230d50-vms` against UUID `2f230d50b6e7...`). That coincidence makes the assumption "the firewall name encodes a prefix of `value(id)`" look workable, then fails sharply on CCM-managed firewalls, whose 16-character short ID is independently generated.

## Why the Failure Stays Invisible

Three properties of the sweep step compound the misconception into a silent success:

- `gcloud --format='value(id)'` returns a non-empty string, so any `[[ -z "$CLUSTER_UID" ]]` guard passes.
- `gcloud compute firewall-rules list` against a non-matching filter exits zero with empty stdout, indistinguishable from a legitimate "nothing to sweep" outcome.
- `xargs -r` no-ops on empty input. No delete is attempted, no audit-log event is emitted, and `continue-on-error: true` would have absorbed any error anyway.

An orphan firewall surfaces this failure only when it blocks the downstream `terraform destroy` on the VPC. Until a cluster runs a LoadBalancer Service, the CCM never creates a cluster-scoped firewall. Without a target firewall, the sweep has nothing to match, and the filter on the step is silently correct by absence. Correctness becomes load-bearing on the first run against a cluster that did host a LoadBalancer Service.

## Resolution

Match CCM-managed firewalls by the resources they touch, not by an identifier the workflow has to resolve out of band. The VPC name is derivable from `inputs.cluster_name` and is unique to the ephemeral world of the cluster:

```yaml
gcloud compute firewall-rules list \
  --project="${{ env.PROJECT_ID }}" \
  --filter="network~/${{ inputs.cluster_name }}-vpc\$ AND description~kubernetes.io/cluster-id" \
  --format='value(name)'
```

Two filter clauses carry the load. One clause, `network~/<cluster>-vpc$`, scopes the result to firewalls attached to the VPC of this cluster. Another clause, `description~kubernetes.io/cluster-id`, admits only the cluster-scoped CCM firewall. Per-Service CCM firewalls fall outside this filter because their descriptions carry `kubernetes.io/service-name`. Four GKE-managed node-pool firewalls fall outside it because their descriptions are empty. With these clauses in place, the `gcloud container clusters describe` call drops out of the step entirely, and no cross-surface identifier resolution remains.

## Adoption Rule

When a workflow filters cloud resources by an identifier that a Kubernetes controller stamps on them, verify the value on a live cluster. Compare it against the value the cloud API returns. Treat them as distinct until evidence shows otherwise. The matched identifier and the queried identifier must come from the same surface, not from two surfaces that happen to share a noun.

Where the cluster-issued and API-issued identifiers differ, prefer a structural filter that targets the resources the controller manages (network scope, description marker, naming prefix) over an identifier-interpolation filter. Structural filters do not depend on resolving an identifier and do not silently fail when the resolution returns the wrong surface.

## How to Detect

Signs that a `gcloud`-based sweep is silently matching nothing:

- The audit log records zero `firewalls.delete` events from the CI service account across the full history of the workflow, despite clusters that hosted LoadBalancer Services.
- The sweep step exits zero with empty stdout on every run, regardless of the actual firewall inventory of the cluster.
- The downstream `terraform destroy` on the VPC fails on an orphan firewall whose name embeds a hex string the sweep never saw.

A direct cross-check on any live cluster confirms the divergence:

```bash
gcloud container clusters describe "$CLUSTER" --region "$REGION" --format='value(id)'
gcloud compute firewall-rules list \
  --filter="network~/${CLUSTER}-vpc\$" \
  --format='value(name,description)'
```

The first command returns a 64-character UUID. Any `k8s-<hex>-node-http-hc` row from the second command carries a 16-character hex value in both its name and its description. Those two strings share no prefix.
