# LL-0028: Kargo Warehouse `includePaths` requires a `glob:` prefix for `**` patterns

## Summary

Kargo Warehouse git subscriptions interpret `includePaths` patterns with `filepath.Rel` semantics by default — literal-relative path matching, not glob matching. Patterns containing `**` are treated as a literal segment and rejected via a `..`-bearing relative path, producing `NoCommitsDiscovered` with no diagnostic indication that the pattern shape is wrong. Doublestar glob semantics require the explicit `glob:` prefix.

## What happened

The convergence-checker's Warehouse subscription was configured with `includePaths: ["apps/platform/convergence-checker/**"]` to limit Freight production to changes inside the application's directory. Sibling Warehouses (e.g., `web-app`) used bare-prefix patterns without `**` and discovered commits fine. The convergence-checker Warehouse reported `NoCommitsDiscovered` continuously; no commits became Freight; the promotion pipeline never ran.

Investigation walked the Kargo source: `internal/git.ParsePathPattern` defaults to literal-relative matching; only paths prefixed with `glob:` are routed through the doublestar matcher.

## Root cause

`ParsePathPattern` evaluates patterns against changed files using `filepath.Rel(pattern, file)`. When the pattern contains `**` as a literal segment (e.g., `apps/.../convergence-checker/**`), `filepath.Rel` constructs a relative path that traverses upward — producing strings beginning with `..`. The function rejects such relative paths and reports the file as out-of-scope. The result is an empty match set, which Kargo surfaces as `NoCommitsDiscovered` — the same status it would report for a stale or empty repository.

The `glob:` prefix routes the pattern through the doublestar matcher, where `**` has the conventional cross-segment-glob meaning.

## Resolution

Prefix patterns containing `**` with `glob:`:

```yaml
spec:
  subscriptions:
    - git:
        repoURL: ...
        includePaths:
          - "glob:apps/platform/convergence-checker/**"
```

For purely directory-prefix matches (no glob metacharacters), the bare prefix is correct and `glob:` is unnecessary.

## How to detect

Symptoms of this class of pattern-matching mismatch:

- A Warehouse subscription reports `NoCommitsDiscovered` while changes are visibly present in the configured paths on the configured branch.
- A sibling Warehouse with a bare-prefix path discovers fine; the broken Warehouse uses `**`.
- `kubectl -n <kargo-ns> describe warehouse <name>` shows `Healthy: true` but no Freight events.

When configuring Warehouse `includePaths`:

- Bare prefix (`apps/foo`) — literal-relative, no prefix required, matches descendants.
- Doublestar (`apps/foo/**`) — requires `glob:` prefix to be parsed as a glob.
- Negation patterns and other doublestar features — same rule, `glob:` required.

The Kargo convention diverges from `.gitignore`, Bazel, ArgoCD's own glob conventions, and most general-purpose path-matching tools, all of which treat `**` as glob by default. Verify the pattern actually matches by triggering a known-relevant commit and observing the Warehouse Freight events.
