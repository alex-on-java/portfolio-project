---
name: argocd-troubleshooting
description: |
  Diagnose ArgoCD sync, health, and infrastructure deployment issues.
  Use when ArgoCD applications are degraded, not syncing, or platform
  infrastructure (operators, CRDs, ApplicationSets) is broken.
user-invocable: false
---

## Architecture Context

ArgoCD manages everything in the cluster: operators, platform config, Kargo setup, and workloads.
All resources flow through a single bootstrap Application that deploys ApplicationSets.
ApplicationSets derive template variables from annotations on the ArgoCD cluster secret.

## Diagnostic Approach

**1. Which application is unhealthy?**
Distinguish between the root bootstrap app, operator apps (cert-manager, kargo, argo-rollouts),
and workload apps. If `bootstrap` itself is degraded, everything downstream is affected.

**2. Is it a sync error or a health error?**
- Sync error: ArgoCD cannot apply the manifests (wrong branch, missing CRD, resource conflict,
  repo access denied)
- Health error: manifests applied but resources did not become healthy (pod crash, readiness probe failing)

These require different investigation paths.

**3. Is the sync wave ordering the issue?**
Applications deploy in waves:
namespaces (-100) → cert-manager (-50) → kargo + argo-rollouts (0) →
analysis-templates (100) → workloads (200) → kargo-config (300)

A later-wave app will not sync until earlier waves are healthy. Always check earlier waves before
debugging a later-wave app.

**4. Is the targetRevision correct?**
ApplicationSets use `{{metadata.annotations.target-revision}}` from the `in-cluster` cluster
secret to determine which git branch to read. If this annotation points to the wrong branch
(e.g., `master` instead of the PR branch), all apps will sync from wrong content.
Verify the annotation on the `in-cluster` secret in the `argocd` namespace.

**5. Is it a CRD timing issue?**
On a fresh cluster, CRDs must be installed before resources that use them. Rollout CRDs come
from argo-rollouts (wave 0); Kargo CRDs come from kargo (wave 0). Resources using these CRDs
appear in later waves. If the operators are still starting, the CRDs may not yet be registered —
wait and check again.

**6. Helm-based vs git-based apps**
Operator apps use Helm charts pinned to specific versions; check chart version, values file path,
and Helm diff for unexpected changes. Git-based apps (workloads, kargo-config, analysis-templates)
use paths in the repo — verify the path exists on the targetRevision branch.

## Escape

ArgoCD controller logs (`-n argocd`, `argocd-application-controller`) contain detailed
reconciliation errors. Repo-server logs contain git and Helm fetch errors. Check these when
the status output does not give enough detail.
