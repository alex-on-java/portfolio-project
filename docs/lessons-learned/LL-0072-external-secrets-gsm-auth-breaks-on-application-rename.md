# LL-0072: Renaming the External Secrets Application Silently Breaks Workload Identity Auth

## Summary

A Helm fullname helper in the chart produces the External Secrets Operator (ESO) controller ServiceAccount name, deriving it from the release name. The infra Workload Identity (WI) binding targets that ServiceAccount by exact name, `external-secrets/external-secrets`. That exact name rendered only because the ArgoCD Application/release name `external-secrets` collided with the chart name `external-secrets`, collapsing `external-secrets-external-secrets` to `external-secrets`. A routine rename of the Application or ApplicationSet would render the ServiceAccount as `<release>-external-secrets`. The WI binding would no longer match, GSM reads would fail, every ESO pod would stay Running, and no manifest error would appear. Setting `fullnameOverride: external-secrets` pins the ServiceAccount name independent of the release name.

## What Happened

WI auth here depended on an implicit coupling. The infra binding in `portfolio-project-infra/infra/iam/main.tf` hardcodes the member `serviceAccount:<project>.svc.id.goog[external-secrets/external-secrets]`. A GSA annotation `iam.gke.io/gcp-service-account` is set on the controller ServiceAccount in the operator values. Both target whatever name the chart renders for that ServiceAccount.

That name happened to be `external-secrets` only because the release name equalled the chart name. A reviewer noticed that a rename of the ApplicationSet/Application, an ordinary and low-risk-looking change, would change the rendered ServiceAccount to `<release>-external-secrets`. It would then sit outside the infra binding. The result would be a cross-repo break with no local signal: pods Running, manifests valid, GSM reads failing.

## Root Cause

The ESO Helm fullname helper renders `<release>-<chart>`, except when the release name already contains the chart name, in which case it returns just the release name. With release `external-secrets` and chart `external-secrets`, the helper returns `external-secrets`, and the controller ServiceAccount inherits that name.

Workload Identity auth requires two things to line up on the same ServiceAccount. One is the Kubernetes ServiceAccount name referenced by the infra WI binding (`external-secrets/external-secrets`). The other is the `iam.gke.io/gcp-service-account` annotation that maps it to the GSA. A rename satisfies neither against the binding anymore.

The failure is silent for three reasons. A failed Workload Identity token exchange is not a pod crash condition, so the controller stays Running and retries. Manifests render cleanly with no error. The only symptom is that Secret Manager reads return permission errors. This is the same false-green shape as LL-0001: all pods Running while the actual function is broken.

## Resolution

Pin the controller ServiceAccount name in the operator values (`gitops/apps/operators/external-secrets/values.yaml`) so it no longer depends on the release name:

```yaml
fullnameOverride: external-secrets
```

A short invariant comment at the call site records the cross-repo constraint. Verified by `helm template` at chart `2.5.0`:

- release `some-other-name`, no override → annotated ServiceAccount `some-other-name-external-secrets` (broken)
- release `some-other-name`, with override → annotated ServiceAccount `external-secrets` (fixed)
- release `external-secrets`, with override → annotated ServiceAccount `external-secrets` (no regression)

## How to Detect

- ESO pods are Running but `ExternalSecret`s are stuck not-Ready with a sync error; controller logs show permission-denied / 403 from Secret Manager.
- `helm template` the operator and read the controller ServiceAccount `metadata.name`; it must equal the Kubernetes ServiceAccount named in the infra WI binding. If it renders as `<release>-external-secrets`, the binding will not match.
- A rename of the Application/ApplicationSet with no other change correlates with the break.

## Adoption Rule

When a Workload Identity binding (or any out-of-band system) targets a chart-rendered ServiceAccount by exact name, pin that name with `fullnameOverride` rather than relying on a release-name/chart-name coincidence. Record the cross-repo invariant at the call site. Treat any rendered-name identifier that an external system references as a contract, not an incidental output that a rename may change freely.

## Related Records

ADR-033 records the ESO read identity and the Workload Identity binding this name pins. LL-0001 shows the same false-green shape: pods Running while a control-plane function is silently broken.
