# CQP-002: Comments fossilize context

**Rule:** Default to writing no comments in code. Add one only when the WHY is non-obvious: a hidden constraint, a subtle invariant, a workaround for a specific bug, behavior that would surprise a reader.

**Why this matters:** A comment carries implicit authority. It sits next to the code as if still true, the system around it changes independently, and the next reader treats stale context as current. The commit message is a better home for the WHY: it is tied to a point in time and a changeset, the comment is tied to neither.

## What this policy covers and does not cover

Pragmas and tool directives (`# shellcheck disable=...`, `# noqa`, `// eslint-disable-next-line`, `# type: ignore`, `# pylint: disable`) are not comments for this policy. They are governed by [CQP-001: Linter silencers are a last resort](CQP-001-no-linter-silencers.md).

Shebangs (`#!/usr/bin/env bash`), encoding declarations, and TypeScript reference directives (`/// <reference ... />`) are not comments either: they are language-level directives.

## Compliant examples

- ✓ No comment at all. The function name, parameter names, and structure communicate intent.
- ✓ A short note pointing at a commit when a workaround is genuinely required: `# Workaround for issue resolved in <commit>; remove when …`.
- ✓ A section divider that groups related code where the grouping is non-obvious from naming alone.
- ✓ A note recording a non-obvious invariant or constraint that callers cannot derive from the signature: a thread-safety note on a function that is intentionally non-reentrant, for instance.

## Non-compliant examples

- ✗ A comment restating what the code does (`# increment counter` above `counter += 1`).
- ✗ A docstring that paraphrases a single-line function signature.
- ✗ A WHY explanation that belongs in the commit message: motivation for an architectural choice, alternatives that were rejected, references to a past incident.
- ✗ "Used by X" or "added for the Y flow" references. They describe call-site context that rots as the codebase evolves; the commit message and `git blame` carry that context with proper time-binding.
- ✗ A comment marking the absence of something: `# no error handling needed here` says nothing the absence itself does not already say.

## Exceptions

(none yet — false positives go here with date and reason)

## Sibling enforcement

A `PreToolUse` hook nudges in real time: `.claude/hooks/universal/fossilized-comments-reminder.sh` fires on Edit/Write to common code extensions, and the reminder text lives in `.claude/hooks/lib/reminder-messages.sh` (function `reminder_fossilized_comments`).

The reminder is intentionally minimal: it forces a binary decision (drop the comment, or open this file). A focused agent at write time will not switch context to read another file unless redirected unambiguously, so the reminder cannot delegate the rules to this document — it must drive the decision itself. The full rules and examples live here.

If this policy is updated, review the hook reminder text to keep the two aligned.
