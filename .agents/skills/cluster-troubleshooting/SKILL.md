---
name: cluster-troubleshooting
description: |
  Diagnose cluster provisioning and activation failures for ephemeral PR clusters.
  Use when no cluster exists for a PR, a cluster is in failed state, the cluster
  is unreachable, or the activation annotations are wrong.
user-invocable: false
---

## Architecture Context

Three repositories work together: the public repo dispatches a `pr-push` event →
the cluster-pool repo claims or provisions a cluster → the infra repo runs Terraform to create
the GKE cluster. All pool state lives in a GCS bucket — not in Git.

## Diagnostic Approach

Start at the pool state and narrow down:

**1. Is there a cluster entry for this PR?**
Check the pool state JSON in GCS. The bucket name is stored as `POOL_STATE_BUCKET` in the
cluster-pool repo's GitHub Actions variables. Look for a cluster entry with `assigned_pr`
matching the PR number.

**2. What state is the cluster in?**
- `assigned` — cluster exists and is activated. If it is unreachable, refresh credentials
  (`gcloud container clusters get-credentials`). Two stale entries in kubeconfig pointing to
  deleted clusters are normal; use the current cluster name from the pool state to identify the
  correct context.
- `provisioning` — Terraform is still running. Check the infra repo workflow run for progress.
- `failed` — provisioning failed. Check the infra repo workflow run logs for the root cause
  (quota, API error, region issue). A failed entry stays in state until cleaned up by scheduled
  checks; it does not block a retry.
- No entry — the PR push dispatch either didn't arrive or pool-ctl errored before writing state.
  Check the cluster-pool repo `on-pr-push.yml` workflow run.

**3. Did provisioning fail?**
Infra runs are in the `portfolio-project-infra` repo, workflow `cluster-lifecycle.yml`.
The run ID is stored in the cluster entry. Common causes: quota exceeded in the selected region,
GCP API errors, Terraform state lock. The workflow tries regions in round-robin — a failure in
one region is independent of others. A manual re-run (or new PR push) triggers a fresh attempt.

**4. Did activation succeed?**
Activation patches three resources. Check each directly on the cluster:
- ArgoCD cluster secret (`in-cluster` in `argocd` namespace): annotations `branch-prefix` and
  `target-revision` must be set to the PR's values
- `cluster-identity` ConfigMap (in `kargo-shared-resources` namespace): `branchPrefix` and
  `sourceBranch` must match
- Bootstrap Application (`bootstrap` in `argocd` namespace): `spec.source.targetRevision` must
  equal the PR branch; `argocd.argoproj.io/skip-reconcile` annotation must be absent

If annotations are wrong, the bootstrap app reads the wrong branch and all ApplicationSets
target incorrect stage branches.

**5. Is the pool stopped?**
Pool status `stopped` with `target_size: 0` means the TTL expired (4 hours after last claim).
A stopped pool still services claims on demand — it auto-starts when a new PR push arrives.
If manually stopped, new provisioning will not trigger.

## Escape

If none of the above explains the issue: check GCP Console for the cluster status, look at the
Terraform state in the GCS state bucket, or check IAM and Workload Identity Federation
configuration in the infra repo.
