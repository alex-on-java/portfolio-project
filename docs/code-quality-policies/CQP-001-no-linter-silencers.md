# CQP-001: Linter silencers are a last resort

**Rule:** A linter silencer — an inline directive that tells a static-analysis tool to ignore a specific violation, e.g. `# noqa`, `# type: ignore`, `# pylint: disable`, `# shellcheck disable`, `// eslint-disable`, `// @ts-ignore`, `@SuppressWarnings` — is a genuine last resort. The urge to add one is almost never about a wrong rule; it is a shortcut, and naming what kind of shortcut comes first. Two patterns dominate: completion bias driving "make the hook pass and ship," or a design that the rule is correctly objecting to. In both cases the silencer is the wrong response. Reach for a pragma only after a refactor, deletion, or configuration adjustment has been considered and rejected with explicit reasoning, and only with explicit human authorization.

**Why this matters:** Inline silencers do not ratchet. A function with six arguments carrying a "too many arguments" silencer quietly becomes an eight-argument function with the same silencer — the pragma asserts "don't mind here" and the next agent reads it as permission. Each occurrence normalizes the pattern for the next agent: inline silencers are a kind of broken window, and agents under completion pressure tend to add them and invent reasons why they are fine, just to pass the pre-commit hook. *Workarounds Are Broken Windows*: an inline silencer in source carries the same compounding cost as any other tactical-win-strategic-loss workaround.

## What the urge to silence is actually surfacing

Before reaching for a pragma, name which of these the situation is. The silencer is rarely the right move for any of them.

- **Completion bias.** The hook is failing, the work is otherwise done, and the silencer is the cheapest path to a green check. The pragma freezes that bias into source for everyone after you.
- **A design the rule is correctly objecting to.** Many lint rules are *canaries*: they fire on shapes that experienced reviewers find suspicious — a function with too many parameters, a class with too many responsibilities, a catch-all exception handler, a deeply nested conditional, a cyclomatic-complexity threshold breached, a mutable default argument. The rule is the canary; the silencer kills the canary. The right response is usually to find the conflated responsibility, the missing abstraction, or the design choice being protested, and address *that*.
- **Dead context.** A pragma inherited from an earlier shape of the code that no longer applies. Pragmas survive across refactors that move the protected construct elsewhere or delete it entirely; the silencer keeps standing watch over nothing.
- **Tool overlap pretending to be a real exception.** When a project runs more than one linter that overlap in coverage (a Python project running both `ruff` and `pylint`; a JS/TS project running both `eslint` and the TypeScript compiler; a project running multiple security scanners), the same conceptual rule is often counted with slightly different semantics by each tool. The inline pragma exists only to satisfy whichever tool is stricter. The fix is a one-side configuration alignment in the project config, not source-level commentary.

## Decision framework

Walk through these in order. If an earlier rule resolves the situation, the silencer is unnecessary.

1. **Refactor before silencer.** A silencer is acknowledgment that the rule is wrong for *this* site. If the rule is right and the source can comply, comply. The relevant refactor often goes deeper than first inspection suggests:
   - **Bundle.** A function with too many parameters often grows because related arguments travel together as a group — a clock, a sleep function, an interval, and a continuation predicate that always substitute as a unit in tests. Bundling them into a frozen value object names the group, and removes the parameter-count complaint as a side effect, not as the goal.
   - **Split.** Sometimes bundling stops one step short. A function still over the threshold after bundling may be hosting two responsibilities that share an argument list — for example, parsing raw inputs *and* assembling output objects. Splitting them into separate functions can dissolve the original entirely; the parameter count was a symptom, not the disease.
   - **Delete.** Sometimes the protected construct is dead. A pragma at a module entry point, a `__main__` shim, or a wrapper class whose only consumer was removed in an earlier refactor is guarding code that no longer earns its keep. Removing the code removes the silencer for free.

2. **Named symbol beats pragma.** A pragma is passive commentary; a named, typed construct is active and enforceable. Most linters distinguish between a *bare* form of an expression (which they flag) and an *explicit, structured* form of the same expression (which they accept as a deliberate intent signal). The principle: when a linter offers a structural escape hatch, prefer the structural form. The intent ends up named in the code; the rule remains enforced for everyone else. Two illustrative patterns:
   - In Python, a "broad exception" rule flags `except Exception:` but accepts `except (Exception,):` via a tuple expression. Defining a project-level constant `ABSORBED_FAULTS: tuple[type[BaseException], ...] = (Exception,)` and writing `except ABSORBED_FAULTS:` at every deliberate absorb site signals the intent through code. The rule itself stays enforced project-wide, so any *future* `except Exception:` not via the constant still fires.
   - In JavaScript/TypeScript, an "unused variable" rule flags `function f(x) {}` when `x` is unused but accepts `function f(_x) {}` because the leading underscore is the conventional intent signal. The same pattern applies to caught-but-ignored errors (`catch (_err)`).

3. **Configured before inline.** A silencer that applies file-wide or rule-wide belongs in the project configuration (`pyproject.toml`, `.eslintrc`, `tsconfig.json`, `Cargo.toml`, etc.), not next to one occurrence. Inline pragmas are for genuine one-offs whose scope is exactly that line. A test-only relaxation (e.g., allowing hard-coded test passwords in `tests/**`), a framework-aware exemption (e.g., classes inheriting from a runtime-evaluated base must have their type imports available at runtime), or a domain-appropriate threshold (e.g., a similarity floor calibrated for fixture-shaped tests) all belong in configuration where the policy intent is visible in one place.

4. **When two tools disagree on the same rule, fix the disagreement, not the source.** Multi-linter setups regularly produce inline pragmas whose only purpose is to satisfy the stricter of two tools that overlap in coverage. Pick one policy per rule: either both enforce and the source complies, or both silence and the disable carries a brief rationale comment in configuration. Source files should never carry pragmas that exist only because two tools count slightly differently. A small but representative example: one tool's "too-many-arguments" rule may exclude `self` from the count while another includes it — the same method then passes one tool and fails the other, and the only durable fix is to align the configuration.

5. **Look for the linter's purpose-built escape hatch before adding a per-file ignore.** Many rules have framework-aware, class-aware, or decorator-aware configuration knobs that exempt the *legitimate* false-positive shape without muting the rule for unrelated violations in the same file. For example, a "type-only imports must move under a `TYPE_CHECKING` guard" rule typically offers a setting that exempts subclasses of declared runtime-evaluated base classes (e.g., framework model bases that resolve annotations at runtime). A blanket per-file ignore silences legitimate violations alongside the false positive — it is almost always too coarse.

If after walking the framework an inline pragma is genuinely the only honest answer, two further requirements apply:

- **Explicit human authorization.** The pragma is not added unilaterally by an agent; the decision is recorded in the relevant decision record (ADR, lessons learned, or — for transient cases — the commit message that introduces it), and accepted by a human reviewer.
- **Breadcrumb to the decision record.** Pragma plus a short note marking the situation as exceptional and pointing the reader to where the rationale lives. The linter directive itself stays on its own line so the linter parses it cleanly; the breadcrumb comment may wrap onto adjacent lines.

## Compliant examples

- ✓ A "duplicate code" silencer at the top of a test file removed by raising the project's similarity-threshold setting to a domain-appropriate value. Configuration captures the project-wide policy intent (test fixtures of a particular shape span 8–15 similar lines as a norm, not a smell), and no source file carries the directive.
- ✓ Inline silencers for hard-coded test passwords moved into a per-directory configuration entry that exempts only the `tests/**` tree. The exception is configured at the right scope and visible alongside related test-only exceptions.
- ✓ Multiple inline "broad exception caught" pragmas at deliberate orchestration absorb sites replaced with a single named constant of type "tuple of exception types," and a project-level convention of catching that constant at every deliberate absorb site. The named constant signals deliberate intent through code; the rule stays enforced project-wide for any unintentional broad-except.
- ✓ A "too-many-arguments" silencer on a function with six keyword-only parameters retired by responsibility-split. The function was hosting two jobs (parsing identity fields out of a configuration mapping *and* assembling runtime objects); splitting into a parsing function and an assembly function dissolved the original entirely. Removing the silencer also surfaced a duplicated parsing step elsewhere that the pragma had been masking.
- ✓ A module-level pragma and the file hosting it both deleted, after the call site the pragma was protecting was found to no longer exist. The file existed solely to host its own silencer, so the simplest refactor was deletion.

## Non-compliant examples

- ✗ A "duplicate code" silencer at file top to suppress a similarity rule on a structurally similar fixture block. Fails the 10× litmus: each new fixture-shaped test would need its own directive. The right move is configuration (similarity threshold) or refactor (shared fixture, when the tests actually share intent).
- ✗ A per-file ignore on a "type-only import" rule for a file containing framework models whose type annotations must be available at runtime. Silences legitimate violations in the same file alongside the false positive. The right move is the linter's framework-aware escape hatch (e.g., declaring a base class as runtime-evaluated), which exempts only the protected shape.
- ✗ An inline pragma without a breadcrumb pointer or rationale. The next agent reading the source has no way to tell whether the silencer is principled or accumulated.
- ✗ A "too-many-arguments" silencer on a wide function with a comment like "folding the args into a struct would just relocate the count." That argument inspects only the bundle direction and stops a step short. Look for a hidden second responsibility to split out before accepting that the count is irreducible.
- ✗ A "broad-except" silencer over a deliberate catch-all at an absorb site. The deliberate-intent signal belongs in a named typed construct, not in a passive pragma that the next agent will copy without thinking.

## Currently accepted exceptions

The single currently accepted inline-silencer pattern in this project is the bash `ERR`-trap shellcheck silencer documented in `~/.claude/CLAUDE.md` and applied at the top of every project bash script that uses the standard `set -Eeuo pipefail` + `ERR` trap pattern:

```bash
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
```

The silenced rule (shellcheck's "referenced but not assigned" check) flags any name read by the script without a clear assignment in the script's lexical scope. It is genuinely wrong here: the variables it complains about (`pcs`, `rc`, `cmd`, `file`, `line`) are assigned *inside* the trap-handler string at the moment the trap fires, but shellcheck reads the trap installation as a single-quoted string literal and cannot see those assignments. There is no source-level refactor that resolves this without losing the diagnostic the trap exists to produce. The breadcrumb-style comment marks each occurrence as exceptional and explicitly states that any new instance must be authorized by a human.

Any new exception added to this list requires the same shape: an explicit decision recorded in a decision record (ADR or lessons-learned entry), paired with the breadcrumb-style comment at the source site, accepted by a human reviewer. Agents must not unilaterally extend the list.

## Sibling enforcement

A `PreToolUse` hook nudges in real time: `.claude/hooks/universal/linter-silencers-reminder.sh` fires on Edit/Write when an inline silencer pattern appears in the new content. The reminder text lives in `.claude/hooks/lib/reminder-messages.sh` (function `reminder_linter_silencers`), and the silencer pattern set is shared with the fossilized-comments hook via `.claude/hooks/lib/silencer-patterns.sh` so the two hooks cannot drift on what counts as a silencer.

The reminder is intentionally minimal: it forces a binary decision (fix the code, or open this file), and walks a condensed form of the decision framework above. A focused agent at write time will not switch context to read another file unless redirected unambiguously, so the reminder cannot delegate the rules to this document — it must drive the decision itself. The full framework, examples, and accepted-exceptions list live here.

There is no allowlist in the hook. Encoding "this silencer is fine" in a regex would normalize the very pattern the policy warns against; the gate for new silencers is human review at commit time, including for the single accepted-exception above.
