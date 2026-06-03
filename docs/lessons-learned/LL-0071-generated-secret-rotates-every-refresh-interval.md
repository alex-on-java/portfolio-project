# LL-0071: ESO Generator-Backed `ExternalSecret` Rotates the Value on Every `refreshInterval`

## Summary

An External Secrets Operator (ESO) `ExternalSecret` that sources an in-cluster generator (for example the `Password` generator) produces a **new** value on every refresh. ESO generators are stateless: each invocation generates a fresh set of values and the operator does not remember the previous one. On a generator-backed `ExternalSecret`, a timer such as `refreshInterval: 5m` silently rotates the target Kubernetes Secret every five minutes. The consuming pod sees the value change with no triggering change in Git or in any upstream store. Setting `refreshInterval: 0s` alone does not stop this; the explicit lever is `refreshPolicy: CreatedOnce`.

## What Happened

The `web-app` reference demonstrates two secret lifecycles (ADR-033): a GSM-backed Tier A secret and an in-cluster generated Tier B credential. Its Tier B `ExternalSecret` (`gitops/apps/workloads/web-app/base/external-secret-generated.yaml`) initially copied the Tier A `refreshInterval: 5m`. That interval is correct for Tier A, where each refresh re-reads the same fixed value from GSM and the interval only trades staleness against GSM access-call volume.

For the generator-backed Tier B secret the same field means something entirely different. The `Password` generator is stateless, so every 5-minute refresh would re-invoke it and emit a brand-new 32-character password. Target Secret `web-app-demo-generated` would then churn on a 5-minute cadence, and the served evidence page would change every cycle with nothing upstream changing. Because the reference presents `demo-generated` as a stable in-cluster credential under a stable key, a copied pattern would inherit surprise rotation. This was caught while reviewing the copyable reference, before it shipped.

## Root Cause

ESO generators are stateless. The ESO documentation states the generator "does not keep track of the produced values; every invocation produces a new set of values." A generator-backed `ExternalSecret` therefore treats each refresh as *produce again*, not *re-read the same value*. `refreshInterval` drives the refresh cadence, so any non-zero interval regenerates on a timer.

`refreshInterval: 0s` disables the timer but is insufficient on its own: a spec or metadata reconcile can still trigger regeneration. `refreshPolicy: CreatedOnce` is the explicit lever. It produces the value once and never regenerates it regardless of later reconciles.

The trap is that one field, `refreshInterval`, carries two meanings depending on the source. For a store-backed (Tier A) `ExternalSecret` it is a re-read cadence; for a generator-backed (Tier B) one it is a regeneration cadence.

## Resolution

Set `refreshPolicy: CreatedOnce` (with `refreshInterval: 0s`) on generator-backed `ExternalSecret`s that should hold a stable value:

```yaml
spec:
  refreshInterval: 0s
  refreshPolicy: CreatedOnce
  dataFrom:
    - sourceRef:
        generatorRef:
          kind: Password
          name: web-app-demo-generated
```

Keep a timer `refreshInterval` only on store-backed `ExternalSecret`s, where refresh re-reads an external value rather than producing a new one.

## How to Detect

- The value or `resourceVersion` of the target Kubernetes Secret changes on the refresh cadence with no change in Git or the upstream store.
- A consumer that mounts the Secret observes the value change after each interval (served evidence, file checksums, application restarts on remount).
- The `ExternalSecret` sources a `generatorRef` and carries a non-zero `refreshInterval` without `refreshPolicy: CreatedOnce`.

## Adoption Rule

For generator-backed `ExternalSecret`s that should hold a stable value, set `refreshPolicy: CreatedOnce`. Reserve a timer `refreshInterval` for store-backed `ExternalSecret`s, where refresh re-reads an external value rather than producing a new one. If periodic regeneration is genuinely intended, state that intent explicitly on the manifest and in the owning ADR. A copied interval should not imply a rotation story the reference does not own.

## Related Records

ADR-033 records the two-tier secrets model and the per-tier refresh split this lesson grounds.
