# LL-0050: Deleted Firewall Reappears Before VPC Destroy

## Summary

A teardown workflow ran an early sweep step that deleted CCM-managed firewalls, then continued through bootstrap and cluster `terraform destroy` before the network `terraform destroy` step ran. An implicit assumption was that a firewall, once deleted, stays deleted. That assumption holds only after the cluster and its cloud-controller-manager are gone. While the cluster is still running, CCM reconciles owned cloud resources against Kubernetes objects, and an externally deleted firewall can be re-created before `Network: terraform destroy` runs.

## What Happened

`.github/workflows/cluster-lifecycle.yml` ordered the destroy steps as: cascade-delete bootstrap Application, sweep CCM-orphan firewalls, PR DNS destroy, bootstrap `terraform destroy`, cluster `terraform destroy`, network `terraform destroy`. Sweep ran several minutes before cluster destroy. On the run that surfaced the failure, network destroy failed with `Firewall k8s-12b2bb6d095edd54-node-http-hc still exists; not a consistency lag`. A retry-with-guard on network destroy distinguished a real orphan from the 30 to 60 second GCP in-use propagation lag, and refused to spin retrying.

A first hypothesis was that sweep had deleted the firewall and CCM had re-created it before cluster destroy. Subsequent forensic work ruled that out for this specific firewall. Audit-log enumeration and `creationTimestamp` inspection showed continuous existence since an earlier Stage-2 manual cascade test. Run 1 was driven by a different bug, a filter mismatch in the sweep itself. A CCM-race mechanism is nevertheless real for other CCM-owned firewalls and is the durable lesson. This entry records what the ordering actually means, not what one specific incident proved.

## Root Cause

Cloud-controller-manager in GKE owns the per-Service LoadBalancer firewalls (`k8s-fw-<svc-hash>`, the matching `-deny` rules, and `-http-hc` health-check rules) for every `Service.spec.type=LoadBalancer` in the cluster. A service controller watches Service objects, reconciles the desired cloud-resource set, and re-creates anything it expects to find. External deletions are reconciled back while the Service still exists and the controller is still running. This is what cloud-controller-manager exists to do; documentation describes it as the design.

Behavior in GKE diverges from that general pattern in one specific case. A cluster-scoped `k8s-<cluster-id>-node-http-hc` firewall is created once when the first LoadBalancer Service appears, and GKE intentionally retains it across deletion of the last Service. Once external action deletes that specific firewall, CCM does not re-create it on its own. This was verified live: zero `firewalls.insert` events from `service-<n>@container-engine-robot.iam.gserviceaccount.com` followed a manual delete polled over ten minutes against a quiescent cluster.

Together, the two facts produce the ordering rule:

- Sweeping per-Service firewalls before cluster destroy is unsafe whenever a Service still exists at sweep time, because CCM reconciles them back.
- Sweeping the cluster-scoped `node-http-hc` before cluster destroy is safe in GKE only because its trigger Service has been cascade-deleted by the preceding step. CCM does not re-create it.
- Sweeping after `Cluster: terraform destroy` is unconditionally safe: no actor remains to reconcile anything.

A general principle survives the GKE quirk: an external delete of any controller-managed cloud resource is reversible while the controller is alive. Workflows that delete such resources must place the delete so that the deleting actor outlives the reconciling actor, not the other way round.

## Resolution

Two complementary edits keep the sweep correct without coupling its correctness to the ordering of unrelated steps.

First, the sweep is made observable so a silent no-op cannot mask either a CCM race or a filter mismatch. Adding `set -Eeuo pipefail`, `set -x`, and an explicit `Found N firewall(s)` echo, together with removing `continue-on-error: true`, turns every silent failure mode into a visible log signal.

Second, the load-bearing sweep is shifted to run after `Cluster: terraform destroy`. It filters by VPC name rather than by cluster-id description, so the only actor that could have re-created firewalls is provably gone:

```yaml
- name: 'GKE: sweep CCM-orphan firewalls (post-cluster-destroy)'
  if: always() && inputs.action == 'destroy' && steps.cluster-check.outputs.exists == 'true'
  continue-on-error: false
  shell: bash
  run: |
    set -Eeuo pipefail
    NETWORK_NAME="${{ inputs.cluster_name }}-vpc"
    mapfile -t LEFT < <(
      gcloud compute firewall-rules list \
        --project="${{ env.PROJECT_ID }}" \
        --filter="network~/${NETWORK_NAME}\$ AND description~kubernetes.io/cluster-id" \
        --format='value(name)' | sort -u
    )
    if (( ${#LEFT[@]} > 0 )); then
      printf '%s\n' "${LEFT[@]}" \
        | xargs -n1 gcloud compute firewall-rules delete --quiet \
            --project="${{ env.PROJECT_ID }}"
    fi
```

VPC-scoped naming avoids the cluster-id lookup that is the proximate cause of the silent-no-op pattern recorded in a sibling lesson. Post-cluster ordering avoids the CCM-race class that this entry records.

## How to Detect

A diagnostic signature is a network `terraform destroy` failure carrying `Firewall <name> still exists; not a consistency lag`. The underlying GCP error is `The network resource ... is already being used by ...`. Both occur on a teardown where an earlier step nominally cleaned that firewall. Reading the workflow log of the earlier sweep shows the firewall named in the delete output of that step. Inspecting GCP at network-destroy time shows it absent, and the network-destroy error then shows it present again.

Three signals discriminate the race class from the filter-mismatch class:

- Audit-log query under `logName="projects/<p>/logs/cloudaudit.googleapis.com%2Factivity"` shows a `compute.firewalls.delete` event from the CI service account at sweep time. A `compute.firewalls.insert` event from `service-<n>@container-engine-robot.iam.gserviceaccount.com` follows before cluster destroy completes. Under a filter mismatch the delete event is absent.
- Post-failure `creationTimestamp` is later than the wall-clock time of the sweep step. With a filter mismatch the original `creationTimestamp` survives intact.
- The firewall is a per-Service rule (`k8s-fw-<svc-hash>`) whose owning Service was not cascade-deleted before the sweep, rather than the cluster-scoped `node-http-hc`.

## Adoption Rule

For any cloud resource owned by a Kubernetes controller running inside the cluster, cleanup steps that race the controller belong after the controller has been destroyed. The structural form generalizes beyond firewalls. Routes owned by the route-controller, target pools owned by the service-controller, and Ingress-derived forwarding rules share the same property: an external delete is reconciled away while the controller is alive. A safe slot for such cleanup in a teardown workflow is between cluster destroy and network destroy.

An exception is any resource that the cloud provider intentionally leaves behind after its trigger object is gone. The cluster-scoped `node-http-hc` firewall in GKE is the case observed in this project. For such resources an early sweep is correct in principle, but should still be paired with a late sweep. An early sweep no longer relies on absence of the controller for safety; it relies on absence of the trigger, which is a property of the cascade-delete one step earlier.
