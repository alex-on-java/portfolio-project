# Lessons Learned

Platform behaviors, silent failure modes, and non-obvious gotchas discovered during implementation. Each entry documents a problem that was harder to diagnose than to fix — the kind of thing that costs hours to rediscover independently.

## What belongs here

Surprising platform behaviors, invisible failure modes, misleading defaults, and tool quirks. The common thread: knowing this in advance saves significant debugging time.

## What does not belong here

- Architectural decisions — see [Decision Records](../architecture/decision-records/README.md)
- Standard configuration documented in official docs
- Transient issues tied to specific versions that have since been fixed

## Entries

- [GKE Warden silently blocks cainjector leader election in kube-system, leaving the webhook non-functional](LL-0001-cert-manager-empty-cabundle-x509-validation-errors.md)
- [GKE NAP applies invisible 500m/2Gi resource defaults and Warden enforces a 50m/52Mi floor even on Standard clusters](LL-0002-pods-consume-far-more-resources-than-declared.md)
- [Kargo's mutating webhook injects default values not present in Git, creating permanent ArgoCD drift](LL-0003-warehouse-stage-perpetual-outsync-undeclared-fields.md)
- [Kustomize set-image matches container image refs in manifests, not images[].name in kustomization.yaml](LL-0004-phantom-image-entry-after-promotion-no-error.md)
- [ArgoCD Application finalizer is added by two independent controllers — blocking one is not enough](LL-0005-application-deletion-hangs-despite-preserve-resources.md)
- [ServerSideApply controls field ownership, not API-server normalization — cert-manager CRDs need it for a different reason](LL-0006-crd-sync-drift-ssa-ownership-vs-normalization.md)
- [Kustomize blocks file references outside the root directory, but directory references with their own kustomization.yaml are exempt](LL-0007-kustomize-security-error-referencing-files-above-root.md)
- [cert-manager Helm chart defaults crds.keep to false — an uninstall cascade-deletes every Certificate in the cluster](LL-0008-helm-uninstall-cascade-deletes-all-crds-and-resources.md)
- [Kargo expressions like sharedConfigMap() only resolve inside promotion steps — Warehouse specs are plain Kubernetes resources](LL-0009-kargo-expression-literal-appears-in-live-resource.md)
