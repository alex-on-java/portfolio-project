# LL-0049: VPC Delete Reports `resourceInUseByAnotherResource` Against a Firewall That Outlives the GKE Cluster

## Summary

The GKE cloud-controller-manager creates a cluster-scoped health-check firewall named `k8s-<short-id>-node-http-hc` (or `-node-hc` for the ETP=Local variant) the first time a `LoadBalancer` Service reconciles. This rule is keyed by the cluster UID, not by any Service UID. It is intentionally retained when the last `LoadBalancer` Service is deleted, and `gcloud container clusters delete` does not enumerate cluster-id-keyed firewalls either. The surviving rule continues to reference the VPC, and the subsequent `google_compute_network` delete fails with `resourceInUseByAnotherResource`. A cluster that never had a `LoadBalancer` Service never produces the rule, so a green destroy run is not evidence that the lifecycle is well-understood.

## What Happened

On run #139 of the ephemeral-PR teardown, `Network: terraform destroy` exited non-zero with:

> `Error waiting for Deleting Network: The network resource 'projects/<project>/global/networks/portfolio-pool-ew1-19-48-ac0a2fdf-vpc' is already being used by 'projects/<project>/global/firewalls/k8s-b3baa8b865bd5710-node-http-hc'`

By that point, the cluster object was gone. Per-Service `k8s-fw-<svc-hash>` and `k8s-<svc-hash>-http-hc` firewalls had been swept by the GKE control plane during cluster delete. Four node-pool firewalls (`gke-...-{all,vms,exkubelet,inkubelet}`) were gone too. Only the cluster-scoped `k8s-<cluster-uid>-node-http-hc` remained. Identical lineage repeated across runs #129, #132, and #139: three different clusters, three orphan rules with the same name shape.

A 30-day audit-log query for `firewalls.delete` events targeting that rule returned zero entries. No actor had ever attempted to delete it. Not the in-cluster cloud-controller-manager service account (`service-<project-number>@container-engine-robot.iam.gserviceaccount.com`), not the GKE control plane during cluster delete, not any CI service account.

## Root Cause

Two separate GKE actors clean up firewalls during teardown, and neither owns the cluster-scoped health-check rule.

In-cluster cloud-controller-manager runs first. Deleting a `LoadBalancer` Service drives the per-Service firewalls (`k8s-fw-<svc>`, `k8s-fw-<svc>-deny`, `k8s-<svc>-http-hc`) to deletion via the Service finalizer `service.kubernetes.io/load-balancer-cleanup`. The cluster-scoped `k8s-<cluster-uid>-node-http-hc` is not associated with any single Service. Instead, the in-tree service controller patches it on Service rotation to point at the next LB IP and NodePort. When the last `LoadBalancer` Service is removed, the rule remains.

GKE control plane runs second, during `gcloud container clusters delete`. Its cluster-delete path sweeps Service-UID-keyed firewalls and node-pool firewalls. It does not enumerate cluster-id-keyed firewalls. The cluster-scoped health-check rule therefore survives cluster deletion, and the cloud-controller-manager that could have reconciled it is killed alongside the cluster.

A second trap hides in the identifier. The rule names itself off a 16-character GKE *short* cluster-id stamped into the description (`{"kubernetes.io/cluster-id":"<short-id>"}`). That short id differs from the 64-character cluster UUID returned by `gcloud container clusters describe --format='value(id)'`. Neither identifier is a prefix of the other. Any cleanup that resolves the long UUID and then filters firewalls by it matches zero rows.

One more piece of the lifecycle matters for path coverage. A cluster that never reconciled a `LoadBalancer` Service never causes the rule to materialize. Past green destroys of such clusters were not evidence that the workflow handled the rule correctly; they exercised the empty-input path of every cleanup hook.

## Resolution

The destroy workflow sweeps the surviving firewall explicitly before the VPC delete runs, using a description-match filter that targets exactly the marker the cloud-controller-manager stamps:

```bash
gcloud compute firewall-rules list \
  --filter="network:${VPC} AND description~'kubernetes.io/cluster-id'" \
  --format='value(name)'
```

Description-match was chosen over name-match deliberately. Per-Service firewalls share the `k8s-` name prefix but carry a different description key (`kubernetes.io/service-name`). Selecting by description targets exactly the cluster-scoped marker and avoids both classes of false match. It also admits the two known variants uniformly: `k8s-<short>-node-http-hc` (ETP=Cluster legacy path) and `k8s-<short>-node-hc` (ETP=Local).

A second guard wraps the `google_compute_network` delete. The in-use index lags the firewall delete by 30 to 60 seconds, so a retry-with-guard checks each `resourceInUseByAnotherResource` against the live state. When `firewalls.get` on the referenced rule returns 404, the workflow treats the error as the lag and backs off. Should the rule still exist, the workflow fails loudly: that is a real missed dependent, not the lag.

## Adoption Rule

Once a GKE cluster has reconciled a `LoadBalancer` Service even once, treat the cluster-scoped `k8s-<short>-node-http-hc` (or `-node-hc`) firewall as a tombstone. It survives both the last Service and the cluster itself. Any teardown sequence that destroys the surrounding VPC must delete this rule explicitly before invoking `google_compute_network` destroy, scoped by `description~'kubernetes.io/cluster-id'` against the target VPC. The subsequent VPC delete must also be guarded against the in-use eventual-consistency lag.

## How to Detect

Signs that this exact failure mode is in play:

- `terraform destroy` on `google_compute_network` exits with `resourceInUseByAnotherResource` naming a firewall in the form `k8s-<hex>-node-http-hc` or `k8s-<hex>-node-hc`.
- The GKE cluster object is already gone at the time of the error.
- `gcloud compute firewall-rules describe <name> --format='value(description)'` on the offender returns a JSON blob containing `kubernetes.io/cluster-id`.
- A `gcloud logging read 'protoPayload.methodName="v1.compute.firewalls.delete"'` query over the audit-log retention window returns zero entries for the rule name.

A subtler signature: the cleanup step looks green for many runs and never logs a deleted firewall. That is consistent with the rule never materializing, because no `LoadBalancer` Service ever reconciled on the destroyed cluster. Path-coverage requires a destroy against a cluster that actually ran a `LoadBalancer` Service to completion.
