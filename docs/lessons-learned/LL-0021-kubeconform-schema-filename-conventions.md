# LL-0021: kubeconform schema filenames require lowercase kind and first-label API group (KindSuffix)

## Summary

kubeconform resolves schema files using two conventions that differ from intuitive expectations: (1) the `{{.ResourceKind}}` template variable is always lowercase, and (2) K8s builtin schemas use only the first DNS label of the API group (KindSuffix convention), not the full group string. Getting either convention wrong produces schema-not-found errors that are invisible on macOS but break on Linux.

## What happened

The CRD schema pipeline generated filenames using PascalCase kind names from CRD specs (e.g., `Rollout-argoproj.io-v1alpha1.json`). Local validation on macOS passed because APFS is case-insensitive — `rollout-argoproj.io-v1alpha1.json` and `Rollout-argoproj.io-v1alpha1.json` resolve to the same file. On Linux (ext4, case-sensitive), kubeconform could not find the schemas.

Separately, K8s builtin schema filenames were generated using the full API group string (e.g., `ingress-networking.k8s.io-v1.json`). The upstream schema repository (`yannh/kubernetes-json-schema`) uses the KindSuffix convention: only the first DNS label of the group. The correct filename is `ingress-networking-v1.json`. Requests for the full-group filename return 404.

## Root cause

kubeconform's `{{.ResourceKind}}` template variable applies `strings.ToLower()` unconditionally. This is not documented prominently — the template reference shows `{{.ResourceKind}}` without noting the lowercase transformation. The KindSuffix convention (`group.split('.')[0]`) is an implementation detail of the `yannh/kubernetes-json-schema` repository's file naming, not a kubeconform feature per se, but kubeconform's default schema location depends on it.

## Resolution

Centralized all schema filename generation into two functions:
- `crd_schema_filename()`: applies `kind.lower()` for CRD-generated schemas
- `k8s_schema_filename()`: applies `group.split('.')[0]` for K8s builtin schemas

Both functions are the single source of truth for filename conventions, ensuring consistency across the pipeline.

## How to detect

If kubeconform reports "no schema found" for a resource that has a schema file on disk, check: (1) whether the filename uses lowercase kind (not PascalCase), and (2) whether builtin K8s schemas use only the first DNS label of the API group. Test on a case-sensitive filesystem (Linux or `diskutil` with case-sensitive APFS on macOS) — macOS default APFS masks case mismatches.
