# Track B Implementation Report

## Scope

Track B replaced the committed Python/Jinja2 generator with a Kustomize-native service database pattern. The deployed source is now the reviewable source: shared Kustomize structure lives once, and each service database supplies explicit local-config values in one service-owned file.

Starting commit: `2d7d8f8faf5952ba78d388d7a7d7d7076955139a`.

Implementation commits:

- `39437e6a41a226897fc30eebef0607a8c13b2ab2`: replaced the generator-backed `lorem` and `ipsum` manifests with shared Kustomize structure plus service values.
- `5041c7c401333d1d3ec62cc8dd810f5a18d75d25`: replayed `dolor` as service N+1 through the new values mechanism.

This report was added after the live `dolor` proof. It records the evidence for the implementation commits above.

## Why the generator was replaced

The generator reduced typing but split the source of truth across `generate.py`, `services.yaml`, templates, and committed output. Template changes only affected deployment after a human or hook reran the generator and committed the result. That was the wrong maintenance model for this GitOps slice: ArgoCD should consume the same declarative files that reviewers inspect.

The replacement keeps the single-source onboarding intent without introducing Helm, Jsonnet, repo-server plugins, or KRM exec plugins. Kustomize replacements copy explicit values into shared structure, and policies catch the drift modes that Kustomize would otherwise build without complaint.

## Final layout

Shared structure lives in `components/service-database/_shared/`:

- `external-secrets.yaml`
- `database.yaml`
- `provisioning-job.yaml`
- `managed-roles-patch.yaml`
- `kustomization.yaml`

Service values live one directory per service:

- `components/service-database/lorem/values.yaml`
- `components/service-database/ipsum/values.yaml`
- `components/service-database/dolor/values.yaml`

Each service component has a matching `kustomization.yaml` that consumes `_shared` and copies values into exact field paths. The base wires the service list once through Kustomize components:

- `../components/service-database/lorem`
- `../components/service-database/ipsum`
- `../components/service-database/dolor`

The shared provisioning SQL ConfigMap is declared in `base/provisioning-sql.yaml`. Each service component creates its own literal SQL key, for example `data.[provision-dolor.sql]`. That literal field path is the only Kustomize residue in the design, and the conftest policy checks it.

## Render parity

Evidence directory: `/tmp/cnpg-track-b-rewrite.icbWbW`.

The pre-rewrite three-service base and ephemeral renders were saved before any source edits. A temporary copy of the old generator was then rendered with `dolor` removed to create the two-service `lorem`/`ipsum` oracle.

Normalization used:

```sh
yq eval-all '[.] | sort_by(.apiVersion + "/" + .kind + "/" + .metadata.name) | .[] | (... comments="") | (.. style="") | sort_keys(..) | split_doc'
```

Parity checks used `cmp -s`:

- `post-delete-base.normalized.yaml` matched `oracle-two-service-base.normalized.yaml`.
- `post-delete-ephemeral.normalized.yaml` matched `oracle-two-service-ephemeral.normalized.yaml`.
- `post-dolor-base.normalized.yaml` matched `before-base.normalized.yaml`.
- `post-dolor-ephemeral.normalized.yaml` matched `before-ephemeral.normalized.yaml`.

The negative control also held: normalized base and ephemeral renders differed before and after the rewrite.

## Policy coverage

The validation described in this section was the Track B guardrail at the time
of the generator replacement. It has since been superseded by the rendered
Conftest migration: `policies/conftest/cnpg_service_database.rego` now runs in
`package rendered` and validates the rendered CNPG service-database contract
through the generic `tools/k8s-validation/validators/rendered_conftest_validator.py`
bridge. The old dedicated `cnpg-service-database-inventory` hook and bespoke
Python service-database validator have been removed.

The original source-inventory policy checked service values, service component
shape, shared component shape, and combine-mode inventory. Its tests covered
these induced failures:

- missing required value;
- wrong service prefix in a role;
- wrong service prefix in a Secret;
- duplicate role value;
- duplicate Secret value;
- wrong SQL key;
- wrong SQL body;
- service values file not wired into base;
- base references a service with no values file;
- duplicate service wiring;
- values file in the wrong service directory;
- component file in the wrong service directory;
- wildcard replacement field path.

The current rendered policy derives service expectations from rendered
`Database` resources, then checks matching `ExternalSecret`, provisioning `Job`,
SQL `ConfigMap`, CNPG managed-role, placeholder, and rendered DB alias service
contracts inside each rendered manifest file independently.

Residual silent modes:

- Kustomize still cannot derive the provisioning SQL map key from a value, so each service component must name its SQL key field path literally. The current rendered policy checks the resulting SQL key and body.
- The committed acceptance Job intentionally verifies only `lorem` and `ipsum`. N+1 runtime behavior for `dolor` was proved manually in this round, not by an inventory-driven committed acceptance contract. A future guardrail could make the acceptance Job consume the same service inventory, but that was outside this slice.

## Static verification

Static checks passed after both implementation phases:

- `conftest verify --policy policies/conftest`: 101 tests passed.
- dedicated inventory hook: 39 tests passed.
- `pnpm exec nx run gitops:lint`: 7 tests passed after the rendered-contract validator was added.
- `prek run --all-files`: all hooks passed.

Those static checks belong to the original Track B evidence above. Current
static verification for the rendered migration is owned by `conftest verify`,
`uv run --frozen pytest validators/`, `pnpm exec nx run gitops:lint`, and
`prek run --all-files`.

## Live convergence

PR: `#38`.

Cluster-pool workflow reused cluster `portfolio-pool-ew1-10-28-238b7356` in `europe-west1`.

Kubernetes context used for manual proof:

```text
gke_cv-driven-dev-e-commerce_europe-west1_portfolio-pool-ew1-10-28-238b7356
```

Namespace: `datastores`.

Baseline commit `39437e6a41a226897fc30eebef0607a8c13b2ab2` reached `GitOps Convergence Gate` success with `All 23 resources healthy for 10 consecutive checks` at `2026-06-12T11:14:11Z`.

`dolor` commit `5041c7c401333d1d3ec62cc8dd810f5a18d75d25` reached `GitOps Convergence Gate` success with `All 23 resources healthy for 7 consecutive checks` at `2026-06-12T11:20:23Z`.

ArgoCD reported all Applications `Synced` and `Healthy`, including `datastores-cnpg-eso-verification`.

The CNPG cluster was healthy:

- `cnpg-eso-multidb-verification`: `READY=1`, `STATUS=Cluster in healthy state`.
- `cnpg-eso-dolor`: `APPLIED=true`.
- all five `dolor` ExternalSecrets: `SecretSynced`, `READY=True`.
- `cnpg-verification-provision-dolor`: `Complete`.
- `cnpg-verification-acceptance`: `Complete` for its planned `lorem` and `ipsum` scope.

## Manual dolor proof

Manual SQL proof used pod `cnpg-eso-multidb-verification-1`.

Structural checks:

- database `dolor` exists;
- schema `dolor` exists and is owned by `dolor_app`;
- schema `public` is absent;
- `PUBLIC` has no `CONNECT` or `TEMPORARY` on database `dolor`;
- direct `CONNECT` grants are on `dolor_app`, `dolor_app_ro`, `dolor_app_rw`, and `dolor_app_mig`;
- `TEMPORARY` is present only on the owner role `dolor_app`.

Role behavior checks:

- `dolor_app_mig_a` cannot create DDL without `PGOPTIONS='-c role=dolor_app'`.
- `dolor_app_mig_a` can create and drop the probe table with `PGOPTIONS='-c role=dolor_app'`; the session reports `current_user=dolor_app` and `current_role=dolor_app`.
- `dolor_app_ro_a` can read the probe table.
- `dolor_app_ro_a` cannot write to the probe table.
- `dolor_app_rw_a` can write to the probe table.
- `dolor_app_rw_a` cannot perform owner-level DDL.
- `lorem_app_ro_a` cannot connect to database `dolor`.
- `dolor_app_ro_a` cannot connect to database `lorem`.

The probe table was dropped at the end of the proof.

The committed acceptance Job remains scoped to `lorem` and `ipsum`, as planned. Its log confirmed the existing isolation contract for both services after the `dolor` replay.

## Caveats

No cluster stockout or workflow retry was needed during this implementation. The reused cluster was already available, and both pushed implementation commits reached the convergence gate.

No failed `dolor` replay occurred. The `dolor` commit added only the service values, service kustomization, and base wiring entry; shared structure did not change after the baseline commit.
