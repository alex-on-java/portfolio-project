# LL-0011: zizmor silently accepts unreleased allowlist configuration

## Summary

zizmor v1.23.1 accepts the `rules.<rule>.config.allow` key in its configuration file without error, but the allowlist feature only exists in unreleased source code. The config is parsed and ignored — no warning, no effect.

## What happened

The `secrets-outside-env` rule was flagging legitimate uses of `${{ secrets.* }}` outside of `env:` blocks (e.g., in `with:` blocks for actions). The initial fix attempted to use the allowlist configuration documented in zizmor's source code to exempt specific workflows.

## Root cause

zizmor's configuration parser accepts unknown keys without validation. The `allow` key for per-rule allowlists exists in the development branch but was not included in the v1.23.1 release. The config file is silently accepted — zizmor starts normally, applies the rule globally, and the allowlist has zero effect.

## Resolution

Used `disable: true` for the entire `secrets-outside-env` rule as a temporary workaround:

```yaml
rules:
  secrets-outside-env:
    disable: true
```

This is coarser than desired (disables the rule entirely instead of exempting specific workflows) but is the only working option until the allowlist feature ships in a release.

## How to detect

If a zizmor rule config appears to have no effect, check whether the config keys match the *released* version, not just the source code. Compare against the release tag, not the main branch.
