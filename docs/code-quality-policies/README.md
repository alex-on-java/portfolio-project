# Code Quality Policies

Reviewable rules that govern the artifacts the agent produces. Each policy captures a rule that resists static enforcement: too context-dependent for a linter, too prone to false positives. The check happens via focused review against the policy text, with examples and exceptions doing the heavy lifting.

## What belongs here

Rules about how committed code should look:

- Patterns to avoid in source files
- Constraints on configuration shape
- Conventions where mechanical enforcement would produce noise

The common thread: the rule is judgement-dependent enough that a linter would either miss real violations or flag legitimate code, but a focused agent reading examples and exceptions can usually decide correctly.

## What does not belong here

- Operational rules for how the agent acts during a session, see [Agent Operating Policies](../AGENT_OPERATING_POLICIES.md)
- Architectural decisions, see [Decision Records](../architecture/decision-records/README.md)
- Platform behaviors and gotchas, see [Lessons Learned](../lessons-learned/README.md)
- Statically enforceable rules (linter rules, schema constraints) belong in `.pre-commit-config.yaml` or equivalent

## Lifecycle

CQPs are **living rules**, distinct from frozen artifacts like ADRs and Lessons Learned. An exceptions list grows as edge cases surface, examples are refined, and an obsolete policy may be retired. New CQPs typically emerge during a `squash-and-record` flow when a branch articulates a generalized rule, but later edits happen ad-hoc as the policy evolves.

CQPs are intentionally **not** indexed in commit messages. Discoverability is through this README and `git log <file>` on the policy itself. Listing them in a commit message would impose frozen-artifact semantics on a living rule and create stale cross-references the moment an exception is added.

## Cross-referencing sibling enforcement

Each policy file ends with a *Sibling enforcement* section listing any hooks, lint rules, or pre-commit checks that nudge or enforce the same rule. The cross-reference goes both ways: the hook or check points back here, and the policy file points at the hook. Updating either side without updating the other risks drift, and the cross-reference is the maintenance hook that catches the next agent.

## Entries

- [Linter silencers are a last resort](CQP-001-no-linter-silencers.md)
- [Comments fossilize context](CQP-002-no-fossilized-comments.md)
- [Pin external dependencies to exact versions](CQP-003-pin-external-versions.md)
- [Test fixtures must use values distinct from production](CQP-004-test-fixtures-distinct-from-production.md)
- [External-resource identifiers must be required inputs](CQP-005-external-resource-identifiers-as-required-inputs.md)
