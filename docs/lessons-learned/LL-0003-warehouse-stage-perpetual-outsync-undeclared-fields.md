# LL-0003: Kargo Admission Webhook Injects Defaults Causing OutOfSync

**Summary**: Kargo's admission webhook injects default values (`freightCreationPolicy`, `strictSemvers`, `discoveryLimit`) during resource admission. If these fields are not declared in the Git manifest, ArgoCD sees permanent OutOfSync because the live state has values that Git doesn't.

## What happened

Warehouse and Stage resources showed perpetual OutOfSync in ArgoCD despite no manual changes. ArgoCD kept showing diff lines for fields that never appeared in the Git manifests.

## Root cause

Kargo's admission webhook acts as a mutating webhook that injects default values during CREATE/UPDATE. For example:

- `freightCreationPolicy: Automatic` on Warehouse
- `strictSemvers: true` on image subscriptions
- `discoveryLimit: 5` / `20` on subscriptions
- `strictSemvers: true` on git subscriptions using `NewestFromBranch` — even though semver filtering is semantically irrelevant for branch-based selection

These fields exist in the live state (post-admission) but not in Git, so ArgoCD sees a permanent diff.

## Resolution

Declare all webhook-injected defaults explicitly in the Git manifests, matching the post-admission live state. This makes the diff clean without requiring ArgoCD `ignoreDifferences`.

## How to detect

`argocd app diff <app>` shows fields present in live state but absent in Git. Check if the fields match Kargo CRD default values.
