---
name: worktree-create
description: Triggers when the user asks to create or remove a git worktree. Guides agent to make intelligent sync decisions about what to symlink vs recreate fresh.
disable-model-invocation: false
user-invocable: false
---

# Worktree Creation

Triggers when the user asks to create a worktree, work on a branch in isolation, or remove an existing worktree.

## Creation Workflow

### 1. Create the worktree

```bash
${CLAUDE_SKILL_DIR}/scripts/create-worktree.sh add <branch>
```

The script creates a worktree at `../pp-worktrees/<branch>/` relative to the repo root. It handles branch detection (local, remote-tracking, or new) and safety checks. On success, it outputs the absolute worktree path.

### 2. Decide what to sync

Items from `.git/info/exclude` are automatically synced during worktree creation and won't appear in this output.

Run `list-ignored` to see what gitignored items exist in the main repo:

```bash
${CLAUDE_SKILL_DIR}/scripts/create-worktree.sh list-ignored
```

Output is tab-separated: `<type>\t<path>\t<source>` — one entry per line. These are items that exist on disk in the main repo but won't be present in the new worktree (because they're gitignored).

The default is to **sync everything**. Only skip an item when there is a clear, specific reason — not "just in case." Think through each item:

- **Would the user's changes directly invalidate this item?** If they're updating `package.json`, symlinked `node_modules` would be wrong — the worktree needs a fresh `npm install`. If they're only changing application code, there is no conflict.

If you're unsure what specific item to do, ask the Explorer agent to figure this out.
In case of uncertainty, elicit the user's input, but lean toward syncing by default.


### 3. Perform linking

For items you decide to sync:
- **Directories → symlink**: `ln -s <main-repo-path> <worktree-path>`. One link, shared state. Changes in either location are reflected immediately.
- **Files → hardlink**: `ln <main-repo-path> <worktree-path>`. Shares content on disk at creation time. Note: editors that save via temp-file-and-rename (most IDEs, vim) break the link silently — after that, the two copies diverge. This is fine for config and marker files that rarely change; for files that will be actively edited, prefer symlinks. Create parent directories first with `mkdir -p` if needed.

### 4. Post-setup

If the task requires fresh dependencies, run the appropriate install command in the worktree directory (e.g., `npm install`, `pip install -e .`, `go mod download`).

## Removal Workflow

```bash
${CLAUDE_SKILL_DIR}/scripts/create-worktree.sh remove <branch>
```

The script checks for uncommitted changes (warns but does not block), moves the worktree to trash (recoverable), prunes the git worktree entry, and attempts a safe branch delete. If the branch isn't fully merged, it reports this — ask the user before force-deleting with `git branch -D`.

## Examples

These illustrate the reasoning, not rules to memorize:

- **"Create a worktree to fix a CSS bug"** — Code-only change. Symlink `node_modules`, `.idea/`, any build output. Skip caches (they regenerate). Fast setup.
- **"Create a worktree to upgrade React"** — Dependency change. Skip `node_modules` (needs fresh install). Symlink `.idea/`, build output for unrelated apps. Run `npm install` after setup.
- **"Create a worktree to work on Terraform changes"** — Infrastructure work. Symlink application build output and dependency dirs (no reason to rebuild apps). Skip `.terraform/` if it exists (state is environment-specific).
