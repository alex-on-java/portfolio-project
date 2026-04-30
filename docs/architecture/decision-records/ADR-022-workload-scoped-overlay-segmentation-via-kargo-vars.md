---
status: accepted
date: 2026-04-30
decision-makers: [alex-on-java]
---

# Workload-Scoped Overlay Segmentation via Kargo `vars.targetSegment` with PLACEHOLDER Sentinel

## Context and Problem Statement

The shared `promote-kustomize-app` `ClusterPromotionTask` builds each workload's overlay path by composing several path components: workload name, segment, and environment. Earlier promotion logic resolved the segment via a runtime expression — `${{ sharedConfigMap('cluster-identity').overlayTarget }}` — placing the segment value on the cluster, indexed by cluster identity, and consumed by every workload's promotion identically.

That shape worked when one workload existed. As the workload set grows toward asymmetric topologies (e.g., one workload with a different overlay subtree than the others), the cluster-scoped segment couples every workload's promotion to a single cluster-wide choice. Teaching the system about a per-workload overlay shape would require either splitting `cluster-identity` into per-workload sections or introducing a parallel ConfigMap — both choices push the workload-specific value into a place that doesn't naturally belong to the workload.

The architectural question this ADR settles is where the segment value lives and how it flows from the workload's identity to the promotion task.

## Decision Drivers

- **10× scaling:** asymmetric workloads must override the segment without touching shared bases used by other workloads.
- **Locality of identity:** a workload-specific value belongs in the workload's own configuration, not in cluster identity.
- **CQP-005 conformance:** external-resource identifiers — values that name something the system reads at runtime (here, the overlay subtree) — must not carry silent defaults; the source must be explicit and fail-loud when missing.
- **Migration safety:** the cutover from cluster-identity lookup to workload-scoped var must be safe at the git layer; cluster-side gating mechanisms cannot be relied on (see `LL-0035`).

## Considered Options

1. **Cluster-identity ConfigMap lookup (status quo)** — the segment value lives in `cluster-identity.overlayTarget`; every workload's promotion resolves the same expression at runtime.
2. **Stage-scoped literal in `promotionTemplate`** — the segment is hard-coded directly on each `Stage`'s `promotionTemplate.spec.vars`.
3. **Workload-scoped Kargo var** — `vars.targetSegment` declared on the shared CPT; each workload supplies its value through `app-vars.yaml`, substituted into shared `Stage` bases via a Kustomize replacement at build time.

## Decision Outcome

**Option 3 — workload-scoped Kargo var with PLACEHOLDER sentinel and Kustomize replacement**, implemented across four artifacts:

### 4.1 CPT declares the input, no default

`gitops/platform/kargo/project/cluster-promotion-task.yaml` declares `spec.vars[]` with `name: targetSegment` and **no `value:` field** — matching the existing convention for inputs without a sensible cluster-wide default (`appName`, `appCategory`, `imageRepo`, `warehouseImageURL`). Kargo's CRD admission does not enforce "required" on `vars[]`; the policy is enforced at consumption time by the filesystem-layer fail-loud (a missing or unsubstituted value produces a directory-not-found error against `overlays/<value>/<env>`). This is exactly CQP-005's intent: no silent fallback at the input layer; loud failure at the consumption layer.

### 4.2 Stage bases supply a literal `PLACEHOLDER`

Each shared `Stage` base (`stage-{dev,stg,prd}.yaml`) supplies `targetSegment: PLACEHOLDER` in its `promotionTemplate.spec.vars`. The literal sentinel is a deliberate choice (CQP-005's "Conventional sentinels" exception): if a workload's `app-vars.yaml` omits the key, the literal `PLACEHOLDER` propagates to the CPT's path expressions, and the downstream filesystem step fails loudly with `overlays/PLACEHOLDER/<env>` — a diagnostic symptom far easier to investigate than a literal `null` segment from an unset embedded reference.

### 4.3 Kustomize replacement substitutes the per-workload value

`gitops/platform/kargo/components/app-core/kustomization.yaml` declares a Kustomize replacement that substitutes `PLACEHOLDER` in every `Stage`'s `targetSegment` var with the value from the workload's `app-vars.yaml` at build time. The substitution is per-workload, deterministic, and visible in `kustomize build` output.

### 4.4 The current segment value is `any`

`gitops/platform/kargo/apps/workloads-web-app/app-vars.yaml` supplies `targetSegment: any`. The workload tree under `gitops/apps/workloads/web-app/overlays/any/{dev,stg,prd}` reflects the actual structure of today's choice space: there is exactly one segment value, and the name does not assert a dimension that does not vary. Future asymmetric workloads override `targetSegment` in their own `app-vars.yaml`, untouching shared bases.

### Consequences

- **Good**: workload autonomy — adding an asymmetric workload requires only a new `app-vars.yaml` and a matching `overlays/<segment>/{dev,stg,prd}` tree; shared `Stage` bases and the CPT are unchanged.
- **Good**: missing-value behavior is loud (`directory not found: overlays/PLACEHOLDER/dev`), not silent.
- **Good**: the indirection — declaration on CPT, sentinel on `Stage`, value in `app-vars.yaml`, substitution in `app-core` — is fully visible in the manifest tree; `kustomize build` shows the resolved state.
- **Bad**: four artifacts must stay in sync (CPT var entry, three Stage `vars`, the Kustomize replacement, each workload's `app-vars.yaml`). The `PLACEHOLDER` sentinel makes drift loud at the filesystem layer, but it does not prevent drift at the manifest layer.
- **Bad**: a reader scanning a single `Stage` manifest sees `targetSegment: PLACEHOLDER` and must trace through the Kustomize component to learn the actual value at build time. The cost of indirection is paid every time someone investigates the path resolution.

## Pros and Cons of the Options

### Cluster-identity lookup

- **Good**: zero per-workload indirection; one cluster-wide value drives every workload identically.
- **Bad**: couples every workload's overlay topology to a single cluster-scoped value. Asymmetric workloads cannot exist without splitting `cluster-identity` or adding a parallel ConfigMap.
- **Bad**: misplaces the value's identity — the segment is a workload property, not a cluster property.

### Stage-scoped literal

- **Good**: simplest path from a single-workload perspective — the value lives directly on the consuming `Stage`.
- **Bad**: shared `Stage` bases are consumed by every workload; placing the literal value there couples every workload's `Stage` to one workload's segment choice. The first asymmetric workload forces a Stage fork.

### Workload-scoped Kargo var with PLACEHOLDER sentinel

See **Decision Outcome** above.

## More Information

- `ADR-001` — the Kargo + Argo Rollouts pipeline that the CPT belongs to.
- `ADR-003` — deterministic commit-pinned promotions; `vars.targetSegment` is the same kind of explicit input as `imageRepo`.
- `LL-0035` — why the migration to this shape had to be staged at the git layer (cluster-side gating is reverted by ArgoCD selfHeal faster than Promotions land).
- `LL-0009` — the same operational nuance about literal `${{ vars.* }}` expressions appearing in live Kargo specs.
