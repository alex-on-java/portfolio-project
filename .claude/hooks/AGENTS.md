# Hook Invocation Control

## Variable system

Two env var prefixes control whether a hook runs:

| Prefix | Role | Lives in |
|--------|------|----------|
| `HOOK_DEFAULT_<NAME>` | Committed default state | `settings.json` `env` block |
| `HOOK_INVOCATION_<NAME>` | Runtime override for one session or run | Shell or `settings.local.json` `env` block |

`HOOK_INVOCATION_<NAME>` takes precedence. When neither is set, the hook runs (effective default: `enabled`).

Valid values: `enabled` / `disabled`.

## Naming rule

Derive `<NAME>` from the hook filename:
1. Take the basename, strip `.sh`
2. Apply `tr '[:lower:]-' '[:upper:]_'`

Example: `local/stale-kubectl-contexts-reminder.sh`
→ `HOOK_DEFAULT_STALE_KUBECTL_CONTEXTS_REMINDER`
→ `HOOK_INVOCATION_STALE_KUBECTL_CONTEXTS_REMINDER`

## Common workflows

**Disable a hook for this machine** — add to `settings.local.json` `env`:
```json
"HOOK_DEFAULT_STALE_KUBECTL_CONTEXTS_REMINDER": "disabled"
```

**Disable a hook for one run** — prefix the `claude` invocation:
```sh
HOOK_INVOCATION_STALE_KUBECTL_CONTEXTS_REMINDER=disabled claude
```

**Ship a hook as opt-in (dormant by default)** — add to `settings.json` `env`:
```json
"HOOK_DEFAULT_MY_HOOK": "disabled"
```

**Enable an opt-in hook for one run** — prefix the `claude` invocation:
```sh
HOOK_INVOCATION_MY_HOOK=enabled claude
```

## Rename warning

If a hook script is renamed, `<NAME>` changes. Update:
- Any `HOOK_DEFAULT_<OLD_NAME>` entries in `settings.json`
- Any `HOOK_INVOCATION_<OLD_NAME>` entries in `settings.local.json` or team docs

## Same-basename collision

Two hooks in different directories with identical filenames (e.g., `local/foo.sh` and `universal/foo.sh`) share the same `<NAME>`. One `HOOK_INVOCATION_FOO` value applies to both.
