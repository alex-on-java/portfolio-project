# LL-0045: Conftest Loads Every Policy File for Every Parser-Specific Test

## Summary

`conftest verify` evaluates every `deny` rule in the policy directory against every test fixture, regardless of which parser produced the input. A policy written for one input shape (a JSON object from `package.json`, say) therefore runs against unrelated shapes too, including Dockerfiles parsed into arrays of command objects. Any structural access that assumes the wrong shape crashes the verify run with a cryptic `object.get: type error`. The message names neither the offending policy nor the offending input.

## What the Failure Looks Like

`conftest verify --policy policies/conftest` exits non-zero with a single line resembling:

```
object.get: operand 1 must be object but got array
```

No filename, no rule name, no input identifier. The crash aborts the verify run before any test result is reported, so a freshly added policy appears to break unrelated tests.

## Why This Is Non-Obvious

A reader reasonably assumes conftest pairs each parser with its own policies: a Dockerfile parser with `dockerfile_*.rego`, a JSON parser with `npm_*.rego`, and so on. There is no such pairing. All `.rego` files in the policy directory share the same `package` (here, `package main`), and every `deny` rule is collected into a single rule set that runs against every fixture. The cross-format application is implicit in the conftest loading model, and the error message does not surface it when a structural call fails.

A policy authored and unit-tested only against its intended parser format therefore passes its own tests in isolation. It then takes down `conftest verify` the first time a sibling test loads a fixture of a different shape.

## Root Cause

Rego built-ins like `object.get`, `object.keys`, and indexed access fail with a type error when called against a non-object input. A policy that begins with `object.get(input, ...)` (or any equivalent unguarded structural access) presumes `input` is an object. The presumption is violated at runtime when the same policy is evaluated against an array-shaped fixture from a different parser.

In this repo, the `package.json` override-pinning policy (`policies/conftest/npm_dependency_pinning.rego`) was the first to walk an `overrides` subtree with `object.get(input, group_path, {})`. The Dockerfile parser test fixtures supplied an array of command objects; the override rule fired against that array and crashed `conftest verify`.

## Resolution

Guard input shape at the top of every rule whose body assumes structure:

```rego
deny contains msg if {
    is_object(input)
    some group_path in _npm_override_groups
    overrides := object.get(input, group_path, {})
    # ...
}
```

`is_object(input)` short-circuits the rule for any non-object fixture without raising. Rules intended for array-shaped inputs use `is_array(input)` symmetrically. A rule that walks the command list of the Dockerfile parser can iterate `some cmd in input` directly, which already implies array shape and is safe.

## How to Detect

Symptoms of an unguarded shape assumption in a shared-package conftest policy set:

- A new policy passes its own `_test.rego` cases, but `conftest verify --policy <dir>` aborts with `object.get: type error` (or a similar built-in type error) and no further detail.
- The error appears the first time a fixture authored for a *different* parser is added, even though the new fixture is unrelated to the new policy.
- Removing the new policy file makes the verify run pass again; removing the unrelated fixture also makes it pass.

## Adoption Rule

Every Rego policy in a shared-package conftest directory must guard `input` shape before any structural access: `is_object(input)` for object-keyed fixtures, `is_array(input)` for arrays, and so on. Run `conftest verify --policy <dir>` against the full fixture set of the repository, not only the format the policy targets, before relying on it.
