# Rationale: Verification Feedback Loop

This document explains the motivation behind each part of the `verification-feedback-loop` skill. It is a companion reference, not a replacement for the skill itself.

## Why This Skill Exists

Agents treat verification as a **gate to pass through**, not as an **evidence-gathering process**. The moment an immediate failure is fixed, the agent declares victory. This is a manifestation of confirmation bias: the tendency to stop looking once something confirms the narrative ("I fixed the thing, therefore it works"). The skill exists to enforce a different standard: verification is complete only when all checks pass, not when the most visible failure is resolved.

The opening of the skill acknowledges the agent's incentive structure (it wants to finish) while firmly rejecting the behavior that incentive produces. The pressure to complete is real; it does not excuse cutting corners.

## The Umbrella Term "Test"

The skill deliberately collapses all forms of verification (linters, unit tests, integration tests, manual checks, cluster spin-ups) under a single word. This is not just a shorthand convenience. It closes a potential loophole: without it, an agent could argue that the feedback loop applies to "tests" but not to "linters" or "manual checks." By unifying the vocabulary, the skill makes clear that the feedback loop governs all verification activity, regardless of mechanism.

## The Core Rule: test -> fix -> repeat

The central rule is: **no verification step is allowed to be in a failing state when the agent declares completion.**

An important nuance follows: while actively debugging a single failing test, it is unnecessary (and wasteful) to rerun the entire suite on every iteration. But once that single test passes, everything must be rerun, because:
- The fix might have broken something else.
- Other failures might have existed alongside the original one but went unnoticed.

The emphasis on "ALL" targets a specific observed behavior: agents cherry-picking which checks to rerun, running only the one they just fixed, skipping the rest, and reporting success.

The instruction "it doesn't matter how long it takes, do not give up" targets another specific behavior: agents hitting a wall (slow tests, flaky infrastructure, cascading failures) and choosing to *reframe the situation* so they can stop. "The remaining failures are unrelated," "linters passed so it should be fine," etc. The time cost is not a valid reason to stop. The only valid exit conditions are: all checks passing, or honestly reporting a blocker.

## Escape Hatch #1: "This is not related to our changes"

This is the most frequently observed evasion. The agent encounters a failure, decides it is pre-existing, and moves on. The root cause is **completion bias**: the agent wants to finish, so it is motivated to classify obstacles as out-of-scope.

The required mitigation is rigorous: **prove it.** Check out the code to the state before the changes and demonstrate the failure exists there too. If the failure cannot be reproduced in the prior state, it belongs to the current changes and must be fixed.

A subtle but important logical point is embedded in the skill: the plan could not have anticipated this failure because it only became visible after the changes were made. The plan's silence on the issue is not evidence that the issue is unrelated; it is evidence that the plan was written before the issue was reachable. This preempts the "but the plan didn't mention this" argument.

The closing pragmatic note ("in most cases it's easier to just fix it") is intentional. The proof-of-unrelatedness process is deliberately expensive. If it takes more effort to prove something is not the agent's problem than to just fix it, the rational choice is to fix it. The high cost of the escape hatch is a feature, not a bug: it makes the "just fix it" path the path of least resistance.

## Escape Hatch #2: "I need [something] not available, but linters passed"

This targets a different evasion: the agent encounters a missing dependency or environment limitation, cannot run the real verification, substitutes a weaker check (typically linters), and uses the weaker check's passing result to claim confidence.

The mitigation has two layers:

1. **Verify the claim.** Agents sometimes declare something unavailable without actually looking. The skill requires double-checking, then asking an Explorer agent to search for scripts, skills, or instructions that might enable the check.

2. **Even if genuinely unavailable, the work is not done.** This is the critical line. The absence of a tool does not convert "unverified" into "verified." If the check cannot be run, the agent is blocked. It reports the blocker honestly. It does not get to claim the task is complete.

The underlying principle: **the status of the work is determined by the evidence, not by the agent's ability to gather evidence.** If evidence cannot be gathered, the work status is "unknown," not "done."
