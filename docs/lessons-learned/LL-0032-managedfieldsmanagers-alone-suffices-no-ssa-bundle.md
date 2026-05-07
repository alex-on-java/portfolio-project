# LL-0032: `ignoreDifferences[].managedFieldsManagers` alone suffices for selfHeal drift suppression — the SSA/ServerSideDiff/RespectIgnoreDifferences bundle is not required

## Summary

Common advice for cooperative-write resources (where a controller writes one part of a resource and ArgoCD reconciles the rest) is to enable a stack of switches: the controller writes via Server-Side Apply, the AppSet sets `RespectIgnoreDifferences=true`, and `ServerSideDiff` is enabled in compare-options. A live PoC against the ephemeral cluster's actual ArgoCD version showed none of these are required: a single `ignoreDifferences[].managedFieldsManagers: [<controller-name>]` rule on the AppSet, paired with a client-side `PATCH` carrying the matching `field_manager` parameter, is sufficient to stop selfHeal from reverting the controller's writes.

## What happened

When configuring the convergence-checker's heartbeat write to coexist with ArgoCD's reconciliation of the same `ConfigMap`, the first attempt used path-based ignoreDifferences (`jsonPointers: [/data]`). Aside from being a blanket suppression that contradicts `ADR-009`, this surfaced a second question: should the migration to the field-manager-scoped rule also enable the SSA stack that public examples and ArgoCD docs commonly bundle with cooperative-write configurations?

A throwaway PoC was set up against the ephemeral PR-16 cluster:

- Branch A: AppSet with `managedFieldsManagers: [convergence-checker]` only; checker writes via the kubernetes Python SDK's `patch_namespaced_config_map` with `field_manager="convergence-checker"`. No other switches.
- Branch B: same as A, plus `RespectIgnoreDifferences: true` in `syncOptions`.
- Branch C: same as A, plus ArgoCD `compare-options: ServerSideDiff=true`.
- Branch D: same as A, but checker writes via SSA (`server-side-apply` patch type).

Across all four branches, selfHeal stopped reverting the heartbeat writes immediately after the AppSet rule was applied. Branch A — the minimum config — produced the same observable behavior as branches B/C/D. None of the additional switches changed the outcome.

## Root cause

ArgoCD's `ignoreDifferences[].managedFieldsManagers` reads the resource's `metadata.managedFields[]` array (which Kubernetes populates automatically on every write, regardless of whether the write was SSA or a client-side PATCH) and excludes from the diff any field whose owning manager matches the configured list. The mechanism does not depend on:

- **`RespectIgnoreDifferences` in `syncOptions`** — that flag controls whether the *sync* operation honors `ignoreDifferences` (relevant for explicit `kubectl sync`); selfHeal already honors `ignoreDifferences` via the diff calculation.
- **`ServerSideDiff` in compare-options** — that switch controls how ArgoCD computes diffs (server-side vs client-side); for `managedFieldsManagers` rules the server-side path is not required because Kubernetes populates `managedFields` on any write.
- **SSA writes from the controller** — the controller's PATCH method (`application/strategic-merge-patch+json`, `application/merge-patch+json`, or SSA's `application/apply-patch+yaml`) does not change which manager owns the field; the `field_manager` parameter is honored across all PATCH types.

The bundle is sometimes necessary for *other* drift problems (e.g., field-defaulting drift where the API server populates fields the controller didn't write — `ServerSideDiff` matters there), but it is not necessary for the selfHeal-vs-cooperative-write problem when ownership is declared by manager name.

## Resolution

Configure only the `managedFieldsManagers` rule. The AppSet:

```yaml
ignoreDifferences:
  - group: ""
    kind: ConfigMap
    name: gitops-convergence-heartbeat
    managedFieldsManagers: [convergence-checker]
```

The controller's write:

```python
api.patch_namespaced_config_map(
    name="gitops-convergence-heartbeat",
    namespace="observability",
    body={"data": {"lastHeartbeatAt": now}},
    field_manager="convergence-checker",
)
```

No `RespectIgnoreDifferences`, no `ServerSideDiff`, no SSA from the controller. The decision is recorded in `ADR-023`; this LL captures the empirical finding that informed it.

## How to detect

When a cooperative-write configuration is being designed:

- The reflexive answer "we need SSA + ServerSideDiff + RespectIgnoreDifferences" is a tripwire — it means the configuration was inherited from advice rather than verified against the actual target.
- Live-test on a non-prod cluster with each switch added and removed independently. If the field-manager rule alone stops selfHeal from reverting writes, none of the other switches are doing useful work.
- For a different drift problem (default-field drift, normalization drift), `ServerSideDiff` may genuinely be required (`LL-0006`, `LL-0016`); diagnose the specific drift first before reaching for the bundle.

The principle generalizes: configuration whose components are all "needed for safety" is brittle precisely because no single component's contribution is established. Test components individually until each one's role is verified.
