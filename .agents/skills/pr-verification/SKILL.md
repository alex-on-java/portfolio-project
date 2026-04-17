---
name: pr-verification
description: |
  Verify end-to-end deployment health.
  Triggers when asked to verify a deployment, check if changes are live, confirm the pipeline completed, or validate the PR environment. Also must be loaded after pushing to a feature branch.
user-invocable: false
---

## Architecture Context

A PR push produces pre-gate CI checks and then, once an ephemeral cluster is live, a single
aggregated commit status — `GitOps Convergence Gate` — that reflects the health of every ArgoCD
Application and every Kargo Stage in the cluster. The gate is the source of truth for deployment
health; drop into a per-layer skill only when the gate is `pending` past its normal window or
reports `failure`.

**Three lifecycle owners share the gate-status context, in sequence:**

1. **Cluster-pool workflow** posts `pending` at PR push; posts terminal status if provisioning is
   skipped by policy or fails outright.
2. **In-cluster reporter** (a Deployment whose job is to evaluate cluster state and post commit
   status) takes over once the cluster is live and its pod is Ready; posts `pending`/`success`/
   `failure` per evaluation cycle.
3. **Watchdog CronJob** posts `failure` if the reporter goes silent past its staleness threshold —
   otherwise a crashed reporter would silently convert the gate from "blocking" to "confusing."

The status **description** is the primary signal — read it first; it names the offending resource
or the silent reporter.

## Diagnostic Approach

Check each in order — stop and report if a layer fails; downstream checks are meaningless without
the upstream layer being green.

**1. Pre-gate layer — CI**
`gh run list` for the latest run on this branch. If any required job failed, report which one and
stop.

**2. Pre-gate layer — Ephemeral Cluster**
The `Ephemeral Cluster` commit status confirms Terraform provisioned and pool-ctl activated:

```
gh api repos/<owner>/<repo>/commits/$(git rev-parse HEAD)/status \
  --jq '.statuses[] | select(.context == "Ephemeral Cluster")'
```

If not green within a minute, provisioning may be in flight — a cluster from scratch takes ~10+
minutes. Wait with `/loop 15m`, using `date` to track elapsed time. **Always cancel the loop**
once the status resolves — a forgotten loop keeps reporting stale state while you're already
debugging.

Not green after the wait → `cluster-troubleshooting`.

**3. Gate layer — GitOps Convergence Gate**
The aggregated status:

```
gh api repos/<owner>/<repo>/commits/$(git rev-parse HEAD)/statuses \
  --jq '.[] | select(.context == "GitOps Convergence Gate")'
```

(Note: list form `.../statuses` is GET-only; `.../statuses/{sha}` is POST-only.)

`state` tells you the outcome. `description` tells you *why*.

## Dispatch

When the gate is `pending` past its normal window or `failure`, use the status description to
pick the next skill:

- Description mentioning "watchdog" or the reporter being unresponsive → `app-troubleshooting`
  (reporter pod) *and* `cluster-troubleshooting` (watchdog infra). Both are in play.
- Description naming an ArgoCD Application (Degraded / OutOfSync / sync failure) →
  `argocd-troubleshooting`.
- Description naming a Kargo Stage (promotion failure, stage unhealthy) →
  `kargo-troubleshooting`.
- Gate stuck `pending` with an empty or vague description, or no description movement at all →
  `cluster-troubleshooting` (activation keys in `cluster-identity` may be missing or still at
  placeholder values — the reporter has no PR context to report against).

**Correlation key.** The reporter posts statuses against the commit SHA held in
`cluster-identity.prCommitSha` — *not* the PR's current HEAD. If statuses arrive on an
unexpected SHA, a Terraform re-apply or a stale activation may have left the reporter posting
against a previous commit. See `cluster-troubleshooting` for the re-apply hazard.

Unsure where the symptom lives? Inspect the reporter's logs directly. Discover the in-cluster
reporter by name — today, one reporter Deployment runs in the cluster:

```
kubectl --context <ctx> get deploy -A -o name | grep -i -E 'checker|reporter|gate'
kubectl --context <ctx> logs -n <reporter-ns> deployment/<reporter-name>
```

## Final Consistency

All pre-gate + gate statuses green → report success. No deeper ritual is needed; the gate
aggregates Application and Stage health across the cluster by design.
