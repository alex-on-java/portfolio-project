---
name: argocd-troubleshooting
description: |
  Diagnose ArgoCD sync, health, and infrastructure deployment issues.
  Use when ArgoCD applications are degraded, not syncing, or platform
  infrastructure (operators, CRDs, ApplicationSets) is broken.
user-invocable: false
---

## Architecture Context

ArgoCD manages every cluster resource via a bootstrap Application → ApplicationSets →
Applications. Template variables (branch prefix, target revision, domain) come from annotations
on the `in-cluster` Secret in `argocd` and from the `cluster-identity` ConfigMap (see
`cluster-troubleshooting` for the contract). The cluster's manifest state is a **dependency
graph**: later waves depend on earlier waves, and some Applications depend on artifacts (stage
branches) that only exist after Kargo has promoted.

Discover the live tree before reasoning about it:

```
kubectl --context <ctx> get applicationsets -n argocd \
  -o json | jq -r '.items[] | "\(.metadata.annotations["argocd.argoproj.io/sync-wave"] // "none")\t\(.metadata.name)"' \
  | sort -n
kubectl --context <ctx> get applications -n argocd
```

## Diagnostic Approach

**1. Which Application is the root of the failure?**
Drill from the failing app upward. If `bootstrap` or a platform-infra Application is degraded,
everything downstream is affected. Ignore workload noise until the infrastructure layer is Healthy.

**2. Sync error vs health error?**
- **Sync error** — ArgoCD cannot apply manifests (wrong branch, missing CRD, resource conflict,
  repo access denied).
- **Health error** — manifests applied, resources did not become healthy (pod crash, probe
  failing, webhook rejecting).

These need different lenses. Read the Application's `status.conditions` and
`status.operationState` before guessing.

**3. Is wave ordering the issue? (dependency graph)**
ApplicationSets declare `argocd.argoproj.io/sync-wave` (negative to positive). A later-wave
Application cannot sync until earlier waves are Synced + Healthy. When debugging a later-wave
Application, verify the earlier waves first — the symptom usually lives upstream.

**4. Is the Application waiting on a Kargo-produced stage branch? (`targetRevision` pattern)**
ApplicationSets rendered-by-Kargo point at `stage/<branch-prefix>/<stage-name>`. That branch
only exists **after** Kargo's first promotion. If such an ApplicationSet is `OutOfSync` or
reports a missing-ref error on a fresh cluster, check whether the upstream Kargo ApplicationSet
(often a later wave) has completed its first promotion. A transient window of `OutOfSync` is
expected here, not pathological — bound it by the gate's safety timeout (see
`app-troubleshooting`).

**5. `ignoreDifferences` pattern: does the Application write to its own declared resource?**
ArgoCD reconciles toward the declared state. When an Application writes runtime state into a
ConfigMap or Secret that the *same* Application also declares, ArgoCD reverts the writes on
every sync — reconcile fight, typically every ~30s. The fix is an `ignoreDifferences` block on
the mutated field (usually `/data`).

This pattern applies to any Application that persists its own state into Kubernetes resources
(heartbeat, cached computation, accumulated counters). Presence of `ignoreDifferences` on a
self-writing Application is load-bearing; removing it reopens the fight. Absence on a
self-writing Application is a failure mode to look for.

**6. Is it a CRD timing issue?**
On a fresh cluster, CRDs shipped by operator Applications (typically wave 0) must register before
later-wave Applications that use them can sync. If operators are still starting, CRD-using
Applications appear stuck — wait and check again.

**7. Is `targetRevision` on the in-cluster Secret correct?**
ApplicationSets derive `{{metadata.annotations.target-revision}}` and `branch-prefix` from the
`in-cluster` Secret in `argocd`. If these are wrong, every Application syncs the wrong branch.
Verify:

```
kubectl --context <ctx> get secret in-cluster -n argocd -o jsonpath='{.metadata.annotations}'
```

If wrong → `cluster-troubleshooting` (activation did not patch the Secret).

**8. Helm-based vs git-based Applications**
Helm-based Applications pin a chart version + values file path; diff the chart version and values
for unexpected changes. Git-based Applications use repo paths — verify the path exists on the
resolved `targetRevision`.

## Escape

Application controller logs carry reconciliation errors:

```
kubectl --context <ctx> logs -n argocd -l app.kubernetes.io/name=argocd-application-controller
```

Repo-server logs carry git and Helm fetch errors. Check these when the status output is cryptic.
