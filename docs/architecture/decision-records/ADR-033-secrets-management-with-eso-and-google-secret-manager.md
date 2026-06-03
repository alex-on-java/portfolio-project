---
status: accepted
date: 2026-06-03
decision-makers: [alex-on-java]
---

# Secrets Management with ESO and Google Secret Manager

## Context and Problem

The repository had no in-repo secrets-management pattern. No workload consumed a real secret yet, so every future service would have had to invent its own approach. The first pattern that lands will be copied, so it must make the safe path the obvious path. It must not instead seed per-service Terraform sprawl, broad IAM, JSON-key authentication, plaintext secret values in Git or Terraform state, ambiguous environment mapping, or production credentials leaking into temporary environments.

This is the cheapest moment to establish the reference. There are no real secret consumers, so the architecture can be settled before a backend, database, vendor key, or production credential adds delivery pressure. The `web-app` serves as the living demonstration so a later, higher-stakes workload has something already working to copy.

The target architecture already fixed the identity mechanism: External Secrets Operator (ESO) reading Google Secret Manager (GSM) through GKE Workload Identity, with secrets mounted as files by default. This decision settles the open questions that remain: the store topology, the environment-mapping mechanism, how CRDs are managed, how the read identity is granted, how demo secret containers are provisioned, and which generated-credential primitive is demonstrated now.

## Decision Drivers

- Routine onboarding of a new service or Tier A secret must not require repeated infra-repo changes; coupling GitOps to infra makes GitOps inflexible.
- The reference will be replicated, so each choice is weighed against what happens when a future agent copies it many times over.
- Plaintext secret values must never enter Git or Terraform state.
- Environment-specific secret mapping must be explicit and reviewable in Git, without mentally replaying promotion-time mutations.
- A temporary production-like environment must never read real production fixed-secret material; this is a real threat for real secrets and the reference must show a proper solution.
- The reference must demonstrate two distinct secret lifecycles: externally sourced fixed secrets, and credentials generated in-cluster where no human chooses, types, commits, or stores the value.
- Boundaries around deferred hardening must stay honest; the first single-store reference must not be presented as the settled answer to every future isolation and provisioning question.

## Decision

Secrets follow a two-tier model. Tier A is externally sourced fixed material, born outside the system, held in GSM, and synced into a Kubernetes Secret by ESO. By contrast, Tier B is generated in-cluster by ESO, with no GSM round trip and no human ever selecting the value. The `web-app` demonstrates both: one Tier A Secret synced from GSM under the stable key `demo-gsm`, and one Tier B password generated in-cluster under the stable key `demo-generated`.

A single cluster-wide ESO controller identity and one `ClusterSecretStore` serve this scoped Tier A material. Because Tier B database credentials will be generated in-cluster rather than read from GSM, GSM holds only Tier A material. That removes the value a per-service store and GSA would otherwise add, an approach that would also have coupled service onboarding to infra changes. The store uses the `gcpsm` provider, project `cv-driven-dev-e-commerce`, and ambient Workload Identity credentials with no JSON key. This single-store topology is a scoped implementation choice for now, not the final isolation story.

The ESO read identity is granted once in the infra repo. That grant comprises an `external-secrets` GSA, a Workload Identity binding to the `external-secrets/external-secrets` Kubernetes ServiceAccount, and `roles/secretmanager.secretAccessor` conditioned to GSM secrets whose resource name starts with the `portfolio-project-` prefix. The grant deliberately omits `roles/secretmanager.viewer`, so the operator cannot enumerate secrets; each `ExternalSecret` names its `remoteRef` key explicitly. This is the operator's one-time identity, not per-secret provisioning, so a new service or Tier A secret reuses it without a further infra change. The ESO controller ServiceAccount carries the GSA email as an `iam.gke.io/gcp-service-account` annotation set directly in the operator values file, matching the cert-manager and external-dns precedent. The chart fullname is pinned to `external-secrets`, so the controller ServiceAccount remains `external-secrets/external-secrets` even if the Argo CD Application or Helm release name changes, preserving the Workload Identity binding.

Environment mapping lives in Kustomize overlays, where the GSM key each environment reads is visible in Git. The base `ExternalSecret` carries an invalid `REPLACE_IN_OVERLAY` sentinel rather than a real key. Every overlay must therefore set its key explicitly, and an unpatched or newly added overlay fails closed instead of silently reading the dev secret.

Render validation enforces this mapping in three ways. First, no rendered `ExternalSecret` may retain `REPLACE_IN_OVERLAY`. Second, every expected overlay must render the expected GSM key mapping: `any/dev -> dev`, `any/stg -> stg`, `ephemeral/prd -> stg`, and `main/prd -> prd`. Third, every ephemeral-reachable render, including `any/dev`, `any/stg`, and `ephemeral/prd`, must avoid production GSM keys and `dataFrom.find`. The validation covers both `spec.data[].remoteRef.key` and `spec.dataFrom[].extract.key`; `dataFrom.find` is rejected for ephemeral-reachable renders because its matched keys are resolved only at reconcile time and cannot be statically bounded.

The `prd` environment is lifecycle-sensitive: `overlays/ephemeral/prd` reads the staging GSM secret, and `overlays/main/prd` reads the production GSM secret. This overlay split is the central safety invariant. The staging reference is the current non-production substitute for ephemeral `prd`. It was chosen because it is much safer than reading the production secret in a temporary environment, not because it is the universal future answer. The lifecycle-specific `prd` overlays introduced under ADR-032 exist to ground exactly this difference between ephemeral and main `prd` secret material.

ESO CRDs are managed by the chart through `installCRDs: true`. These CRDs carry the `argocd.argoproj.io/sync-options: Prune=false` annotation so that removing the operator Application does not cascade-delete the CRDs and the custom resources they own. Conversion is disabled and `unsafeServeV1Beta1` is false, so the cluster serves only the `external-secrets.io/v1` API for `ClusterSecretStore` and `ExternalSecret`. The operator Application uses `ServerSideApply=true` because the rendered ESO CRDs exceed the client-side-apply annotation size limit. Under chart `2.5.0` the `Password` generator is `generators.external-secrets.io/v1alpha1`, while the core resources are `external-secrets.io/v1`.

The three demo GSM secret containers were created out of band with `gcloud`, each with one high-entropy dummy value. This keeps plaintext payloads out of Git and Terraform state. It is a current pragmatic provisioning choice, not a rule against managed containers; its auditability and traceability are weak and may be revised.

Workloads consume secrets as mounted files. The `web-app` keeps nginx as a static server and adds a busybox initContainer. That initContainer reads each mounted Secret file, writes its byte length and the hex encoding of its first five bytes into a shared `emptyDir`, and exits. Nginx then serves that generated evidence under `/secrets/`. Verification must exercise `/secrets/` rather than relying on the unchanged static `/` route. The first five bytes are read byte-bounded with `dd` and rendered as hex, so the preview is deterministic, bounded once per file regardless of newlines, and non-interpretable as HTML. The secret files are exposed through full Secret volume mounts without `subPath`. Showing a byte length and a five-byte hex prefix is a deliberate, entropy-aware observability affordance for high-entropy dummy values, not a default to copy onto real secrets.

## Options Considered

- One cluster-wide `ClusterSecretStore` and one prefix-conditioned read GSA, organized by secret rather than by service.
- A per-service `SecretStore` and GSA.
- Chart-managed ESO CRDs through `installCRDs`.
- Terraform-managed or Config Connector-managed GSM secret containers.
- Kargo promotion-time remapping of the ephemeral `prd` secret.
- Three distinct dummy values with no `prd` remap, versus lifecycle-specific `prd` overlays.
- Demonstrating the Tier B `Password` generator now, versus deferring all of Tier B.

## Option Analysis

The per-service `SecretStore`/GSA option was set aside for this reference. That option couples service onboarding to repeated infra-repo changes and fits shared and secret-less services poorly. It also leaves the ESO controller as a single shared trust point, so it does not buy the isolation its cost implies. With GSM holding only Tier A material, the single store carries the routine cases well. The narrower question of whether one store is right at ten times the scale is real and remains open. Today the leaning is a replicator-style mechanism that distributes secrets across environments, but the operator choice and scoping are unresolved, and building it now would be scope creep.

Terraform-managed or Config Connector-managed secret containers were not used for this implementation. Out-of-band container provisioning was the pragmatic way to create dummy values quickly, and the durable auditability model for containers is still open. The hard durable rule is narrow: plaintext secret values must not enter Git or Terraform state. That rule does not bar managed containers, because a container is metadata and can be managed without its payload ever entering state. These provisioning models are not rejected. They are the natural path toward the better container traceability the out-of-band approach lacks, and they remain revisitable.

Promotion-time remapping for the ephemeral `prd` secret was set aside because the `overlays/ephemeral/prd` and `overlays/main/prd` split is simpler and reviewable directly in Git. The split needs no replaying of Kargo promotion mutations to see which secret an environment reads.

The three-distinct-values option without a `prd` remap was the earlier demo plan, before ADR-032 made lifecycle-specific `prd` overlays buildable. That overlay split was then adopted because grounding the difference between ephemeral and main `prd` secret material was the driving reason the lifecycle segment was added to `web-app`.

Demonstrating the `Password` generator now exercises the in-cluster generation primitive as a copyable reference even though the database-credential pipeline is deferred. The future database-credential generation mechanism remains open, but generating and demonstrating a random internal secret is a firm requirement for this reference.

## Consequences

- Good: a new service or Tier A secret onboards by editing GitOps manifests, reusing the one read identity and prefix-scoped grant without touching the infra repo.
- Good: each environment's secret source is visible in Git, and the ephemeral `prd` overlay reading staging is reviewable as a static fact rather than a promotion-time behavior.
- Good: the read identity is least-privilege by resource-name condition and cannot enumerate secrets, because `secretmanager.viewer` is withheld and keys are named explicitly.
- Good: removing the ESO Application does not cascade-delete its CRDs or their custom resources, because the CRDs carry `Prune=false`.
- Neutral: the single `ClusterSecretStore` keeps the ESO controller as one shared trust point. RBAC and review constrain access, but stronger per-environment or per-namespace isolation is deferred, not solved here.
- Bad: out-of-band GSM container creation leaves weak traceability and auditability for which containers exist and why; this is accepted for now and flagged for revision.
- Bad: a mounted secret value does not hot-reload; a changed GSM value reaches a running pod only after the refresh interval and a pod restart.

## Postponed Effort

- Stronger per-environment or per-namespace isolation and distribution of secrets, possibly through a replicator-style mechanism. The operator choice, scoping, and exact mechanism are unresolved.
- A managed and auditable provisioning model for GSM secret containers, such as Terraform-managed containers or Config Connector, addressing the traceability weakness of out-of-band creation.
- The Tier B database-credential pipeline, including CNPG integration, rotation overlap, and `PushSecret` mirroring to GSM. Only the in-cluster generation primitive is demonstrated now.
- Live `main/prd` verification once a main-cluster deployment path exists. This decision proves `main/prd` only by code and rendered-manifest review.
- Hot reload of changed mounted secret values.

## More Information

Both the Tier A and Tier B keys are stable (`demo-gsm`, `demo-generated`), so the workload never needs to know GSM container names; it mounts Kubernetes Secrets. The Tier A `ExternalSecret` refreshes every `5m` rather than `1m`, chosen so a copied pattern does not multiply GSM access calls across many secrets. By contrast, the Tier B `ExternalSecret` does not refresh on a timer: it uses `refreshPolicy: CreatedOnce` (with `refreshInterval: 0s`) so the generated password is produced once and never regenerated. ESO generators are stateless and re-run on every refresh, so a periodic interval would silently regenerate the value every cycle. Because Tier B rotation is explicitly deferred above, the reference generates the value once rather than implying a rotation story it does not own.

Verification at implementation time was static and render-based for the cluster-independent facts:

- 23 ESO CRDs render with `Prune=false`.
- The `ClusterSecretStore` and `ExternalSecret` serve under `external-secrets.io/v1`, while `v1beta1` is not served.
- The `Password` generator is `generators.external-secrets.io/v1alpha1`.
- The controller ServiceAccount carries the GSA email annotation, and the chart fullname is pinned so the ServiceAccount name remains `external-secrets/external-secrets`.
- No rendered `ExternalSecret` retains the `REPLACE_IN_OVERLAY` sentinel.
- Every expected overlay renders the expected GSM key mapping: `any/dev -> dev`, `any/stg -> stg`, `ephemeral/prd -> stg`, and `main/prd -> prd`.
- Ephemeral-reachable renders contain no production GSM key and no `dataFrom.find`; key scanning covers `spec.data[].remoteRef.key` and `spec.dataFrom[].extract.key`.
- The web-app secret-evidence route is `/secrets/`, and rendered verification configuration points at that route rather than `/`.

The infra grant was applied and confirmed. Concretely, the `external-secrets` GSA exists, the Workload Identity binding to `external-secrets/external-secrets` exists, and the GSA holds `roles/secretmanager.secretAccessor` with the prefix condition and no `secretmanager.viewer`.

The deployable ephemeral path had not yet been live-verified in a PR cluster at the time of this record. This ADR therefore captures the accepted architecture, static/render evidence, and applied-IAM evidence, not final end-to-end implementation proof. A final verification report must record the live ESO-to-GSM-to-Kubernetes-Secret-to-mounted-file-to-served-evidence chain for ephemeral environments, including the live `ephemeral/prd -> stg` safety invariant, before the implementation is treated as fully proven.

This design depends on a GKE node-identity prerequisite that was already resolved before this work. The scoped `portfolio-project-gke-node` service account holds only `roles/container.defaultNodeServiceAccount`, and both cluster types use `GKE_METADATA`. No `roles/editor` binding exists for the custom node SA or the default Compute Engine SA. That prerequisite must still be rechecked on the fresh implementation PR cluster before final security sign-off.

The `main/prd` path is not claimed as live-verified. A main cluster deployment path does not exist yet, so its production secret mapping is proven by manifest and render review only.

## Related Records

- ADR-032: the lifecycle-specific `prd` overlays this decision uses to ground the difference between ephemeral and main `prd` secret material.
- ADR-004: Helm for external charts and Kustomize for first-party manifests, the convention the ESO Application and the `web-app` overlays follow.
- ADR-002: the ephemeral and main cluster separation the lifecycle-sensitive `prd` mapping protects.
- ADR-014: chart-managed CRD handling, which the `installCRDs` and `Prune=false` choice follows.
- LL-0071: ESO generator-backed `ExternalSecret` refresh behavior, which explains why the generated demo secret uses `refreshPolicy: CreatedOnce`.
- LL-0072: ESO ServiceAccount naming and Workload Identity, which explains why the chart fullname is pinned.
- LL-0073: Secret Manager IAM `startsWith` conditions, which explains why an empty prefix must never reach the applied grant.
