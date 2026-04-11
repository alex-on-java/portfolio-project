# LL-0016: ArgoCD ServerSideDiff must be enabled via compare-options, not syncOptions

## Summary

`ServerSideDiff=true` placed in `syncOptions` is silently ineffective. Server-side diff must be configured as a compare option.

## What happened

Several attempts assumed server-side diff was active because no validation error was shown, but diff behavior did not change. The option had been set in the wrong configuration surface.

## Root cause

ArgoCD has separate knobs for sync behavior and compare behavior. Server-side diff belongs to compare configuration (for example, `argocd.argoproj.io/compare-options`), not sync options.

## Resolution

Enable ServerSideDiff using compare options and then verify effect through observed diff behavior, not by absence of config errors.

## How to detect

If `ServerSideDiff=true` is present under `syncOptions`, treat it as misconfiguration. Confirm server-side diff by checking effective app metadata and resulting diff normalization behavior.
