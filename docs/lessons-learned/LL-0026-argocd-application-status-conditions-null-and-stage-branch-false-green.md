# LL-0026: ArgoCD `Application.status.conditions` is null in practice, and Synced+Healthy is false-green on a stage branch with no resources

## Summary

The ArgoCD `Application` reports `Synced+Healthy` even when the stage branch it tracks contains no resources yet — "Healthy" means "no resource is unhealthy," which is vacuously true on an empty source. Independently, `Application.status.conditions` is observed empty on every Application this project deploys, contradicting documentation that lists it as the canonical surface for sync/operation diagnostics. An evaluator that reads only `sync.status` and `health.status` reports false-green during the window between AppSet creation and the first successful Kargo promotion.

## What happened

The convergence-checker, in an early draft, classified Applications as healthy when `sync.status == Synced` and `health.status == Healthy`. The same evaluator was tested against a freshly created stage-branch Application (created by the AppSet, before any Promotion had populated the stage branch with manifests). The Application reported `Synced+Healthy` immediately, the evaluator declared the cluster converged, and the gate posted `success` — even though the actual workload was not deployed.

A parallel investigation tried to use `status.conditions[]` as the operational-state surface (per ArgoCD's documentation). Live inspection across every Application in the cluster showed `status.conditions` was always `null` — never populated by the controller in this version, despite docs.

## Root cause

ArgoCD's "Healthy" verdict is a logical AND over the resources tracked by the Application: if no resource is in `Degraded` or `Missing` state, the Application is `Healthy`. An Application whose source has no manifests has zero resources, and "no resource is unhealthy" is vacuously true. The same logic produces `Synced` because there is no drift between an empty source and an empty live state.

`status.conditions` is a documented field that the controller in this version does not populate for Applications created by ApplicationSets in this project's configuration. The field's absence is silent; the API returns the resource without the field, and naive evaluators read `null`.

## Resolution

The evaluator's per-Application verdict is `Healthy` purely on `health.status == "Healthy"` and `sync.status == "Synced"`; `status.conditions` is not consulted. Field mappings in `models.py` use `status.health.status`, `status.sync.status`, and `status.operationState.phase` (the last is consulted for explicit `Failed`/`Error` failure verdicts, not for resource-presence). The single-Application surface alone does not distinguish empty-source false-green from real success, by design — the protection lives one level up.

For the gate as a whole, two cross-cutting properties prevent the false-green from reaching a `success` commit status:

- **Cross-product with Kargo Stage evaluation.** A Stage that has not completed a Promotion does not reach `Healthy+Ready+Verified` (its `Ready`/`Verified` conditions stay `False`). The aggregate verdict is the AND of every Application AND every Stage — an empty stage-branch Application paired with a still-`Pending` Stage produces `pending`, not `healthy`.
- **Multi-cycle stability counter (`LL-0033`).** A single observation never flips the gate to `success`; the counter requires N consecutive cycles of all-healthy state. The transient-Synced window that would surface this false-green resolves before N cycles elapse.

The combination is load-bearing: removing either one would let the empty-source case slip through.

## How to detect

Symptoms of this class of false-green:

- A freshly promoted stage-branch Application reports `Synced+Healthy` immediately, before resources are populated.
- Mocked unit tests pass against synthetic Application objects that include `status.conditions[]`, but live cluster inspection (`kubectl -n argocd get application <name> -o yaml`) shows `status.conditions` is `null`.
- The evaluator's verdict matrix matches the docs but not the live API.

When auditing evaluator code that consumes ArgoCD CRDs, verify field mappings against a live cluster's `kubectl get` output, not against the CRD schema or the API reference. `status.conditions` is the most common documentation/reality gap; resource-presence checks are the most common false-green omission.
