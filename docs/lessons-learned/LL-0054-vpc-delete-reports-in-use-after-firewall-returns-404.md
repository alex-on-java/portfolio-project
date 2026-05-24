# LL-0054: GCP VPC Delete and Firewall Get Read from Independent Indexes

## Summary

GCP serves `firewalls.get` and the in-use check inside `networks.delete` from independent eventually-consistent indexes. After `firewalls.delete` reaches Operation status `DONE` and `firewalls.get` returns 404, `networks.delete` can still reject with `resourceInUseByAnotherResource` for roughly 30 to 60 seconds. The named firewall is already gone from every read path. Worse, `networks.get` and `getEffectiveFirewalls` read from the same lagged path that backs the VPC in-use bookkeeping. No GCP API call distinguishes a consistency lag from a real reference still being present. The orchestrator must retry with backoff and use the firewall `get` as a sanity check rather than a precondition.

## What Happened

The ephemeral-cluster teardown in `portfolio-project-infra/.github/workflows/cluster-lifecycle.yml` deletes cluster-scoped CCM-orphan firewalls, then runs `terraform destroy` on the network module. On the live experiment the sweep step deleted the firewall successfully and `firewall-rules describe` returned 404, yet the very next `Network: terraform destroy` failed with:

```
Error waiting for Deleting Network: The network resource
'projects/.../global/networks/<vpc>' is already being used by
'projects/.../global/firewalls/k8s-<uid>-node-http-hc'
```

A second terraform attempt 30 to 60 seconds later returned success against the same VPC, with no further API actions in between. The same shape reproduced across multiple cluster releases.

## Root Cause

Three independent reads were observed:

1. `firewalls.delete` Operation transitions to `DONE`.
2. `firewalls.get` returns 404.
3. `networks.delete` still rejects with `resourceInUseByAnotherResource` citing the same firewall name.

This contradiction has a structural explanation. The firewall-resource index that backs `firewalls.list` and `firewalls.get` propagates ahead of the VPC in-use bookkeeping that backs the precondition check inside `networks.delete`. No GCP API is documented to bridge the two. `globalOperations.wait` covers the firewall delete Operation only. `networks.get` exposes `peerings` and `subnetworks` but no enumerated "firewalls referencing me" field. `networks.getEffectiveFirewalls` reads the same lagged path as the in-use check, so a positive answer is not an authoritative reference, only a redundant observation. Issues #9812, #5948, #18156, #6852, and #675 against terraform-provider-google are all the same class, all unresolved at the provider layer; the maintainers' position is that orchestrators own the retry budget. Published Google guidance for `resourceInUseByAnotherResource` is local retry with backoff, with no SLA on the window. The observed 30 to 60 s on this codebase is a community-consistent range, not a contract.

For tooling design the consequence is direct: no read lets the orchestrator wait for "VPC bookkeeping has caught up" before issuing `networks.delete`. Polling `firewalls.get` until 404 satisfies one index but says nothing about the other.

## Resolution

`Network: terraform destroy` is wrapped in a retry-with-guard loop. On each `resourceInUseByAnotherResource`, the loop extracts the referenced firewall names from the error and calls `firewall-rules describe` on each one. When every referenced firewall returns 404, the failure is classified as a consistency lag and the loop backs off on a budget that comfortably exceeds the observed window (`5 s, 10 s, 15 s, 20 s, 30 s`, approximately 165 s total). If any referenced firewall still exists, the loop exits non-zero with `Firewall <name> still exists; not a consistency lag`. That outcome flags a real orphan, not a lag; silently retrying would hide a missed dependent.

This `firewall-rules describe` call is a guard against masking real bugs, not a precondition for proceeding. The retry budget is what makes the path correct.

## How to Detect

Symptoms of the firewall-index versus VPC-bookkeeping split:

- `networks.delete` (or `terraform destroy` on `google_compute_network`) returns `resourceInUseByAnotherResource` naming a specific firewall.
- `gcloud compute firewall-rules describe <name>` against the named firewall returns `NOT_FOUND` immediately afterward.
- The same `networks.delete` call retried after 30 to 60 seconds succeeds with no other action in between.

When all three hold, the orchestrator is observing the lag, not a real dependent. If the firewall still exists, the orchestrator is observing a real reference and must fix the dependency rather than extend the retry budget.

## Adoption Rule

Any orchestrator that deletes a GCP firewall and then a parent VPC must:

- Retry `networks.delete` on `resourceInUseByAnotherResource` with bounded backoff that comfortably exceeds the community-observed 30 to 60 s window (this repo uses approximately 165 s).
- On every retry, parse the firewall names from the error and call `firewalls.get` on each. Treat the failure as transient only when every referenced firewall returns 404; otherwise fail loud.
- Not rely on `firewalls.list`, `firewalls.get`, `networks.get`, or `getEffectiveFirewalls` as a synchronization barrier before issuing `networks.delete`. None of these reads observe the VPC in-use bookkeeping.

This shape applies to other GCP resource pairs whose deletion order crosses an eventually-consistent boundary: `forwardingRules` and `backendServices`, `targetPools` and `instanceGroups`, `subnetworks` and `networks`. The retry-with-guard pattern generalizes; the firewall-specific sanity check does not.

## Generalization

The broader lesson is that an "X is gone" read on one resource type is not evidence that the parent view of X has converged. When two GCP resources are linked by a containment or reference relationship, the API surfaces that observe each side often live behind independent caches. A deletion orchestrator that treats one read as authoritative for the other is correct only by coincidence of timing. The reliable shape is to retry the operation that actually depends on the converged view, bounded by a budget, with a guard that distinguishes lag from a genuine missed dependency.
