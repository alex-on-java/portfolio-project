# LL-0064: GCP Audit Log Is Silent on `firewalls.list` and `clusters.describe` by Default

## Summary

Cloud Audit Logs ship with Admin Activity enabled and Data Access disabled. Google classifies `compute.firewalls.list`, `compute.firewalls.get`, and `google.container.v1.ClusterManager.GetCluster` as `ADMIN_READ`, a Data Access permission type. Under the default configuration none of these read calls produce a log entry. A post-mortem that reads the audit log to reconstruct gcloud calls sees writes only. It cannot tell apart code paths that differ only in their read calls.

## What Happened

A forensic reconstruction of `cluster-lifecycle.yml` destroy failures needed the audit log to identify which branch of a sweep step had executed. The step shape was roughly:

```bash
CLUSTER_UID="$(gcloud container clusters describe --format='value(id)' ...)"
[[ -z "$CLUSTER_UID" ]] && exit 0
gcloud compute firewall-rules list --filter="..." --format='value(name)' \
  | xargs -r gcloud compute firewall-rules delete --quiet
```

Two failure modes produce the same outward signal: "step exits 0 with no firewall deleted." Under branch (A), `describe` fails fast and `CLUSTER_UID` is empty. Under branch (B), `describe` succeeds and `firewalls.list` returns empty. Either way the script exits 0.

Audit-log evidence from the failing run showed no `firewalls.delete` event in the sweep window. That ruled out a third hypothesis in which the firewall had been deleted and then recreated. The log did not show the `firewalls.list` or `clusters.describe` calls themselves. As the investigation captured it directly: "GCP audit logs are silent on `firewalls.list` and `clusters.describe` (those are Data Read events, not Admin Activity, not logged by default). So I still cannot see which branch the script took." Branch (A) versus branch (B) had to be discriminated by GitHub Actions check-run annotations. Specifically, the presence or absence of `::warning::Could not resolve cluster UID` selected the branch, not the audit log.

## Root Cause

Cloud Audit Logs are organized into four categories. Admin Activity logs (`ADMIN_WRITE` permissions) are always on and cannot be disabled. Data Access logs cover three permission types: `ADMIN_READ`, `DATA_READ`, and `DATA_WRITE`. All three are disabled by default for every service except a small set of BigQuery exceptions. Enabling them requires an explicit IAM audit-config change at the project, folder, or organization level, and incurs the standard Cloud Logging ingestion charge.

Per-method categorization is published in the per-service audit-logging reference. On Compute Engine, `v1.compute.firewalls.list` and `v1.compute.firewalls.get` are listed under `ADMIN_READ`. Their write siblings `v1.compute.firewalls.insert`, `v1.compute.firewalls.delete`, `v1.compute.firewalls.patch`, and `v1.compute.firewalls.update` are listed under `ADMIN_WRITE`. For GKE, `google.container.v1.ClusterManager.GetCluster` and `ListClusters` are listed under `ADMIN_READ`, while `CreateCluster`, `DeleteCluster`, and siblings are listed under `ADMIN_WRITE`. These `ADMIN_READ` calls read configuration and metadata, not user data, and yet still fall on the Data Access side of the default-off divide.

Two consequences follow. First, the audit log under the default configuration is a record of state changes, not a record of API calls. Read operations and their failures stay invisible. Second, a code path that branches on a read call leaves no fingerprint the audit log alone can reconstruct. Branch identity must come from a different signal. Useful signals include stdout captured at run time, a warning annotation, the absence of a later write one branch would have produced, or a parallel observation against the resource.

A note on the candidate framing. Session-log narration used "Data Read" to label the missing events. Per the Google audit-logging reference, the published categorization for these specific methods is `ADMIN_READ`. Both subtypes share the same Data Access bucket, the same default-off behavior, and the same explicit opt-in. Subtype matters when filtering by permission type at enable-time, not for the surface symptom of the missing log entry.

## Resolution

In the live investigation the fix was a different evidence source. GitHub Actions check-run annotations carried the `::warning::Could not resolve cluster UID` line that branch (A) would have emitted, and their absence selected branch (B). That conclusion is structural rather than specific to one step. Any script that may branch silently on a read call must emit a marker on each branch. A `::warning::` line, a `::notice::` line, a stdout breadcrumb, or an exit-code distinction will do. The post-mortem reads the marker, not the audit log.

A project that wants the audit log to be the authoritative record changes that default. The enable surface is the IAM audit-config of the project (or a higher resource), per the published guide at `cloud.google.com/logging/docs/audit/configure-data-access`. Costs scale with read volume. Listing firewalls runs on every CI sweep, every Terraform refresh, and every console page-load that lists firewalls. The published guidance specifically warns against blanket enablement on busy services. A pragmatic middle ground enables `ADMIN_READ` on a small set of services where read-call evidence pays for itself, such as `compute.googleapis.com` and `container.googleapis.com`. Leave `DATA_READ` and `DATA_WRITE` off everywhere.

## Adoption Rule

Treat the GCP audit log under the default configuration as a write-only ledger. Any CI step that may take silent branches on a read call must attach a per-branch marker the post-mortem can read. Acceptable markers include a `::warning::` annotation, a `set -x` echo, or a sentinel write that pins which branch ran. That marker is the load-bearing artifact; the audit log corroborates writes but does not reconstruct the call sequence.

Should enabling Data Access logs be on the table, opt in per service and per permission type, not project-wide. The Google audit-logging reference for the target service lists which methods change category under each opt-in. Cost of `ADMIN_READ` on `compute.googleapis.com` is bounded by control-plane traffic; cost of `DATA_READ` on a busy object-storage or database service can dominate the logging bill.

## How to Detect

Signs that an investigation is hitting the read-call silence:

- An audit-log query under `logName="projects/<p>/logs/cloudaudit.googleapis.com%2Factivity"` returns rows for writes (`firewalls.delete`, `firewalls.insert`, `CreateCluster`, `DeleteCluster`). It returns no rows for reads (`firewalls.list`, `firewalls.get`, `GetCluster`, `ListClusters`) over the same window from the same service account.
- A `logName="projects/<p>/logs/cloudaudit.googleapis.com%2Fdata_access"` query returns zero entries across the retention window, regardless of read activity the CI logs prove must have occurred.
- A post-mortem cannot distinguish between two code paths whose only observable difference is the set of read calls each issues.

The confirming check is `gcloud logging read 'protoPayload.methodName="v1.compute.firewalls.list"' --limit=1` over a window where the CI run is known to have made the call. An empty result against the default project configuration is the expected outcome. It is not evidence that the call did not happen.
