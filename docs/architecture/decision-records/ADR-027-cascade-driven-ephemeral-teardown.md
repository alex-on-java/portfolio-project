---
status: accepted
date: 2026-05-24
decision-makers: [alex-on-java]
---

# Cascade-Driven Ephemeral Cluster Teardown

## Context and Problem

Ephemeral GKE clusters host ArgoCD-managed workloads that provision GCP resources outside the cluster boundary. Services of type `LoadBalancer` create forwarding rules and DNS records. PersistentVolumeClaims will create disks once they are added, and any future workload may attach more cloud objects.

Earlier, the ephemeral teardown design suppressed the ArgoCD cascade-deletion path so that Terraform could destroy the cluster directly. Two suppression mechanisms were in place. One was an ephemeral-overlay patch on generated ApplicationSets that set `preserveResourcesOnDeletion: true` and cleared the template `metadata.finalizers`. The other was the `argocd.argoproj.io/sync-options: Delete=false` annotation carried by each ArgoCD-managed namespace (`dev`, `stg`, `prd`, `observability`).

That design held only as long as no workload owned a cloud resource. After Services of type `LoadBalancer` landed, every ephemeral release left orphaned GCP networking and DNS Zone entries. Those entries had to be removed by hand before the cluster could be marked released.

## Decision Drivers

- Workload-owned GCP resources must release without manual intervention on PR close.
- The teardown contract must generalize to any future workload that allocates cloud resources, rather than requiring a per-resource `gcloud delete` patch each time the platform grows.

## Decision

Ephemeral teardown runs in two phases:

1. The release workflow deletes the ArgoCD bootstrap Application. ArgoCD cascades through the tree to zero state, removing Kubernetes resources together with the cloud resources they own.
2. Terraform destroys the cluster and the surrounding network after the cascade settles.

The ephemeral overlay no longer patches generated ApplicationSets with `preserveResourcesOnDeletion: true` or with cleared `template.metadata.finalizers`. Generated Applications inherit base cascade behavior, including the default `resources-finalizer.argocd.argoproj.io` that the ArgoCD controller adds.

The ArgoCD-managed namespaces (`dev`, `stg`, `prd`, `observability`) no longer carry the `argocd.argoproj.io/sync-options: Delete=false` annotation. Cascade can therefore delete those namespaces after their workloads drain.

Both changes apply to GitOps manifests only. The release workflow and the surrounding Terraform code are out of scope for this ADR.

## Options Considered

No other option was considered seriously. Targeted `gcloud delete` patches in the release workflow were ruled out: each new cloud-resource shape added to the platform would require its own patch step.

## Option Analysis

The chosen approach is future-proof against new workloads. Any Kubernetes resource added to ArgoCD that provisions a GCP resource is released in the same cascade pass as its owning Kubernetes object. This covers Services of type `LoadBalancer`, PersistentVolumeClaims, backend-config attachments, and any later additions. The release workflow needs no corresponding change.

The rejected per-resource cleanup approach scales poorly. Each new workload type that allocates a cloud resource would require a matching `gcloud delete` step in the workflow. Over time, the workflow would drift toward an enumerated catalog of cloud shapes that ArgoCD already understands through Kubernetes owner references.

## Consequences

- **Good**: workload-owned cloud resources release without manual cleanup. `LoadBalancer`-backed network entries and DNS Zone records are removed by cascade. The same path will cover PVC-backed disks and any later additions.
- **Good**: adding a workload that allocates a cloud resource does not require a release-workflow change. Platform release contracts scale with workload growth.
- **Good**: removing the ephemeral-overlay patch retires the JSON-patch surface that [ADR-002](ADR-002-ephemeral-and-main-cluster-separation.md) flagged as a fragility cost.
- **Bad**: teardown now depends on ArgoCD reaching zero state before Terraform destroy can start. A stuck reconciliation blocks teardown until it is resolved.
- **Neutral**: [ADR-002](ADR-002-ephemeral-and-main-cluster-separation.md) gave "safe teardown without hanging finalizers" as a driver; that rationale is no longer load-bearing. Other decisions in ADR-002, including the base/overlays pattern, the polling intervals, the auto-promotion breadth, and the CRD wave ordering, remain in force.

## Related Records

- [ADR-002](ADR-002-ephemeral-and-main-cluster-separation.md) establishes the base/overlays manifest pattern this ADR builds on. The teardown approach recorded there is the part this ADR revises; the rest of ADR-002 continues to apply.
