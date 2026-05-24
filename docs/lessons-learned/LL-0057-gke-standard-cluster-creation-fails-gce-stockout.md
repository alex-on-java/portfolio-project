# LL-0057: GKE-Standard Cluster Creation Fails `GCE_STOCKOUT` Even With Quota Headroom

## Summary

A GKE-Standard cluster module pinned `node_locations = ["${var.region}-b"]` for ephemeral PR clusters. GKE honored the single-zone constraint exactly. Provisioning failed with the `GCE_STOCKOUT` `StatusCondition.code` when the chosen zone happened to be physically tight. That error reports a zone-local capacity exhaustion that is unrelated to project quota: `gcloud compute regions describe` returned full headroom on every quota the run had touched. Omitting `node_locations` restores the GKE default of spreading nodes across the three control-plane zones, which lets the provisioner skip a tight zone instead of failing the request. The single-zone pin originally fixed a different bug, regions where the `-a` zone does not exist, and was carried forward as the path of least resistance.

## What Happened

The Standard-cluster module in `portfolio-project-infra/infra/cluster/main.tf` carried:

```hcl
node_locations = ["${var.region}-b"]
```

On run `26254477129` (`Pool: PR Push`, 21:35:01Z on 2026-05-21), provisioning of `portfolio-pool-use5-21-36-eaa0ca32` in `us-east5` failed. GKE surfaced `StatusCondition.code = GCE_STOCKOUT` on the cluster resource. No nodes ever came up. The cluster object reached state `ERROR` and the pool state machine recorded `consecutive_provision_failures: 1`.

Project quota for the affected region carried full headroom. A `gcloud compute regions describe us-east5` call returned `E2_CPUS=8/0 used` and `CPUS=32/0 used`. Capacity in the zone was exhausted; a quota guard did not fire.

The recurrence pattern across seven days of cluster-pool history was four `GCE_STOCKOUT` events, every one of them in a `-b` zone:

| Date       | Zone             |
| ---------- | ---------------- |
| 2026-05-21 | `us-east5-b`     |
| 2026-05-20 | `europe-west4-b` |
| 2026-05-19 | `us-west1-b`     |
| 2026-05-18 | `us-east5-b`     |

That `-b` concentration is fully explained by the module hard-coding the `-b` suffix: every claim, in every region the pool rotation picked, landed in `-b`. The denominator was 100 percent `-b`, so the numerator was 100 percent `-b`. Such data does not separately support a claim that `-b` zones are intrinsically tighter than `-a` or `-c` zones. Public GCE-discuss threads on `ZONE_RESOURCE_POOL_EXHAUSTED` enumerate stockouts across all three letters; the lesson generalizes to any pinned zone.

## Root Cause

GKE treats `node_locations` as an exact constraint. Setting it overrides the regional cluster default of spreading nodes across the three control-plane zones. The provisioner therefore had no permission to substitute a healthy zone for a tight one. Published GCE guidance for zone-local stockouts is to retry against a different zone. Pinning to a single zone removes the only mitigation the platform offers without a Compute Engine reservation.

That `-b` pin entered the module in `bf9ea84 fix(cluster): use zone -b for node_locations` to work around regions that lack `-a` (`europe-west1` and `us-east1` carry only `-b`, `-c`, `-d`). Its commit message flagged the hardcoded suffix as tech debt and proposed a `google_compute_zones` data source as the proper fix. The proper fix was parked because "the failure mode is loud (immediate Terraform error) and the region list changes rarely". That framing assumed the only failure mode of pinning was the zone-missing one. Capacity exhaustion is a second, louder failure mode that the same pin enables.

A note on the error code. `GCE_STOCKOUT` is the canonical `StatusCondition.code` value GKE stamps onto the cluster resource for this case. Compute Engine itself surfaces a different identifier, `ZONE_RESOURCE_POOL_EXHAUSTED`, on the underlying `instances.insert` operation. Both refer to the same physical condition observed at different API surfaces. Searches across mixed logs and docs therefore read like two separate problems.

## Resolution

Omit `node_locations` on the Standard-cluster resource. By default, a regional GKE cluster replicates each node pool across the three zones of the control plane. The provisioner is then free to sidestep a tight zone instead of failing the request. For the ephemeral-PR fleet, cluster identity is name and region; the zone of its nodes carries no meaning to anything downstream of provisioning.

When a region lacks one of its three default zones for a needed machine type, prefer a `google_compute_zones` data source filtered by `UP` plus machine-type availability. Feed that discovered list into `node_locations`. The shape replaces a literal pin with a discovered list. It preserves the "loud failure" property the original commit valued, without forfeiting platform-side zone substitution.

Region rotation in the cluster-pool is a partial mitigation that bounds stockout exposure across regions but not across zones. The rotation walks `last_region_index` over the nine regions in the pool, so a tight zone in one region is naturally retried in a different region on the next claim. That property reduced the practical hit rate to four events in a week. A single failure still blocks the cluster lifecycle of a PR until the next event-driven retry. The `-b` pin therefore remains a recurring tax even with rotation in place.

## Adoption Rule

For ephemeral, short-lived GKE-Standard clusters whose identity is not tied to a specific zone, prefer omitting `node_locations` over pinning. The platform default trades nothing the workload values and surrenders the only mitigation against zone-local stockouts the platform offers.

When a single-zone pin is genuinely required (compliance, persistent-disk locality, GPU availability windows), pair it with a Compute Engine reservation in that zone or with explicit retry-on-stockout logic. Treat the pin and its mitigation as a single decision, not two.

When a zone-suffix literal appears in any cluster module, audit it against the full region list the module is invoked with. A literal like `${var.region}-b` works only as long as every region in scope carries the `-b` zone *and* has spare capacity for the requested machine type. Both conditions are silent and time-varying. Discovering zones via a `google_compute_zones` data source filtered by live machine-type availability turns both into plan-time errors instead of run-time provisioning failures.

## How to Detect

Signs that a single-zone `node_locations` pin is the proximate cause of a provisioning failure:

- The cluster resource carries `status: ERROR` and `statusConditions[].code: GCE_STOCKOUT` (or `ZONE_RESOURCE_POOL_EXHAUSTED` on the underlying `instances.insert` operation).
- A `gcloud compute regions describe <region>` call returns full headroom on every CPU and instance-type quota in scope, ruling out a quota guard.
- The cluster `nodeLocations` field contains exactly one entry, and that entry is the zone named in the error message.
- A retry of the same plan against a different region in the rotation succeeds without changes to quota, machine type, or node count.

When all four hold, the failure is a zone-local stockout amplified by a single-zone pin, not a quota error and not a region-wide outage. Removing the pin or feeding `node_locations` a discovered multi-zone list eliminates the amplifier.
