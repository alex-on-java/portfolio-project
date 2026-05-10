# LL-0042: `nx show projects` Silently Accepts Unknown Flags, and Nx Flag Namespaces Diverge Between Subcommands

## Summary

Two nx subcommands name the same conceptual operation differently. The `show projects` subcommand takes `--withTarget=<name>` (short `-t`); the `affected` subcommand takes `--target=<name>` (alias `--targets`, short `-t`). Worse, `nx show projects` accepts unrecognised long flags **silently**: no warning, no error, no non-zero exit. A typo such as `--target=publish-image` produces a plausible-looking JSON array, the unfiltered list of affected projects, and the command exits zero. Fixed in commit `e03ed8d`.

## What Happened

The `changes` job in `.github/workflows/ci-pr.yml` originally invoked:

```bash
pnpm exec nx show projects --affected --target=publish-image --json
```

That command was intended to emit only the affected projects declaring a `publish-image` target. Instead, the unknown `--target` flag was silently dropped, the filter never applied, and every affected project landed in the emitted matrix. Consider a diff touching `mise.toml`, an input of `k8s-validation:validate-gitops`. The matrix would include `k8s-validation`, and the `build` entry would fail running a non-existent `k8s-validation:publish-image` target.

Replacing `--target=publish-image` with `--withTarget=publish-image` corrects the filter. On the cumulative branch diff the corrected command returns `["web-app","convergence-checker"]`, which is what the `build` matrix expects.

## Why the Bug Is Invisible to Static Checks

Three things conspire to hide the mistake. First, the wrong flag is syntactically valid: `--target=publish-image` parses as a long option with a value. Second, the output is JSON-valid, an array of strings. Third, the matrix is plausibly-shaped: a list of project names is exactly what the downstream `build` job consumes. Nothing about the shape, exit code, or stderr distinguishes a correctly-filtered result from an unfiltered one.

Lint, prek, actionlint, zizmor, conftest, and a verification sub-agent all passed the change. The mistake surfaces only when you run the exact command on a real diff and compare the output against the expected project set.

## How to Detect at Authoring Time

Before committing an nx CLI invocation, run the exact command on a real diff whose expected output set is known by hand, and compare. "Ran and produced JSON" is not verification; "produced the expected list of projects" is. This applies the project "Verify Assumptions Against the Actual Target" principle to CLIs the team has used before. Flag namespaces drift between subcommands within a single tool, and silent-accept behaviour is worse than a hard error because it hides the mistake behind a well-formed result.

## Note on Long-Flag Versus Short-Flag Form

The fix uses the verbose `--withTarget=publish-image` rather than the short `-t publish-image`, for grep-friendliness in CI YAML. A future reader who recalls the wrong flag spelling, whether `--target`, `-t`, or `--withTarget`, will still find this line by either long form. Verbose form also makes the subcommand-specific spelling explicit at the call site.

## Adoption Rule

When scripting an nx CLI command:

- Run the exact command on a real diff and verify the output against expectations *before* committing.
- Write the long-flag form at the call site so the subcommand-specific spelling is grep-able.
- Do not rely on linters or sub-agent review to catch flag-name mistakes in nx invocations; they cannot.

## Generalisation

This is a member of the broader class of CLIs that silently accept unknown flags: historically `kubectl` for some subcommands, certain `yq` versions, and tools built on permissive argument parsers. When a CLI argument parser does not reject unknown options, a typo produces a wrong-but-plausible output instead of a hard error. The only reliable detection is comparing the live output against a known-expected result on a representative input.
