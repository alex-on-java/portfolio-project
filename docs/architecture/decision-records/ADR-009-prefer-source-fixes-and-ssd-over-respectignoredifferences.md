---
status: accepted
date: 2026-04-11
decision-makers: [alex-on-java]
---

# Prefer Source Fixes and Server-Side Diff over `RespectIgnoreDifferences`

## Context and Problem Statement

During ArgoCD drift remediation work, one recurring option was to use `ignoreDifferences` with `RespectIgnoreDifferences=true` to stop OutOfSync churn. While this can make sync status look stable, it can also mask real configuration or ownership problems and turn future debugging into guesswork.

The project needed an explicit rule for drift handling that reflects the working principles "Workarounds Are Broken Windows" and "Explicit Over Implicit".

## Decision Drivers

- Keep drift signals trustworthy for future operators and agents
- Avoid band-aid mechanisms that hide root causes behind green status
- Prefer explicit, source-level convergence over diff masking
- Reduce risk of latent bugs caused by ignored fields silently diverging
- Keep exceptions visible, narrow, and auditable

## Considered Options

1. Prefer source fixes and ServerSideDiff; treat `RespectIgnoreDifferences` as exceptional
2. Use `ignoreDifferences` + `RespectIgnoreDifferences` as standard drift-control tool
3. Broadly suppress drift by manager/path patterns to minimize operational noise

## Decision Outcome

**Option 1: Prefer source fixes and ServerSideDiff, with `RespectIgnoreDifferences` as an explicit exception path only.**

Default strategy:
- fix manifest values at source when platform mutation is deterministic,
- use ArgoCD Server-Side Diff in the correct compare-options location,
- remove ignore rules when root-cause convergence is achievable.

Exception strategy:
- allow `ignoreDifferences`/`RespectIgnoreDifferences` only when a field is provably non-roundtrippable or otherwise impossible to converge at source,
- scope ignores to the smallest possible target,
- document why the exception exists and what risk it introduces.

### Consequences

- **Good**: OutOfSync remains a reliable signal rather than a cosmetic one.
- **Good**: hidden divergence risk is reduced because real differences are fixed, not concealed.
- **Good**: operational intent is explicit and easier to audit in future incidents.
- **Bad**: requires more up-front investigation before accepting a workaround.
- **Neutral**: in a small set of edge cases, explicit exceptions are still needed and must be maintained deliberately.

## Pros and Cons of the Options

### Source Fixes + Server-Side Diff (Exceptions by Design)

See **Decision Outcome** above.

### `ignoreDifferences` + `RespectIgnoreDifferences` as Default

- Good: fast way to suppress noisy drift loops.
- Good: can restore green dashboards quickly.
- Bad: can normalize hidden misconfiguration and defer failures to harder-to-debug moments.
- Bad: weakens the meaning of sync status over time.

### Broad Drift Suppression

- Good: lowest immediate operational noise.
- Bad: highest long-term risk of silent divergence.
- Bad: makes regression detection and incident triage significantly harder.
- Bad: conflicts with project principles around explicitness and avoiding workaround accumulation.
