---
name: intermediate-commits
description: |
  Triggers on every `git commit` on a non-default branch. Must be loaded together with the `squash-and-record` skill: you will read full skill description of both skills to judge which commit to choose.

---

# Intermediate Commits

This skill governs commits on feature branches during active work.
It helps capture implementation context, discoveries, and pitfalls while the agent has peak context — the moment right after doing the work.

Intermediate commits are **durable inter-agent communication artifacts**; they are the only record that survives agent handoffs when multiple agents collaborate on a single feature. They capture what happened during implementation: what worked, what broke, what was surprising. They do not restate what was planned.

## When to use this skill

Use this skill when **all** of the following are true:
- You are on a feature branch (not the default branch)
- Work is in progress — implementation, CI fixes, deployment fixes, review feedback

**If unsure, default to this skill.** An intermediate commit can always be squashed
later; a premature squash loses the implementation timeline.

## How to proceed

Read `references/commit-protocol.md` for the full protocol: subject line format, body structure, deliberation pipeline, and commit execution.
