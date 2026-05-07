# CQP-005: External-resource identifiers must be required inputs, not silent defaults

**Rule:** When an application reads a value that names an externally-defined resource — a queue, a topic, a database, a configuration object, a hostname, a contract identifier — the application must require that value to be supplied explicitly at startup. A built-in default that happens to equal the deployed resource name is forbidden: it masks rename mistakes by letting the application fall back to a stale value rather than failing loudly when the input is missing.

**Why this matters:** External-resource names are contracts between systems. The application asks for a thing by name, the deployment provides a thing by that name, and a third place — an access policy, a discovery entry, an ignore rule — typically also names the thing. The system works only when all of these agree. When the deployment renames the resource and forgets to update the application's input, the right outcome is for the application to fail at startup with a clear error pointing at the missing input. A silent default turns that visible failure into a delayed-and-quiet one: the application starts, queries a resource that no longer exists, and surfaces the consequence somewhere downstream — typically logged in a place no one is watching, or only after a partial failure has already leaked.

The rule is about *failure mode*, not mechanism. An application can receive an external-resource identifier via environment variable, command-line flag, configuration-file path, mount-injected file, service-discovery handle, or constructor argument. What matters is that the application crashes immediately and clearly when the input is missing, instead of substituting a baked-in fallback.

This is also a *Verify Assumptions Against the Actual Target* concern: a default value encodes an assumption about how the surrounding system is named. Assumptions baked into source rot independently of the system they describe. Required inputs cannot rot — they have no value to be wrong about.

## Scope

The rule applies wherever the application carries the literal name of a resource that lives outside its own process boundary:

- Names of resources the application reads or writes: configuration objects, queues, topics, tables, files at known paths, distributed-cache keys, secrets
- Identifiers of external systems the application contacts: service hostnames, API endpoints, project or account identifiers, tenant identifiers
- Contract-shaped strings whose value must equal a value used elsewhere in the deployment to function correctly: status-check names, lock keys, advisory-lock identifiers, leader-election keys

## What does **not** belong under this rule

Pure tuning parameters — values that govern the application's own internal behavior and are not duplicated anywhere in the deployment — can carry sensible defaults. Examples: poll intervals, retry counts, cache sizes, log levels, batch sizes, timeouts that govern only the application's own loops. The litmus test is whether the same value also lives somewhere else in the deployment. If yes, the rule applies. If no, a default is fine.

A close relative: values that the application *advertises* to others (a port the application binds to, a listening address) are also acceptable as defaults, because the application is the source of truth and the deployment configures *around* it. The rule cuts the other way: it targets values where the application is the *consumer* of a name authored elsewhere.

## Compliant examples

- ✓ A worker reads its queue name from a required input. Starting without it produces an immediate fatal error; the operator gets a clear message naming the missing input. A rename of the queue in the deployment that misses the input override fails fast in the next rollout, not silently in production.
- ✓ A reporter that posts a status to an external system requires the status-context identifier as an explicit input. A test exists that boots the application with the input unset and asserts the startup fails with a readable error.
- ✓ A daemon takes the path to its configuration file as a CLI flag with no default; running the binary without the flag exits non-zero with usage text. The path is not embedded in the binary even though, in production, only one path is ever used.
- ✓ A service that looks up a tenant identifier reads it from an injected file at a fixed mount point. The mount point itself is the input; if absent, the service refuses to start.

## Non-compliant examples

- ✗ The application's configuration file ships a default for the name of an external resource that matches the production name. A reader of the file later "updates the name" only there, the deployment manifest is not changed, and the application keeps using the old name in production because the default never went away.
- ✗ A client embeds the production database hostname as a fallback "for convenience in development." A production rollout with the env override accidentally unset connects silently to the development host using the same fallback.
- ✗ A reporter has a hardcoded fallback for the status-context name. The deployment is renamed, the source remains, and the reporter posts statuses under the old name — invisible to whoever is watching for the new name.
- ✗ A scheduler uses a constant for the lock key it competes on. Two services intended to share the lock use the same constant by coincidence, not by contract — a rename in one breaks the coordination silently.

## Exceptions

- **Pure internal tuning** (see *Scope* above): the application is the only place the value lives, and a default is appropriate.
- **Self-advertised values**: the application is the authority on the value (its bind port, its module name, its logical identifier), and the rest of the system configures itself around the application.
- **Conventional sentinels**: where the deployment mechanism itself provides a default that is universally understood — e.g., a service-mesh injection that always sets a known environment variable — the default lives in that injection, not in source. The application can rely on the deployment mechanism to provide it; it does not embed the literal.

When in doubt, apply the inversion check: rename the production value alone, leaving the application's source unchanged. If the application keeps working in production after the rename, the source had a fallback that should not exist.

## Sibling enforcement

No automated check today. Empirical verification is the practical sibling: for each external-resource identifier the application reads, run the application without the input and confirm the failure is loud, immediate, and points at the missing input. A startup-mode test that exercises the missing-input path is a reasonable in-suite sibling check; it remains a judgement call which inputs are important enough to merit such a test.

The companion to this policy is [CQP-004](CQP-004-test-fixtures-distinct-from-production.md): tests that exercise the application with explicit external-resource identifiers should pick deliberately fake values, so that a coincidental match between a test fixture and production cannot mask a leaked default.
