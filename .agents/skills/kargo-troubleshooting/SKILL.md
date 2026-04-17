---
name: kargo-troubleshooting
description: |
  Diagnose Kargo promotion pipeline issues.
  Use when freight is not detected, stages are not promoting,
  promotions are failing, or stage branches are not being updated.
user-invocable: false
---

## Architecture Context

Kargo polls git and image sources (Warehouse), packages discoveries into immutable Freight, then
drives promotions through Stages by running a ClusterPromotionTask: render the manifest, commit
it to a stage branch, and nudge the matching ArgoCD Application. The flow:

```
Warehouse → Freight → Stage → stage-branch commit → ArgoCD sync
```

**Project↔namespace convention** (contract): a Kargo Project lives in a namespace of the same
name — the admission webhook enforces this. Two Projects exist on the cluster today:

- `portfolio-project` — workload pipelines (dev/stg/prd Stages).
- `observability-project` — platform-workload pipelines (currently the convergence-checker
  reporter). Its Stage is terminal and unverified today; not a permanent rule — re-check when
  the pipeline shape changes.

Discover Projects + Stages at runtime:

```
kubectl --context <ctx> get projects.kargo.akuity.io -A
kubectl --context <ctx> get stages -A
kubectl --context <ctx> get warehouses -A
```

**ClusterPromotionTask ↔ cluster-identity** (contract): promotion task steps expand template
variables from the `cluster-identity` ConfigMap (`branchPrefix`, `domainPrefix`, `overlayTarget`,
`clusterLifecycle`, ...). If pool-ctl has not written the PR-context keys yet (still `"pending"`),
template expansion fails silently — Kargo breakage here often traces back to a cluster-activation
issue (see `cluster-troubleshooting`).

## Diagnostic Approach

Follow the pipeline from its earliest broken point.

**1. Is the Warehouse detecting new artifacts?**
Inspect Warehouse status for the latest image digest and git commit:

```
kubectl --context <ctx> describe warehouse -n <project-ns> <warehouse-name>
```

Polling interval is configurable per overlay — detection should happen within a single interval
of CI completing. If nothing is detected, confirm the subscription (registry, branch,
`includePaths` with a `glob:` prefix for wildcards) matches what CI actually pushes.

**2. Is Freight being created?**
Freight requires *all* Warehouse subscriptions satisfied. If image is detected but no Freight
appears, confirm the git subscription is polling the right branch and its `includePaths` match
changed paths:

```
kubectl --context <ctx> get freight -n <project-ns>
```

**3. Is the Stage promoting?**
`kubectl --context <ctx> get stages -n <project-ns>`. Non-promotion reasons:
- No upstream freight available (downstream stage waiting on upstream verification).
- Auto-promotion disabled for this stage (check `ProjectConfig` + per-stage labels — ephemeral
  overlay typically enables it via a label-selector patch).
- A `Running` Promotion already exists for this Stage.

**4. Is the Promotion failing?**
Fetch the failing Promotion and inspect `status.steps` — each step reports its own status. Steps
are declared in the Project's ClusterPromotionTask spec; different Projects may use different
task variants, so **read the spec** rather than assuming a step sequence.

Common step-class failures:
- `git-*` steps → GitHub App credentials (Secret in `kargo-shared-resources`) expired or lacking
  permission on the target branch.
- `kustomize-*` steps → overlay path missing on the source branch. Overlay paths are often
  templated from cluster-identity keys; a mis-activated cluster surfaces here.
- `argocd-update` → target Application missing, or missing
  `kargo.akuity.io/authorized-stage: "<project>:<stage>"` annotation. Renaming either the Project
  or the Stage requires updating this annotation on every dependent Application.

**5. Stage branches**
A successful Promotion leaves one commit on `stage/<branch-prefix>/<stage-name>`. Stage branches
hold a **pre-rendered manifest**, not a kustomize tree — the Application targeting that branch
uses `path: .`.

The stage-name segment is per-Stage: workload Stages include an env suffix (e.g.
`portfolio-project-dev`); terminal platform Stages may have no suffix (e.g. `convergence-checker`).
Verify branch existence at the remote rather than assuming a naming convention:

```
git ls-remote origin 'refs/heads/stage/<branch-prefix>/*'
```

If a branch exists but its HEAD predates the expected Freight, the Promotion succeeded for an
older Freight — confirm the current Promotion targets the right Freight ID.

**6. Is verification gating downstream?**
A Stage may declare verification (e.g. an AnalysisRun) that must pass before downstream Freight
flows. A `Verified: false` Stage blocks downstream. Not every Stage has verification —
inspect `status.verifications` on the Stage to see whether it applies here.

## Escape

Controller logs carry promotion-step detail and polling errors:

```
kubectl --context <ctx> logs -n kargo -l app=kargo-controller
kubectl --context <ctx> logs -n kargo -l app=kargo-management-controller
```

Management-controller covers `ProjectConfig` and auto-promotion policy issues.
