# Commit Protocol

Full instructions for composing an intermediate commit message. Read this file after determining that `intermediate-commits` is the correct skill (not `squash-and-record`).


## Subject Line

Format: **sentence-style, past tense, capitalized, no trailing period.**

- Target 50–70 characters
- Start with a past-tense verb: "Fixed", "Added", "Replaced", "Improved", "Disabled", "Extracted", etc.
- Describe the outcome, not the activity

Forbidden: conventional commit prefixes (eg `fix:`, `feat:`, `ci:`, `chore:`). Write a plain sentence.


## Body Structure

Read `decision-tree.md` (same directory) and walk through Gates 1–5 to determine which sections to include.
The key rules:
- **Branch A** (plan exists): plan path in footer, write only the implementation delta
- **Branch B** (no plan): full self-contained context
- **In both branches**: include the conditional sections from Gates 2–5. `Issues faced`,
  `Workarounds applied`, and `Unexpected facts discovered` are high-signal content — even
  subtle implementation friction can reveal patterns that should be fixed upstream.

**Truthfulness rule:** Only write what you can source from the plan, the human's words, or observed system behavior. If motivation isn't established, don't invent it.

**What to avoid** (soft guidance — the judge agents enforce these through structural tension):
- Fabricated motivation — the cardinal anti-pattern
- Restating context already in the plan or earlier commits
- Placeholder sections ("None", "N/A", "Not encountered")
- Forward-looking speculation about how this commit will be used


## Think Out Loud

Before composing the draft, write your reasoning **in the conversation** (not in the commit):

> **Commit reasoning:**
> - What did the human say about motivation? (quote or "nothing stated")
> - What did I discover that was unexpected/surprising?
> - What issues did I face during implementation?
> - Did any issue or workaround repeat a known pattern that needs upstream mitigation?
> - What in the plan was a false assumption?

This externalized reasoning is visible to the user and serves as a debugging trail. If a commit message looks wrong later, the user can scroll up and see where the reasoning went off. Since thinking tokens are not visible, this is the only way to trace the agent's decision process.


## Deliberation Protocol

If the user explicitly requests deliberation ("with deliberation", "with sub-agents"), run the full multi-agent review pipeline described in `deliberation-protocol.md` (same directory) before committing.


## Case File

If the decision tree leaves you uncertain (even slightly) read `case-log.md` (same directory) before proceeding. It contains precedents from previous ambiguous situations and their human-resolved outcomes.

If your situation is genuinely novel and the case file has no similar entry:
1. Use `AskUserQuestion` to ask the human how to proceed
2. After receiving the answer, append a new entry to `case-log.md` following the format template at the top of that file


## Commit Execution

Stage specific files by name. Do not use `git add -A` or `git add .`.

Format the commit using a HEREDOC:

```bash
git commit -m "$(cat <<'EOF'
Subject line here

## What was done
...

Plan: path/to/plan/file/if/exists
EOF
)"
```
