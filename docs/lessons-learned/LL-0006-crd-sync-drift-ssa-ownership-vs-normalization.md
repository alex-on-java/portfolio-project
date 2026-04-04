# LL-0006: SSA vs ignoreDifferences for CRD Sync Drift

**Summary**: ServerSideApply (SSA) controls field ownership, not API-server value normalization. Use `ignoreDifferences` for fields the API server normalizes away (like `preserveUnknownFields: false`). SSA is required for cert-manager because its CRDs exceed the 262KB `last-applied-configuration` annotation limit.

## What happened

Argo Rollouts CRDs showed perpetual OutOfSync on `spec.preserveUnknownFields`. Enabling SSA on the argo-rollouts ApplicationSet did not fix the drift. Meanwhile, cert-manager also needed SSA, but for a completely different reason.

## Root cause

Two distinct problems requiring different solutions:

1. **Argo Rollouts CRD drift**: The upstream Helm chart includes `preserveUnknownFields: false` in CRD templates, but the API server normalizes this away (false is the default for `apiextensions.k8s.io/v1`). ArgoCD sees a diff that can never converge. SSA does not help because SSA controls *field ownership*, not *value normalization* — the API server strips the field regardless of who owns it.

2. **cert-manager CRD size**: cert-manager CRDs are extremely large. Measured sizes against pinned chart v1.20.1:
   - `clusterissuers.cert-manager.io`: 310.8 KB
   - `issuers.cert-manager.io`: 310.7 KB
   - `challenges.acme.cert-manager.io`: 261.2 KB

   Without SSA, client-side apply writes a `last-applied-configuration` annotation that would exceed the 262 KB metadata limit, breaking sync entirely.

## Resolution

- Argo Rollouts: `ignoreDifferences` with `jqPathExpressions: [".spec.preserveUnknownFields"]` on CRDs
- cert-manager: `ServerSideApply=true` in syncOptions (annotation is not written with SSA)
- Kargo: Neither needed — Kargo CRDs do not include `preserveUnknownFields` and are under the size limit

## How to detect

For normalization drift: `argocd app diff` shows fields present in desired but absent in live. For size issues: sync fails with annotation size error in ArgoCD controller logs.
