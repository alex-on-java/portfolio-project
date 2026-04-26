---
name: cluster-troubleshooting
description: |
  Diagnose cluster provisioning and activation failures for ephemeral PR clusters.
  Use when no cluster exists for a PR, a cluster is in failed state, the cluster
  is unreachable, or the activation annotations are wrong.
user-invocable: false
---

## Architecture Context

Three repositories cooperate to produce a PR's ephemeral cluster: the main repo dispatches a
`pr-push` event → the cluster-pool repo claims or provisions a cluster → the infra repo runs
Terraform to create the GKE cluster. Pool bookkeeping lives in a GCS bucket (not Git);
per-cluster runtime state lives in the cluster itself.

### `cluster-identity` ConfigMap — cross-layer contract

One ConfigMap in `kargo-shared-resources`, two writers, many readers:

- **Terraform (seed)** — sets cluster-shape keys (overlay target, lifecycle, base domain, ArgoCD
  namespace) during bootstrap. PR-context keys that pool-ctl will own are seeded to placeholder
  values (`"pending"`).
- **pool-ctl (activation)** — overwrites the PR-context keys (`branchPrefix`, `sourceBranch`,
  `domainPrefix`, `prCommitSha`, `activationTimestamp`, ...) at claim time and re-asserts them on
  every reuse.

Readers span the cluster:
- ApplicationSets template `targetRevision` and paths from it.
- Kargo ClusterPromotionTasks expand template variables from it (see `kargo-troubleshooting`).
- In-cluster reporters read PR commit SHA and the ArgoCD namespace from it.
- The watchdog reads the activation timestamp and commit SHA from it.

**Re-apply hazard**: writer sets overlap. A Terraform re-apply reverts the PR-context keys to
`"pending"` until pool-ctl runs again. Expect cluster-wide transient breakage after a re-apply;
the fix is a fresh PR-push dispatch (or manual pool-ctl reactivation).

### Watchdog CronJob — liveness gate for in-cluster reporters

Any in-cluster Deployment whose job is to *report* PR status via GitHub commit status is silent
when it crashes — a missing status is worse than a failing one, because the PR is then
ambiguous. The watchdog (Terraform-provisioned CronJob) reads a reporter's heartbeat ConfigMap
and, past a configurable grace-period + staleness window, posts a `failure` commit status in the
reporter's place. Without this, the gate silently degrades from "blocking" to "confusing."

The watchdog signs a JWT from a Secret (GitHub App credentials). Secret key names and private-key
format are contract — see `app-troubleshooting` for the reporter side and the infra repo's
watchdog module for the watchdog side.

## Diagnostic Approach

**1. Is there a cluster entry for this PR?**
Pool state in the GCS bucket (`POOL_STATE_BUCKET` in cluster-pool GitHub Actions vars). Look for
an entry with `assigned_pr` matching the PR.

**2. What state is the cluster in?**
- `assigned` — cluster up. If unreachable, refresh credentials
  (`gcloud container clusters get-credentials`). Stale kubeconfig entries for deleted clusters
  are normal; use the current cluster name from pool state to identify the right context.
- `provisioning` — Terraform still running; check the infra-repo workflow run.
- `failed` — provisioning failed; infra workflow logs carry the cause (quota, API error, region).
  A failed entry does not block retry.
- No entry — the PR-push dispatch did not arrive or pool-ctl errored before writing state.
  Check cluster-pool's `on-pr-push.yml` workflow run.

**3. Did provisioning fail?**
Infra workflow (`cluster-lifecycle.yml`) logs. Regions are tried round-robin — one region's
failure is independent of others. A manual re-run (or a new PR push) triggers a fresh attempt.

**4. Did activation succeed? (inspect `cluster-identity`)**
The primary evidence is the ConfigMap itself:

```
kubectl --context <ctx> get cm cluster-identity -n kargo-shared-resources -o yaml
```

Look for:
- PR-context keys are **not** `"pending"` — pool-ctl wrote them.
- `prCommitSha` matches the PR's HEAD (`git rev-parse HEAD`).
- `activationTimestamp` is recent and plausible.
- Terraform-owned keys (overlay, lifecycle, argocd namespace, base domain) are set.

If PR-context keys are missing or `"pending"`, pool-ctl either didn't run or errored. If Terraform
was re-applied after activation, the re-apply reverts them (see re-apply hazard above) — the
cure is to re-dispatch the PR so pool-ctl re-activates.

Wrong activation propagates: the `in-cluster` Secret in `argocd` carries matching annotations
(`branch-prefix`, `target-revision`). If those are wrong, ApplicationSets target the wrong branch
— see `argocd-troubleshooting` step 7.

**5. Is the watchdog healthy?**
The watchdog is a CronJob; check its recent Job runs. Discover by CronJob name — today, a
single watchdog CronJob runs in the reporter's namespace:

```
kubectl --context <ctx> get cronjobs -A | grep -i -E 'watchdog|gate'
kubectl --context <ctx> get jobs -n <watchdog-ns> \
  -l batch.kubernetes.io/cronjob-name=<watchdog-name> \
  --sort-by=.metadata.creationTimestamp | tail -5
kubectl --context <ctx> logs -n <watchdog-ns> job/<job-name>
```

The watchdog logs its decision per run (no activity / within grace / heartbeat fresh / stale →
posting failure). A silent watchdog on a cluster past the grace period is itself a failure mode
— the backstop isn't armed.

**6. Pool stopped?**
Pool status `stopped` with `target_size: 0` means the pool TTL expired. On new PR push it
auto-starts; if *manually* stopped, provisioning won't trigger until someone restarts the pool.

## Escape

GCP Console for cluster existence. Terraform state in the GCS state bucket. IAM and Workload
Identity Federation configuration in the infra repo.
