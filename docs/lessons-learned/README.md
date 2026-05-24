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
- [ArgoCD `Application.status.conditions` is null in practice; Synced+Healthy is false-green on a stage branch with no resources](LL-0026-argocd-application-status-conditions-null-and-stage-branch-false-green.md)
- [Kargo `Stage.status.phase` does not exist on the live CRD — field mappings differ from documentation](LL-0027-kargo-stage-status-phase-does-not-exist.md)
- [Kargo Warehouse `includePaths` requires a `glob:` prefix for `**` patterns; bare `**` is parsed literally and produces NoCommitsDiscovered](LL-0028-kargo-warehouse-includepaths-requires-glob-prefix.md)
- [Kargo `Project` admission rejects pre-existing namespaces without the `kargo.akuity.io/project` label — separate management and deployment namespaces](LL-0029-kargo-project-rejects-pre-existing-unlabeled-namespace.md)
- [`uv sync` defaults to editable installs — multi-stage Docker images that copy only `.venv` break at runtime with ModuleNotFoundError](LL-0030-uv-editable-installs-break-multi-stage-docker-runtime.md)
- [Dynaconf with `environments=False` treats `[default]` as a literal nested table — the magic-section behavior is opt-in](LL-0031-dynaconf-default-section-literal-with-environments-false.md)
- [`ignoreDifferences[].managedFieldsManagers` alone suffices for selfHeal drift suppression — the SSA/ServerSideDiff/RespectIgnoreDifferences bundle is not required](LL-0032-managedfieldsmanagers-alone-suffices-no-ssa-bundle.md)
- [ArgoCD reports `Synced` briefly after a manifest mutation — single observations are unreliable, sustained-observation is required for merge gating](LL-0033-argocd-transient-synced-window-after-mutation.md)
- [kmock 0.7 platform quirks — adoption rules for in-process K8s API integration testing](LL-0034-kmock-platform-quirks-and-adoption-rules.md)
- [Kargo migrations must be made safe at the git layer — cluster-side gating (ProjectConfig pause, RBAC patches) is reverted by ArgoCD selfHeal faster than a Promotion can land](LL-0035-kargo-migrations-must-be-safe-at-the-git-layer.md)
- [On `pull_request` events, `github.sha` is the synthetic merge commit on `refs/pull/<n>/merge`, not the head SHA the developer pushed](LL-0036-pr-image-tag-absent-from-branch-history.md)
- [The legacy `/branches/{branch}/protection` endpoint only sees Classic branch protection rules and not rulesets](LL-0037-branch-protection-endpoint-returns-404-on-protected-branch.md)
- [Required status checks on GitHub treat `skipped` as `success`; a job cascade-skipped by a failed `needs:` silently passes the merge gate](LL-0038-required-check-green-despite-failed-upstream-job.md)
- [GitHub Actions reads `uses: ./<path>` against the working tree before `actions/checkout` runs; a composite cannot bootstrap itself](LL-0039-local-composite-action-yml-missing-before-checkout-runs.md)
- [`docker/setup-buildx-action` defaults to the `docker-container` driver, whose builds skip the local daemon unless invoked with `--load`](LL-0040-buildx-build-succeeds-but-image-missing-from-daemon.md)
- [A SHA pin on `jdx/mise-action` locks the wrapper, not the mise binary; a separate `version:` input sets the installed mise version](LL-0041-installed-tool-version-drifts-despite-sha-pinned-action.md)
- [`nx show projects` uses `--withTarget` (not `--target`) and silently accepts unknown flags; a misspelled filter emits the full list](LL-0042-nx-show-projects-target-filter-silently-dropped.md)
- [Nx hashes only files declared in a target's `inputs`; a lockfile-only pin bump replays the cache when `uv.lock` is missing from the set](LL-0043-nx-target-cache-survives-lockfile-pin-bump.md)
- [The hook fixes Conftest's `--parser` per invocation; widening `files:` across formats feeds the wrong bytes to that fixed parser](LL-0044-conftest-toml-parse-error-on-widened-files-regex.md)
- [`conftest verify` evaluates every `deny` rule against every fixture; an unguarded structural access crashes on a sibling parser's shape](LL-0045-conftest-verify-crashes-with-object-get-type-error.md)
- [GitHub Actions auto-prepends `success() &&` to a job-level `if:` lacking a status-check function, walking the transitive `needs:` graph](LL-0046-job-skipped-despite-explicit-needs-result-check.md)
- [GitHub Actions auto-prepends `success() &&` past the `allowed-skips` of a safe-merge-gate aggregator, silently skipping any downstream job](LL-0047-downstream-job-silently-skipped-after-green-aggregator.md)
- [GKE exposes two unrelated cluster IDs: `Cluster.id` is a 64-char UUID; CCM stamps an independent 16-char short ID into firewall metadata](LL-0048-gke-cluster-id-filter-never-matches-ccm-firewalls.md)
- [GKE CCM retains the cluster-scoped `k8s-<short>-node-http-hc` health-check firewall, which outlives the cluster and blocks VPC delete](LL-0049-vpc-delete-blocked-by-firewall-after-cluster-destroyed.md)
- [GKE cloud-controller-manager reconciles owned firewalls against live Services; a pre-cluster-destroy delete can reappear before VPC destroy](LL-0050-deleted-firewall-reappears-before-vpc-destroy.md)
- [`roles/compute.networkAdmin` grants read-only access on firewalls; `compute.firewalls.delete` lives only in `roles/compute.securityAdmin`](LL-0051-firewalls-delete-permission-denied-under-network-admin.md)
- [`kubectl --cascade=foreground` is Kubernetes ownerReference GC; ArgoCD workloads need the resources-finalizer on the Application to drain](LL-0052-kubectl-cascade-foreground-leaves-argocd-workloads-behind.md)
- [ArgoCD application controller re-creates a deleted Service within ~166 ms while selfHeal is on; kubectl delete cannot drain the LoadBalancer](LL-0053-deleted-loadbalancer-service-reappears-before-next-step.md)
- [GCP serves `firewalls.get` and the in-use check in `networks.delete` from independent indexes; firewall 404 lags VPC bookkeeping by ~30-60s](LL-0054-vpc-delete-reports-in-use-after-firewall-returns-404.md)
- [Tenacity `reraise=True` propagates a custom `TransientHTTPError(Exception)` past `except requests.HTTPError`; match is by class, not cause](LL-0055-custom-retry-exception-bypasses-existing-http-handlers.md)
- [`status_code >= 500` retry classifier routes 429 (Too Many Requests) to the terminal 4xx branch; GitHub rate limiting becomes fatal](LL-0056-429-rate-limit-routed-to-terminal-4xx-branch.md)
- [GKE honors single-zone `node_locations` exactly and surfaces `GCE_STOCKOUT` when the pinned zone runs tight, even with full quota headroom](LL-0057-gke-standard-cluster-creation-fails-gce-stockout.md)
- [Argocd-server maps `--propagation-policy` to a finalizer variant on the Application CR; the apiserver delete carries empty `DeleteOptions`](LL-0058-argocd-app-delete-propagation-policy-only-picks-finalizer-variant.md)
- [Deleting an App-of-Apps parent without a finalizer strands children; child finalizers stay inert and ownerReferences do not chain to parent](LL-0059-app-of-apps-children-orphaned-after-parent-delete.md)
- [Tenacity `stop_after_attempt(N)` bounds count not wall-clock; combine with `stop_after_delay(s)` to keep an outer poll deadline honest](LL-0062-inner-retries-consume-outer-poll-budget.md)
- [`pool-ctl release` collapses last-poll transient errors into `DESTROY_FAILED` without a final re-read; a real `success` can be discarded](LL-0063-successful-destroy-marked-failed-by-poll-timeout-race.md)
- [GCP audit logs default to writes; `firewalls.list` and `clusters.get` are `ADMIN_READ` Data Access events, silent until audit-config opt-in](LL-0064-audit-log-silent-on-list-and-describe-calls.md)
- [`argocd --core` resolves namespace via kube-context, not a fixed `argocd` default; lookup misses surface as `NotFound` without `-N argocd`](LL-0065-argocd-core-app-delete-not-found-in-default-namespace.md)
