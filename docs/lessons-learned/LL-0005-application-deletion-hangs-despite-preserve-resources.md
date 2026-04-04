# LL-0005: ArgoCD Application Finalizer Dual-Source Problem

**Summary**: The ArgoCD Application finalizer (`resources-finalizer.argocd.argoproj.io`) is added by two independent code paths. Blocking only one leaves the finalizer active, preventing clean ephemeral cluster teardown.

## What happened

After configuring `preserveResourcesOnDeletion: true` on ApplicationSets for ephemeral clusters, Applications still had the `resources-finalizer.argocd.argoproj.io` finalizer. Deleting the ArgoCD namespace hung because the finalizer triggered resource cleanup on a cluster being torn down.

## Root cause

Two independent code paths add the finalizer:

1. **Application controller** — automatically adds the finalizer to any Application it reconciles. Blocked by setting `preserveResourcesOnDeletion: true` on the ApplicationSet's `syncPolicy`.
2. **ApplicationSet controller** — propagates finalizers from the ApplicationSet template to generated Applications. Blocked by setting `template.metadata.finalizers: []` (empty array) in the ApplicationSet spec.

Both must be addressed. This is documented in ArgoCD GitHub issues (#18201, applicationset#254) but not in the main documentation.

## Resolution

Applied both mitigations in the ephemeral Kustomize overlay:

```yaml
patches:
  - target:
      kind: ApplicationSet
    patch: |
      - op: add
        path: /spec/syncPolicy
        value:
          preserveResourcesOnDeletion: true
      - op: add
        path: /spec/template/metadata/finalizers
        value: []
```

## How to detect

`kubectl get applications -n argocd -o jsonpath='{range .items[*]}{.metadata.name}: {.metadata.finalizers}{"\n"}{end}'` — if any Application has the finalizer on an ephemeral cluster, one of the two paths is not blocked.
