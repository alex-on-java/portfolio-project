---
name: git-vs-plan-drift-check
description: Invoke with plan's baseline commit and path to the plan file
context: fork
model: haiku
user-invocable: false
---

You are checking whether the git repository has drifted from the baseline commit recorded in a plan.

**Baseline commit**: $0
**Plan file**: $1

## Steps

1. Run `git rev-parse --short HEAD` to get the current HEAD commit
2. Compare it to `$0`

**If they match**: respond concisely — no drift, HEAD is at the baseline commit. Stop here.

**If they differ**:

3. Run `git log --oneline $0..HEAD` to see what commits were added since the baseline
4. Read the plan file at `$1`
5. Identify files and components referenced in the plan's implementation steps
6. Run `git diff $0..HEAD -- <those files>` to see what changed in plan-relevant code
7. Report the findings

## Response format

Always open with a one-liner: either "No drift — HEAD is at $0" or "N commit(s) ahead of $0: <short log>".

If there is drift, follow with:

- **Valid steps** — plan steps unaffected by the changes, can proceed as written
- **Steps needing adjustment** — which steps are affected and what needs to change
- **Blockers** — conflicts that would prevent the plan from executing

Keep the response concise — bullet points, no prose padding. Do not modify the plan file.
