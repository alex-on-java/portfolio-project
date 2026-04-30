# LL-0033: ArgoCD reports `Synced` briefly after a manifest mutation, before the controller detects the divergence

## Summary

ArgoCD's `Application.status.sync.status` is updated asynchronously by the controller's reconciliation loop. Immediately after a manifest mutation (e.g., a fresh Kargo promotion writes new images and hostnames into the stage branch), there is a window — typically seconds — during which the live `Application` reports `Synced`+`Healthy` against the *previous* tracked revision, before the controller has observed the new revision and re-evaluated drift. A single observation taken inside this window is falsely-positive: the gate would declare convergence on stale state. Sustained-observation across multiple cycles is required to distinguish true convergence from a transient `Synced` snapshot.

## What happened

During development of the convergence-checker's evaluator, an early loop took one observation per cycle and declared convergence as soon as every Application reported `Synced+Healthy`. End-to-end testing produced an intermittent false positive: a cycle running shortly after a Kargo promotion would observe `Synced+Healthy` on every Application, post `success`, and then — visible only by re-checking minutes later — the same Applications would briefly transition to `OutOfSync` before re-converging.

The window is short (single-digit seconds in practice) but deterministic: every fresh promotion produces it. A gate that polls at any cadence and accepts a single matching cycle will hit this window often enough to be unreliable for merge-blocking purposes.

## Root cause

ArgoCD's controller reconciliation is polling-based and asynchronous. The pipeline that updates `status.sync.status` runs periodically and not as an immediate consequence of a Git mutation:

1. The Git source mutates (a Kargo promotion writes a new image SHA to the stage branch).
2. The Application's tracked revision (`status.sync.revision`) is *not* updated until the controller next polls the source.
3. The Application's verdict (`status.sync.status`) is computed against the previously-recorded revision; until the controller observes the new revision, the verdict reflects the prior state.
4. After the next polling cycle, the controller recomputes against the new revision, marks `OutOfSync`, applies, and returns to `Synced` once the new state is reconciled.

The window is the gap between steps 1 and 3. During this gap, the Application's API surface looks identical to its converged state — same `sync.revision`, same `sync.status`, same `health.status`. There is no per-Application timestamp the evaluator can read to detect that the snapshot is stale.

## Resolution

Require the same all-healthy verdict on N consecutive cycles before declaring convergence (the **stability counter**). Configuration:

- `stability_threshold = 5` cycles by default.
- `check_interval_seconds = 12` between cycles.
- Total dwell-time required for a `success` verdict: ~60 seconds — comfortably longer than the observed transient-Synced window across realistic promotion patterns.

The counter resets on any non-converged observation. A successful `success` post requires 5 consecutive cycles where every Application is `Synced+Healthy` and every Stage is `Healthy` with `lastPromotion.status: Succeeded`. The counter is bounded so it does not grow unboundedly across long-running clusters (the status description reads "healthy for N consecutive" up to a cap, then stops incrementing the displayed count).

The 5-cycle/60-second dwell is empirical; the actual transient window has been observed in single-digit seconds, so the threshold has comfortable margin. If the underlying ArgoCD reconciliation cadence changes materially, the threshold can be re-tuned via `settings.toml`.

## How to detect

Symptoms of this class of transient false-positive:

- An evaluator that takes one observation per cycle reports `success` intermittently after recent promotions.
- Re-checking minutes later shows the cluster transitioned through `OutOfSync` between observations.
- ArgoCD's UI shows a short flicker in the timeline: `Synced` → `OutOfSync` → `Synced`.

When designing any gate that consumes ArgoCD `Application.status` for merge-blocking decisions, treat single observations as unreliable. Multi-cycle stability is the load-bearing property; the specific cycle count and interval can be tuned but the multi-cycle requirement is non-optional.

The same reasoning applies to Kargo `Stage` evaluation: `lastPromotion.status` updates asynchronously after a promotion completes, and a single observation can be stale for the same reason.
