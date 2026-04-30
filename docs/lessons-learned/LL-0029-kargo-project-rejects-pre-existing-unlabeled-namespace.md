# LL-0029: Kargo `Project` admission rejects pre-existing namespaces without the `kargo.akuity.io/project` label

## Summary

Kargo's admission webhook owns the lifecycle of the namespace named by a `Project` resource. If the namespace already exists when the `Project` is admitted, admission requires the namespace to carry the `kargo.akuity.io/project=<project-name>` label. Pre-creating the namespace through Kustomize (or any other path) without the label causes `Project` admission to fail with a namespace-conflict error — silent unless the operator inspects the AppSet's sync status. The clean shape is to separate the **management namespace** (where the `Project` lives) from the **deployment namespace** (where workloads run), allowing Kargo to create the management namespace itself.

## What happened

The platform's AppSet for Kargo observability resources declared both a `Namespace` (named `observability`) and a `Project` (also named `observability`) in the same Kustomize base. The AppSet failed to sync; ArgoCD reported a generic `admission webhook denied the request` from the Kargo webhook.

Inspection of the webhook's response revealed:
> "namespace observability already exists and is not labeled as a Kargo project"

Three resolution paths were considered:

1. Label the pre-created `Namespace` in `namespaces.yaml` with `kargo.akuity.io/project: observability` — couples the namespace's identity to Kargo, leaks Kargo concerns into a base manifest that owns multiple workloads' namespaces.
2. Remove the namespace from `namespaces.yaml` and let Kargo create it — diverges from the established `dev`/`stg`/`prd` pattern where namespaces are pre-created by the platform.
3. Move the `Project` into a different namespace from the deployment namespace — uses Kargo's natural shape: the `Project` resource is a control-plane object, not a deployment object.

## Root cause

Kargo's webhook treats the `Project` resource as a declaration of "this namespace belongs to Kargo." Admission is synchronous with namespace ownership — either Kargo creates the namespace itself (and labels it during creation), or the namespace already carries the label (signaling that a prior Kargo `Project` admission has happened). A pre-existing un-labeled namespace breaks this contract and is rejected.

The webhook's error message is informative once you read it; the silent failure mode is that the AppSet sync error surfaces only as `admission webhook denied the request`, which routes a debugging investigation through ArgoCD before reaching the webhook's actual reason.

## Resolution

Renamed the Kargo `Project` to `observability-project` (in a fresh namespace `observability-project`); workloads continue to deploy into `observability`. The two namespaces have distinct purposes:

- `observability-project` — the **management namespace**, owned by Kargo, contains `Project`, `ProjectConfig`, `Stage`, `Warehouse`. Created by Kargo on first admission.
- `observability` — the **deployment namespace**, owned by the platform, contains the workloads' Deployments, ConfigMaps, ServiceAccounts. Pre-created in `namespaces.yaml`.

This separation makes the control-plane/data-plane boundary visible in the namespace topology and avoids both the labeling-leak path and the divergence-from-pattern path.

## How to detect

Symptoms of this class of admission conflict:

- A Kargo `Project` resource fails admission with a namespace-related error.
- The named namespace exists in another manifest (a base `Namespace`, a Helm chart, a Terraform module).
- The namespace does not carry `kargo.akuity.io/project=<project-name>`.

When designing a new Kargo workload's manifest layout, default to the `<workload>` (deployment) + `<workload>-project` (Kargo control plane) namespace split. The split costs one extra namespace per workload but eliminates the entire class of admission conflicts and keeps Kargo concerns out of the deployment namespace's manifests.
