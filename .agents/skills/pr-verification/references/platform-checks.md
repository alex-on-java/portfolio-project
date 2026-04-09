# Platform Checks — ArgoCD

ArgoCD manages ALL infrastructure: operators, platform config, and workloads.
Everything in the cluster flows through ArgoCD.

## What Should Be Green

**ArgoCD applications** (check `-n argocd`): every application should be both Synced AND Healthy.
- `bootstrap` — the root application; its `targetRevision` must match the PR branch
- Operator apps (cert-manager, kargo, argo-rollouts): Synced + Healthy; their pods must be running
- `kargo-config` — deploys Kargo project, stages, and warehouse configuration
- `analysis-templates` — deploys the shared health check template
- Workload apps (one per environment: dev, stg, prd): each must be Synced + Healthy

**Operator pods**: check that actual pods are running in cert-manager, kargo, and argo-rollouts
namespaces. A Helm app can be "Synced" while its pods are CrashLooping.

**Workload app branches**: each workload ArgoCD app tracks a stage branch
(`stage/{branch-prefix}/{app}-{env}`). The synced revision must be a recent Kargo-authored commit.

## Key Configuration

ApplicationSets derive template variables from annotations on the ArgoCD cluster secret
(`in-cluster` in `argocd` namespace):
- `branch-prefix` — determines the stage branch namespace (e.g., `pr-2`)
- `target-revision` — the git branch ApplicationSets read for operator values and kargo config

If these annotations are wrong, all ApplicationSets will target incorrect branches.

## Sync Wave Ordering

Applications deploy in a fixed order. A failure in an early wave blocks later waves:

namespaces (wave -100) → cert-manager (wave -50) → kargo + argo-rollouts (wave 0) →
analysis-templates (wave 100) → workloads (wave 200) → kargo-config (wave 300)

If a later-wave app is not syncing, check whether an earlier-wave dependency is healthy first.
