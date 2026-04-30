# CQP-004: Test fixtures must use values distinct from production

**Rule:** A test fixture's literal values — names, identifiers, hostnames, paths, addresses, serialized payloads, magic numbers — must be chosen so that they cannot equal any value used in production. When a fixture's value coincides with the production value, a test that should be exercising parameter-passing through the system can pass for the wrong reason: the production value reached the assertion via some side channel rather than via the test inputs.

**Why this matters:** A passing test is evidence of "produces the expected output for the given inputs" — nothing more. If the test input equals the production value, you can no longer tell whether the test machinery actually drove that value through the code path under test, or whether some implicit lookup found the same value via a side channel: an environment default, a global config, a cache, a hardcoded fallback constant, a service-discovery hit. The coincidence makes the leak invisible. Tests are an inversion check on production behavior; they cannot be inversions if they share values with production.

This is also a matter of *Explicit Over Implicit*. A deliberately fake value in a fixture announces "this test is about plumbing, not contract." A production-matching value announces nothing, and the next reader cannot tell whether the choice was deliberate or coincidental.

## Scope

The rule applies wherever a test asserts on, seeds, or constructs from a literal value, and that value has a production analog anywhere in the system:

- Resource names, namespace names, table names, queue names, topic names
- Hostnames, URLs, port numbers, service identifiers
- File paths, mount points, configuration-file locations
- Repository slugs, organisation names, project identifiers
- Tuning numbers (intervals, thresholds, timeouts) when production uses a specific number
- Serialized payloads embedded in tests where a field value has a production meaning
- Credentials, tokens, secrets — these should already be fake; the rule makes the requirement explicit and reviewable

The rule applies independently of testing layer (unit, integration, contract, end-to-end) and of how the fixture is delivered (inline literal, fixture function, configuration file, factory).

## The inversion check

The practical heuristic for whether a literal needs to change: imagine renaming the production value alone, without touching the test. There are exactly two acceptable outcomes:

1. **The test fails.** The test exists to verify the production string itself; the literal *is* the contract under test. The fixture is correct as-is and falls under the *Exceptions* below.
2. **The test is unaffected.** The literal was incidental to the test's purpose, and the rename should not have touched it. The fixture is fine if and only if the value was already deliberately fake.

The unacceptable outcome is the third: the test still passes, with the same fixture value, because the rename and the fixture happen to agree by coincidence. That is the leak this policy is designed to prevent.

## Compliant examples

- ✓ A test for a queue consumer seeds the test queue as `test-orders-queue` while the production queue is `customer-orders`. The fact that the consumer reads from whatever queue name is passed is exercised by the test; the production name is irrelevant to the assertion.
- ✓ A database integration test creates a schema named `t_<uuid>` per test run; the production schema name is `prod_orders`. A rename of the production schema does not affect the test in any way.
- ✓ A handler test asserts on a hostname `https://test.example.invalid` (RFC 2606 reserved domain) rather than the production hostname. The handler's URL-construction logic is what the test verifies, not the specific hostname.
- ✓ A polling-loop test sets the interval to `0.001` seconds, far from the production interval. The test verifies the loop's stop condition, not the interval value.
- ✓ A configuration-loading test uses a fake project identifier `test-project-id-1`. Production uses a real GCP/AWS/Azure project identifier; the loader's behavior is independent of which.

## Non-compliant examples

- ✗ An integration test seeds a fixture with the exact production resource name. The reader-under-test queries by that same name. The test passes today because the fixture and the reader agree, *and* it would still pass if the reader's name parameter were silently sourced from a production default — the test cannot distinguish the two.
- ✗ A hostname assertion in an HTTP-client test that uses the production API hostname. If the client's URL builder were silently falling back to the production hostname instead of using the configured one, the test would still pass.
- ✗ A test for a config-file loader that uses the same numeric thresholds as production. If the loader silently ignored its input and returned built-in production defaults, the assertion would still hold.
- ✗ A serialized event payload in a test where one field carries the production correlation-ID format. A bug that drops the correlation-ID and substitutes a default would not be caught.

## Exceptions

- **Contract assertions.** A test that exists to pin the production string is allowed — and required — to use it. Examples: a test asserting that an outbound HTTP request is sent with the exact public API contract field, or that a status-check posted to a third-party system uses the exact context name a downstream rule depends on. Such tests are the canonical home for the production literal; mark them with a name or comment that signals "this test pins the production value" so the next reader does not treat them as an oversight to clean up.
- **Incidental literals in pure-data tests.** Where the assertion is about shape (round-trip, schema validity, parser correctness) and the literal value has no semantic role, the value can be anything readable. A coincidence with production here is harmless because no production code path is being exercised.
- **Universally-fake values that look like production.** Some "production-shaped" literals are conventionally understood as fake and reserved for documentation and tests: RFC 2606 example domains (`example.com`, `*.example.invalid`), RFC 5737 documentation IP ranges, the `test-` prefix conventions of major SDKs. Using these is *not* a violation even though they look real.

## Sibling enforcement

No automated check today. Mechanical detection would require a registry of "production literals," which would itself need maintenance and would drift faster than the test suite. The check is performed at review time using the inversion heuristic above.

A practical aid when authoring or auditing a test: pick one production literal touched by the test's domain (a real resource name, a real hostname) and grep for it across the test directory. Every hit is a candidate violation — either an exception above, or a leak.
