---
name: feature-charter
description: |
  Create a Feature Charter — a persistent alignment document that captures what problem
  we are solving and why, with ranked trade-offs. Injected into every session and sub-agent
  so alignment survives across sessions. Use when starting a long-running feature.
user-invocable: true
disable-model-invocation: true
---

# Feature Charter

A charter is NOT an implementation plan. Do **not** invoke the `plan-creation` skill — it was designed for a different purpose. The charter captures the problem, motivation, and boundaries; the plan (a separate artifact created later) captures the how.

## Workflow

### 1. Explore and research

Before any dialogue about the charter text, invest in understanding the problem space:
- Explore the codebase to understand what exists and what's affected
- Research unknowns in docs, upstream code, or community resources
- Build throwaway PoCs if needed to verify assumptions

The goal is to clarify as many uncertainties as possible before writing. A charter built on unverified assumptions will mislead every agent that reads it.

### 2. Clarify

Align with the user through dialogue on the charter's content. Focus on areas where the user's input is essential — `references/charter-structure.md` specifies which sections require it.

### 3. Write

Compose the charter following the structure defined in `references/charter-structure.md`. Read that file before writing — it is the single source of truth for what each section contains.

#### Size budget

Keep charter content **≤ 8000 UTF-16 code units** (guideline). The `charter-injection.sh` hook appends a `## Session History` section — up to ~10 transcript paths — and, for main agents, a short nudge block. Everything together must fit under Claude Code's 10,000-unit `additionalContext` cap; beyond it, the payload is saved to a file and only a ~2KB preview is inlined, and agents often skip the re-read.

Verify with:

```bash
python3 -c "import sys; print(len(sys.stdin.read().encode('utf-16-le'))//2)" < .claude/charters/<sanitized-branch>.md
```

Byte-based tools (`wc -c`) misreport multi-byte content — use the Python one-liner. If the count approaches 8000, tighten prose; do not rely on truncation.

### 4. Save

Resolve the current branch and save the charter:

```
branch=$(git branch --show-current)
```

If the branch is empty (detached HEAD) or it's a `master`, stop and tell the user — a charter must be tied to a feature branch.

Sanitize the branch name: replace `/` with `--`. Save to:

```
.claude/charters/<sanitized-branch>.md
```

The folder `.claude/charters` is ignored via `.git/info/exclude`.
