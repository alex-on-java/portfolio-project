# Deliberation Protocol

Multi-agent review pipeline for intermediate commit messages. Run this only when the user explicitly requests it — phrases like "with deliberation" or "with sub-agents" are the trigger.


## Steps

1. **Create temp directory:**
```bash
DELIB_DIR=$(mktemp -d)
```

2. **Write a draft:** Save the complete draft commit message to `$DELIB_DIR/draft.md`

3. **Spawn 2 explorer agents in parallel** (use the Agent tool with both calls in a single message):
   - **`commit-explorer-missing`** (Haiku): Give it the path to the draft file and the path to the conversation transcript. It writes findings to `$DELIB_DIR/explorer-missing.md`
   - **`commit-explorer-truthfulness`** (Haiku): Give it the path to the draft file, the plan file path (or "none"), and the staged diff (`git diff --cached`). It writes findings to `$DELIB_DIR/explorer-truthfulness.md`

4. **Once both explorers complete, spawn 2 judges in parallel:**
   - **`commit-judge-opus`** (Opus, fresh context): Give it paths to draft, both explorer files, the plan (if any), and the diff. It writes its verdict to `$DELIB_DIR/judge-opus.md`
   - **`commit-judge-codex`** (Sonnet orchestrator → Codex): Same inputs. It invokes Codex via the `skill-codex` skill and writes Codex's verdict to `$DELIB_DIR/judge-codex.md`

5. **Synthesize:** Read all 5 files in the deliberation directory. Make the final call on what stays, what gets removed, what gets added. The verdicts are advisory — you make the decision, informed by the structural tension between the agents.

6. **Include deliberation path** in the commit footer:
```
Deliberation: /tmp/tmp.xxxxxxxx
```
This is a session-local breadcrumb for debugging. It will not survive the machine session, and will be removed during squash.
