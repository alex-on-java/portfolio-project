# LL-0031: Dynaconf with `environments=False` treats `[default]` as a literal nested table — the magic-section behavior is opt-in

## Summary

Dynaconf's well-known `[default]` (and `[development]` / `[production]` / etc.) magic-section behavior — where keys under those sections are unwrapped to the top level — is gated on `environments=True`. With the default `environments=False`, those section headers are parsed as literal nested-table keys: `[default]` produces `settings.DEFAULT.<key>`, not `settings.<key>`. Code that reads `settings.<key>` raises `AttributeError` despite the value clearly being present in `settings.toml`.

## What happened

The convergence-checker's `settings.toml` initially looked like:

```toml
[default]
check_interval_seconds = 12
stability_threshold = 5
```

The Dynaconf loader was instantiated with default arguments (no `environments=True`). Code accessing `settings.check_interval_seconds` raised `AttributeError`. The same access in a Python REPL with the same loader produced the same error. Investigation showed `settings.DEFAULT.check_interval_seconds` was the live access path — the `[default]` header had been parsed as a literal section, not as Dynaconf's environment-magic marker.

The defect was latent from the initial commit: the test suite stubbed `settings` directly without going through TOML parsing, so the reading path was never exercised in CI. The error surfaced only when the production image actually loaded `settings.toml` from a wheel install (where `Path(__file__).resolve().parent.parent.parent` no longer landed in the project root — see also `LL-0030` for the wheel/editable interaction).

## Root cause

Dynaconf's magic-section handling is opt-in. The `Dynaconf(settings_files=[...])` constructor accepts an `environments` parameter (defaulting to `False`) that controls whether section headers like `[default]`, `[development]`, `[production]` get unwrapped at the top level or parsed as literal nested-table keys. With the default, TOML parsing is faithful: `[default]` is a section, and the keys under it nest as `settings.DEFAULT.<key>` (Dynaconf normalizes section names to uppercase).

The behavior is documented in Dynaconf's reference, but the documentation prominently demonstrates the magic-section pattern in tutorials and quick-start examples — making the literal-section behavior a surprise for anyone whose mental model formed from the tutorials.

## Resolution

Two options work; we chose the second:

1. **Opt into the magic** — instantiate as `Dynaconf(environments=True, settings_files=[...])`. Keys under `[default]` unwrap to the top level; environment-aware overrides via `[development]`/`[production]` become available as a side effect.
2. **Drop the section header** — write `settings.toml` without any section, so all keys are at the top level. Dynaconf parses them as `settings.<key>` directly. No `environments=True` needed.

Option 2 was chosen because:

- The convergence-checker has a single environment (the cluster it runs in); environment-aware config layering is unnecessary.
- A flat `settings.toml` is the simplest shape that produces the desired access path.
- Avoiding `environments=True` means future readers do not need to know which section (`[default]` vs `[development]`) takes precedence in which mode — a cognitive cost paid for no benefit.

## How to detect

Symptoms of this class of section-header confusion:

- `settings.<key>` raises `AttributeError`; the same key is clearly present in `settings.toml` under `[default]` (or `[development]`, etc.).
- `settings.DEFAULT.<key>` (or `settings.DEVELOPMENT.<key>`) returns the value successfully.
- `Dynaconf(settings_files=[...])` is instantiated without `environments=True`.

When auditing Dynaconf usage:

- A `settings.toml` with `[default]` sections paired with a `Dynaconf()` constructor lacking `environments=True` is the tripwire pattern.
- Either remove the section header or pass `environments=True` — there is no third correct configuration.
- Tests that mock `settings` directly hide this defect; the read path through `settings.toml` should be exercised in at least one integration-level test.
