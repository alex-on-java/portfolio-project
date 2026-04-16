---
status: accepted
date: 2026-04-16
decision-makers: [alex-on-java]
---

# Strict Semvers False for Warehouse Subscriptions

## Context and Problem Statement

The Warehouse base manifest declares `strictSemvers: true` on both the image and git subscriptions. This value was added in response to LL-0003 — Kargo's admission webhook injects it as a default, and omitting it caused a permanent ArgoCD OutOfSync diff. The explicit declaration was a GitOps hygiene fix, not a deliberate filtering policy.

With the current selection strategies (`NewestBuild` for images, `NewestFromBranch` for git), `strictSemvers` has no functional effect — these strategies select by build timestamp and branch tip respectively, never parsing tags as semver. CI exclusively produces commit-SHA tags (confirmed: 45 tags in GHCR, zero semver). The field is dormant.

The risk: if `imageSelectionStrategy` is later changed to `SemVer`, `strictSemvers: true` activates silently and blocks every image in the registry. The manifest would carry a latent filter that contradicts the project's actual tagging strategy.

## Decision Drivers

- A dormant flag that can silently activate on an unrelated change is a broken window
- The project principle "Explicit Over Implicit When It Doesn't Hurt" — the manifest should express the actual intent (no semver filtering), not a coincidental webhook default
- The Kargo webhook is a defaulting webhook (`*bool`; `nil` → `true`); it does not override an explicit `false` back to `true`
- LL-0003 requires the field to be present to avoid OutOfSync — but does not prescribe a specific value

## Considered Options

1. Set `strictSemvers: false` explicitly
2. Leave `strictSemvers: true` (status quo)
3. Remove the field entirely

## Decision Outcome

**Option 1: Set `strictSemvers: false` on both image and git subscriptions.**

The value `false` is explicit, survives the webhook (which only defaults `nil`), and correctly reflects the project's tagging strategy. If a future change introduces semver tags and `SemVer` selection, the decision to enable strict filtering can be made deliberately at that point.

### Consequences

- **Good**: eliminates a latent filter that could silently block all images on strategy change.
- **Good**: the manifest now states the actual intent — no semver filtering — rather than echoing a webhook default.
- **Good**: still satisfies LL-0003 — the field is present and explicit, so no ArgoCD OutOfSync diff.
- **Neutral**: a reader seeing `false` may wonder why it was set — this ADR provides the answer.

## Pros and Cons of the Options

### Set `strictSemvers: false`

See **Decision Outcome** above.

### Leave `strictSemvers: true` (status quo)

- Good: no change needed.
- Bad: carries a dormant filter that activates silently if `imageSelectionStrategy` changes to `SemVer`.
- Bad: the value suggests semver filtering is desired, which is misleading — CI produces only SHA tags.

### Remove the field entirely

- Good: reduces manifest noise.
- Bad: the webhook re-injects `true` on next admission, recreating the LL-0003 OutOfSync problem.
- Bad: loses the explicit declaration that LL-0003 established as necessary.
