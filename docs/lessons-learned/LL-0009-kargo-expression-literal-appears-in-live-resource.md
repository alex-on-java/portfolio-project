# LL-0009: Kargo sharedConfigMap Scope Limited to Promotion Steps

**Summary**: `sharedConfigMap()` is a Kargo runtime expression available only inside promotion step configurations. Warehouse specs are standard Kubernetes resources and cannot use Kargo expressions.

## What happened

When making the Warehouse git subscription branch dynamic (to support both ephemeral and main clusters), the initial approach was to use `sharedConfigMap('cluster-identity').branchPrefix` in the Warehouse `spec.subscriptions[].git.branch` field. This did not work — the literal string appeared in the resource instead of the resolved value.

## Root cause

Kargo expressions like `${{ sharedConfigMap(...) }}` and `${{ commitFrom(...) }}` are evaluated by the Kargo controller during promotion step execution. They are not available in Warehouse, Stage, or other CRD specs, which are standard Kubernetes resources processed by the API server without Kargo expression evaluation.

## Resolution

The Warehouse git subscription branch is patched externally via ArgoCD kustomize inline patches at the ApplicationSet level. The ephemeral `kargo-config-appset.yaml` uses:

```yaml
kustomize:
  patches:
    - target:
        group: kargo.akuity.io
        kind: Warehouse
      patch: |
        - op: replace
          path: /spec/subscriptions/1/git/branch
          value: "{{metadata.annotations.target-revision}}"
```

This uses ArgoCD templating (which evaluates at sync time) instead of Kargo expressions.

## How to detect

If a Kargo expression literal (e.g., `${{ sharedConfigMap(...) }}`) appears in a Warehouse or Stage resource's live state, the expression was not evaluated.
