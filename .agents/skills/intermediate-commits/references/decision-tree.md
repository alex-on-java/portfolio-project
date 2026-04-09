# Decision Tree

Walk through these gates in order. Each gate adds or removes content from the commit body.
The gates are cumulative — a single commit can trigger multiple branches.


## Gate 1: Does a plan file exist for the current work?

**Yes → Branch A (plan-anchored commit)**

The plan reference goes in the commit footer (see commit-protocol.md, Commit Execution).
The commit body focuses on the **implementation delta** — what diverged from the plan, what surprised, what broke.
Do not restate the problem, motivation, or approach already documented in the plan.

Sections to include:
- `## What was done` — brief summary of the implementation step
- `## Divergences from plan` — only if the work deviated from the plan's expectations
- Conditional sections from Gates 2–5 below

**No → Branch B (self-contained commit)**

The commit body must stand alone. Include:
- `## Problem` — what was wrong, missing, or needed
- `## Motivation` — why this needed addressing (only if the human established motivation;
  omit entirely if no motivation was stated — a missing section is honest)
- `## What was done` — the approach taken
- `## Why this approach` — rationale for this specific solution
- Conditional sections from Gates 2–5 below

**Plan exists but work has materially diverged** → treat as Branch B. The plan no longer
accurately represents the context, so the commit must be self-contained.


## Gate 2: Is this a fix for a previous commit in the same branch?

**Yes** → Add a line referencing the prior commit:
```
Fixes: <hash> <subject>
```
Then describe what went wrong with the previous commit and why. This is valuable context
for the squash skill — it reveals the learning sequence.

**No** → No action.


## Gate 3: Did you discover something surprising about the platform or tools?

**Yes** → Add a `## Unexpected facts discovered` section. Include:
- The observed behavior (what actually happened)
- The evidence (error messages, commands run, annotations seen)
- Why it was surprising (what you expected instead)

This is the most valuable content in intermediate commits — it seeds future Lessons Learned
files during squash. Be specific and evidence-based.

**No** → Omit the section entirely. Do not include it with "None" or "N/A."


## Gate 4: Is motivation newly established by the human in this session?

**Yes** → Include `## Motivation` using the human's own framing. Do not paraphrase into generic language. If the human said "this crashes in production when email is null," do not rewrite into "to improve null-safety across the authentication pipeline."

**No (already in plan or earlier commit)** → Reference where it's stated:
```
Motivation established in plan
```
or
```
Motivation established in commit: <hash> <subject>
```
Do not restate motivation that exists elsewhere.

## Gate 5: Did implementation hit issues or require a workaround?

**Yes** → Include the relevant section(s), even when the issue/workaround seems small.
Small execution friction is an early signal of tooling/process debt and should be
preserved in intermediate commits.

- `## Issues faced` — include what failed or blocked, the evidence, and the impact.
- `## Workarounds applied` — include what workaround was used, why it was chosen, and
  any constraint it introduced.

If the same issue or workaround appears recurrent, add one line in the relevant section:
```
Systemic follow-up: <upstream mitigation direction>
```
Use this to point at higher-level mitigation (for example instructions, hooks, skills,
or architecture/process hardening), rather than normalizing recurring local workarounds.

**No** → Omit these sections entirely. Do not add placeholders ("None", "N/A").


---

## Examples

### Good: Branch A commit (plan exists)

```
Enabled ConfigMap hash suffixes for automatic rollout on config change

## What was done
Removed `disableNameSuffixHash: true` from all overlay kustomization.yaml files.
Kustomize now appends a content hash to ConfigMap names and rewrites all
configMapKeyRef.name references via its nameReference transformer.

## Unexpected facts discovered
Kustomize's nameReference transformer only rewrites `configMapKeyRef.name` fields
inside container env blocks. Volume mounts using `configMap.name` are also rewritten,
but only if the ConfigMap resource is in the same kustomization. Cross-kustomization
references (e.g., a base ConfigMap referenced by an overlay Deployment) require the
ConfigMap to be listed in the overlay's `resources` for the name rewrite to apply.

Plan: ~/.claude/plans/smooth-floating-bee.md
```

### Good: Branch B commit (no plan, full context)

From commit `b892cd9`:

```
Added git subscription to Warehouse for deterministic commit-pinned promotions

## Problem
The Warehouse subscribed only to an image registry. Freight contained only an
image digest — no git commit reference. The promotion task cloned the source
repo using `branch:`, which resolved to whatever branch HEAD was at clone time.

This caused two failures:
1. The same freight promoted to different stages at different times could clone
   different branch HEADs — violating the promotion-as-verification guarantee.
2. Manifest-only changes (no new image) created no freight at all.

## Motivation
Freight must pin both an image digest and a git commit SHA for reproducible
promotion across stages. The project principles require decisions that hold at
10x scale — with more contributors, the drift window widens.

## What was done
Converted from Kargo's "Image Updater" pattern to the "Common Case" pattern
(image + git subscription, deterministic commit-pinned checkout).

## Why this approach
This follows Kargo's documented "Common Case" pattern and reuses the existing
kustomize replacement infrastructure without introducing new patterns.

## Unexpected facts discovered
In-flight freight (created before this change, containing no git commits) will
cause promotions to fail after the new ClusterPromotionTask is deployed, because
`commitFrom(vars.gitRepoURL)` returns nil when the freight has no commits.
```

### Good: Fix for a previous commit

From commit `5dfb8ef`:

```
Added explicit webhook defaults to warehouse git subscription to resolve OutOfSync

Fixes: b892cd9 Added git subscription to Warehouse for deterministic commit-pinned promotions

## What was done
Added `discoveryLimit: 20` and `strictSemvers: true` explicitly to the base
warehouse template's git subscription.

## Why this approach
The Kargo admission webhook injects these defaults during admission. Without
them in the desired state, ArgoCD sees a permanent diff between desired and
live state, causing continuous reconciliation.

## Unexpected facts discovered
The Kargo admission webhook adds `strictSemvers: true` to git subscriptions
using `NewestFromBranch` commit selection strategy, even though strict semver
filtering is semantically irrelevant for branch-based selection. This appears
to be a blanket default applied regardless of selection strategy.
```

### Bad: Fabricated motivation on a trivial change

```
Renamed variable for improved code clarity and maintainability

## Problem
The variable `svc` was abbreviated, reducing code readability for new
contributors and making the codebase harder to maintain at scale.

## Motivation
Clean, readable code is essential for long-term project health. This
rename improves developer experience and reduces cognitive load during
code reviews, supporting the team's commitment to high-quality software.

## What was done
Renamed `svc` to `service` across 3 files.

## Why this approach
Full words are more readable than abbreviations.
```

**What's wrong:** The motivation is entirely fabricated. Nobody said this was
essential for project health. The honest commit:

```
Renamed `svc` to `service` across Kargo stage templates

## What was done
Renamed `svc` to `service` in 3 stage template files for consistency
with the naming used in the rest of the codebase.
```

No `## Motivation` section — because none was established. No `## Problem`
section — because there wasn't a problem, just a preference. The absence of
these sections is the honest signal.
