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
- [GitHub App installation tokens scope to the current repository by default, even when the App is installed on multiple repos](LL-0010-cross-repo-dispatch-404-despite-correct-app-permissions.md)
- [zizmor's per-rule allowlist config key exists in source but not in the released binary — parsed and silently ignored](LL-0011-zizmor-allowlist-config-parsed-but-has-no-effect.md)
- [Helm hook Jobs can stall ArgoCD reconciliation unless hook delete policy is explicit](LL-0012-helm-hook-jobs-can-stall-argocd-without-delete-policy.md)
- [Helm `skipCrds` is all-or-nothing and can conflict with CRD channel enforcement policy](LL-0013-helm-skipcrds-is-all-or-nothing-under-crd-policy.md)
- [Contour startup can fail progressively on missing Gateway API kinds, requiring full feature-set disablement](LL-0014-contour-startup-fails-progressively-on-missing-gateway-kinds.md)
- [GKE Autopilot enforces `ephemeral-storage` request/limit equality, causing drift when chart presets mismatch](LL-0015-autopilot-enforces-ephemeral-storage-request-limit-equality.md)
- [ArgoCD ServerSideDiff must be enabled via compare-options; placing it in syncOptions is silently ineffective](LL-0016-argocd-serversidediff-must-be-enabled-via-compare-options.md)
- [DNS symptoms can mask promotion blockage and Gateway/dataplane readiness failures](LL-0017-dns-symptoms-can-mask-promotion-and-gateway-readiness-failures.md)
- [HTTP-to-HTTPS redirect can be shadowed unless workload routes are pinned to the HTTPS listener](LL-0018-http-to-https-redirect-can-be-shadowed-without-listener-section-pinning.md)
- [ArgoCD fasttemplate preserves missing keys as literal text — accidental safety from an unmaintained library](LL-0019-fasttemplate-preserves-missing-keys-as-literal-text.md)
- [Kyverno CRD enforces maxLength: 63 on rule names — exceeding it silently loads zero rules](LL-0020-kyverno-rule-name-maxlength-silent-failure.md)
- [kubeconform schema filenames require lowercase kind and first-label API group (KindSuffix convention)](LL-0021-kubeconform-schema-filename-conventions.md)
- [kubeconform default schema location downloads ~243 schemas from GitHub on every run](LL-0022-kubeconform-default-schema-location-fetches-from-github.md)
- [yannh/kubernetes-json-schema has no release tags — SHA pin is the only stable reference](LL-0023-yannh-schema-repo-has-no-release-tags.md)
- [Atomic downloads prevent half-written schema caches on interrupt](LL-0024-atomic-downloads-prevent-half-written-caches.md)
- [Silent `continue` in config extraction masks the root cause of misconfigurations](LL-0025-silent-continue-in-config-extraction-masks-root-cause.md)
