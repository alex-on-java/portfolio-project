# LL-0014: Contour startup can fail progressively on missing Gateway API kinds

## Summary

When a cluster does not serve specific Gateway API kinds expected by Contour, startup failure may appear one missing informer at a time. Fixing only the first missing kind can expose the next one.

## What happened

After disabling one unsupported feature, the controller started further and then failed on the next absent Gateway API kind. This repeated until all unsupported feature informers were disabled.

## Root cause

Informer registration/runtime startup checks are kind-specific. Missing resources are not always reported as one complete set in the first failure.

## Resolution

Treat missing-kind failures as a feature-set compatibility problem. Configure explicit disable flags for all unsupported Gateway API features in the target cluster, and verify controller startup end-to-end afterward.

## How to detect

If controller logs show sequential `no matches for kind ...` failures across restarts, collect the complete unsupported kind set and update feature flags in one coherent change.
