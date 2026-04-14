---
status: accepted
date: 2026-04-14
decision-makers: [alex-on-java]
---

# Go Templates with missingkey=error for All ApplicationSets

## Context and Problem Statement

All 10 ApplicationSets used ArgoCD's legacy fasttemplate engine. Fasttemplate renders missing annotation parameters as literal `{{param}}` text — ExternalDNS and cert-manager reject these as invalid domain names or zone names, making the system fail-closed by accident. This safety relies on an undocumented side effect of an unmaintained library (`valyala/fasttemplate`), not an explicit design choice (see LL-0019).

Fasttemplate is deprecated (argoproj/argo-cd#10858) — removal deferred from v3.0 to v4.0 due to blocker #12836, but migration is inevitable. The project runs ArgoCD v3.3.4. Migrating while the annotation contract is fresh context converts accidental safety into an explicit guardrail.

## Decision Drivers

- DNS isolation must not degrade silently — missing annotations must produce a hard error, not a plausible-looking default
- Relying on undocumented behavior of unmaintained code is a broken window
- Fasttemplate deprecation makes migration inevitable — doing it now preserves context
- The project principle "Explicit Over Implicit When It Doesn't Hurt" directly applies

## Considered Options

1. Go templates with `missingkey=error` (strictest)
2. Go templates with `missingkey=zero` or `missingkey=invalid`
3. Stay on fasttemplate with explicit documentation of its safety property

## Decision Outcome

**Option 1: Go templates with `missingkey=error` on all 10 ApplicationSets.**

The ApplicationSet controller errors explicitly on missing annotations — it refuses to render the Application at all. This is the strictest option Go templates offer.

Migration details:
- `{{param}}` → `{{.param}}` for simple parameters
- `{{metadata.annotations.key}}` → `{{index .metadata.annotations "key"}}` for hyphenated annotation keys (Go templates interpret `-` as subtraction in dotted access)
- YAML values quoted with single quotes where Go template braces conflict with YAML flow mapping syntax

### Consequences

- **Good**: missing annotations produce an immediate, visible controller error — fail-closed by design, not accident.
- **Good**: eliminates dependency on undocumented fasttemplate behavior before deprecation removal.
- **Good**: `index` function for annotation access is immune to silent arithmetic parsing of hyphenated keys.
- **Bad**: Go template syntax is more verbose than fasttemplate for annotation access.
- **Neutral**: migration is a one-time bulk change across all 10 files — the diff is mechanical but wide.

## Pros and Cons of the Options

### Go Templates with `missingkey=error`

See **Decision Outcome** above.

### Go Templates with `missingkey=zero` or `missingkey=invalid`

- Good: still uses the modern Go template engine.
- Bad: `missingkey=zero` renders missing keys as zero values (empty string for strings) — a shorter string that's still invalid but harder to spot in logs.
- Bad: `missingkey=invalid` renders `<no value>` — still fail-closed in practice for DNS but less obviously so.
- Bad: neither option makes the failure as loud or immediate as `missingkey=error`.

### Stay on Fasttemplate

- Good: no migration effort.
- Bad: relies on undocumented literal-preservation behavior (see LL-0019).
- Bad: fasttemplate is deprecated — forced migration later will happen without the current context of the annotation contract.
- Bad: the safety property is invisible and untestable.
