# LL-0008: cert-manager Helm Defaults Cascade-Delete CRDs

**Summary**: The cert-manager Helm chart defaults `crds.keep` to `false`. On `helm uninstall`, this cascade-deletes all CRDs, which in turn deletes every Certificate, Issuer, and ClusterIssuer in the cluster.

## What happened

This was caught during initial configuration review, not in a live incident. The default `crds.keep: false` was identified as a high-risk default for any cluster running cert-manager in production.

## Root cause

Helm's CRD lifecycle: when a chart installs CRDs and is later uninstalled, CRD deletion triggers Kubernetes garbage collection of all custom resources of those types. cert-manager chart defaults to `crds.keep: false`, meaning an uninstall (including an accidental one, or ArgoCD pruning) would wipe all TLS infrastructure.

Additionally, `crds.enabled` is the correct key since cert-manager v1.15+. The older `installCRDs` key is deprecated but still accepted, which can cause confusion.

## Resolution

Set `crds.keep: true` and `crds.enabled: true` explicitly in Helm values.

## How to detect

Review `values.yaml` for `crds.keep`. If absent or `false`, CRDs are at risk on uninstall.
