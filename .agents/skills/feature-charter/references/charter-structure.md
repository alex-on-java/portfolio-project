# Feature Charter Structure

This document defines the charter sections. Each section has a purpose statement and guidance on what belongs (and what doesn't).

---

## Problem

What is broken, missing, or insufficient. Describe concrete, observable symptoms — not abstractions. A reader with no prior context should be able to independently verify that this problem exists.

**Does not belong here:** solutions, implementation hints, or restatements of the motivation.

## Motivation

The deep WHY behind solving this problem. What need or pain drives it, why it matters, and the consequences of not solving it. This must come from the user — if they have not stated it, it must be elicited. Do not fabricate motivation.

**Does not belong here:** surface-level restatements ("because we need it") or the problem description in different words.

## Intended Outcome

What the world looks like after the feature is complete. Describe the end state at a high level — observable behaviors, capabilities, or properties that will exist.

**Does not belong here:** implementation approach, architecture decisions, or success criteria phrased as tests.

## Boundaries

What trade-offs we refuse to accept during implementation. These derive from the project's working principles (`docs/WORKING_PRINCIPLES.md`) but are tailored to the specific feature context.

Only list refusals — everything not listed is implicitly acceptable.

### Non-Negotiable

Trade-offs that are completely off the table. Violating any of these invalidates the implementation regardless of other benefits.

Each entry: state the constraint, then why it's non-negotiable in this context.

### Last Resort Only

Trade-offs acceptable only when all alternatives have been exhausted and the reasons are documented in the commit record. These are guardrails, not walls — but crossing them requires explicit justification.

Each entry: state the constraint, then what circumstances might justify it.

## Principles in Focus

Which working principles are most relevant to this feature and how they apply specifically. Do not restate the principles — reference them by name and explain the specific tension or application in this context.

## Out of Scope

What this feature deliberately does not cover. For each exclusion, state why it's excluded — otherwise a future agent may interpret the omission as an oversight and "fix" it.

## Session History

**Auto-managed.** The `charter-injection.sh` hook appends this section with each main-agent session's transcript path. The hook matches this exact heading; do not alter or annotate it, and do not author entries under it manually. Do not add any section after it — it must remain the last section of the file, or the sub-agent stripping logic will drop whatever follows.
