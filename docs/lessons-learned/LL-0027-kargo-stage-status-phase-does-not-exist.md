# LL-0027: Kargo `Stage.status.phase` does not exist on the live CRD; field mappings differ from documentation

## Summary

Kargo documentation references `Stage.status.phase` as the operational state surface (`Steady`, `Promoting`, `NotApplicable`, etc.). On the live CRD installed by Kargo 1.9.x, this field is not present. Code that reads `status.phase` always gets `None`; mocked tests that match the docs pass while production reads silently fail. The actually-populated surfaces are `status.health.status` and `status.conditions[]`.

## What happened

The convergence-checker's first evaluator referenced `Stage.status.phase` to classify Kargo Stages as `Steady` (converged), `Promoting` (in progress), or `Errored`. Unit tests built fixtures matching the documented schema and passed. Live testing against an ephemeral cluster reported every Stage as having `None` for `phase`; the evaluator could not classify any Stage.

Inspection via `kubectl -n <stage-ns> get stage <name> -o yaml` showed:
- `status.phase` — absent from the resource.
- `status.health.status` — populated with `Healthy` / `Unhealthy` / `Progressing`.
- `status.conditions[]` — populated as a list of `{type, status, ...}` entries for `Ready`, `Healthy`, `Verified`, etc.

The CRD's OpenAPI schema (via `kubectl get crd stages.kargo.akuity.io -o yaml`) confirmed `phase` is not in the schema for this Kargo version.

## Root cause

Documentation lag, version skew, or a deliberate field rename between the docs the evaluator was built against and Kargo 1.9.x. The field's absence is silent — the live API returns the resource without the field, and naive readers get `None` rather than an error.

## Resolution

Evaluator field mappings consume the actually-populated surfaces:

- **Health verdict** — `status.health.status`. `Healthy` is the converged signal; `Unhealthy` is the explicit-failure signal; any other value is treated as in-flight.
- **Conditions** — `status.conditions[]`, unmarshalled into a `{type → bool}` dict where each entry's `status` is `"True"` or `"False"`. The evaluator requires `Ready=True`, `Healthy=True`, and `Verified=True` together for a Stage to be classified `Healthy`. A `Healthy=False` condition is the explicit-failure signal even when `health.status` is not `Unhealthy`.

`status.phase`, `status.lastPromotion`, and `status.freightHistory` are not consulted by the evaluator. Tests use fixtures that match the live shape, not the documented one, and the `kmock` integration test (see `ADR-020`) seeds Stage resources without a `phase` field.

## How to detect

Symptoms that documentation and reality have diverged on Kargo CRDs:

- Code references `Stage.status.phase` (or any other field cited in docs) and receives `None` on live clusters.
- Unit tests pass with fixtures derived from the schema reference; integration tests against a real cluster fail or return `Unknown` verdicts.
- `kubectl get stage <name> -o yaml` shows a different `status` shape than the docs describe.

Before encoding any Kargo `Stage` field mapping, run `kubectl get crd stages.kargo.akuity.io -o yaml | yq '.spec.versions[].schema.openAPIV3Schema.properties.status'` against the actual cluster the evaluator will run against. The CRD is the truth; the docs may be aspirational or out of date.
