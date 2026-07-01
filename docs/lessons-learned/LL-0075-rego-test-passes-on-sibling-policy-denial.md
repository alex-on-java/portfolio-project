# LL-0075: Files Sharing a Rego Package Share `deny`, `data`, and Test Rules

## Summary

Conftest and OPA load every file in the same Rego package into one logical package. In a package such as `rendered_sources`, helper rules, `deny` rules, test rules, and `data` references from one policy file can affect tests written for another file. A test can therefore pass because a sibling policy denied the input, fail because sibling data activated a different rule, or get collected as an unintended test because a fixture name starts with `test_`.

LL-0045 covers the sibling-package crash mode, where the wrong input shape causes a type error. This lesson covers the quieter test-isolation mode: evaluation succeeds, but the assertion may not prove the policy it claims to prove.

## What Happened

The rendered Conftest migration put more than one policy under the same rendered package. Rendered image policy and rendered secrets policy share `package rendered_sources`, and Conftest verifies all of their tests in one policy load.

This shape exposed two practical hazards while the policy set was being assembled. One broad negative assertion, such as `count(deny) > 0`, could be satisfied by any sibling rule in the same package rather than the rule under test. A fixture or helper beginning with `test_` could also be collected by Conftest as a test rule rather than remain inert test data.

The rendered policy tests avoid both hazards. Rendered secrets negative tests assert the exact expected denial message. Shared data such as `data.render_contract` and `data.rendered_sources.workload_gsm_contracts` is overridden in the test call when the test needs a synthetic world. Helpers and fixtures use descriptive names that do not begin with `test_`.

## Root Cause

OPA package boundaries are file-independent. Files that declare the same package contribute to the same rule namespace. Conftest then evaluates that package as a whole. There is no automatic isolation by filename, policy topic, or fixture helper name.

The sharing shows up in four places:

- `deny` is shared, so `count(deny) > 0` asks whether any policy denied anything.
- `data` is shared unless the test overrides it with `with data... as ...`.
- Helper names share one namespace across every file in the package.
- Rules whose names begin with `test_` are collected as tests.

None of this is a Conftest defect; the failures come from tests that ask a package-level question when they mean a policy-specific one.

## Resolution

Rendered Rego tests should isolate the policy they claim to prove. Negative tests should assert the exact denial message or another policy-specific signal. Pass tests should use global `count(deny) == 0` only when the fixture also neutralizes sibling data that could activate unrelated policies. When a test injects `data.render_contract` or other shared data, override unrelated sibling data to a neutral value.

Naming needs the same care: use policy-specific helper prefixes when another file could define a similar helper, and reserve the `test_` prefix for intentional test rules.

## How to Detect

Suspect sibling policy contamination when any of these patterns appear:

- A negative Rego test uses only `count(deny) > 0`.
- A pass test uses global `count(deny) == 0` while injecting shared data.
- Adding a new `_test.rego` file creates helper-name conflicts in another file.
- A constant, fixture, or helper starts with `test_`.
- A test starts failing only after an unrelated policy file is added.

An assertion that only proves "some policy in this package denied something" is too broad for a policy-specific contract test.

## Adoption Rule

In a shared Conftest package, every Rego test must isolate the policy it claims to prove. Negative tests should assert the expected denial. Pass tests should neutralize sibling data or scope the observed denial set to the subject under test. Fixtures and helpers should use policy-specific names and should not start with `test_` unless they are intentional test rules.

## Related Records

- [LL-0045](LL-0045-conftest-verify-crashes-with-object-get-type-error.md)
- [ADR-034](../architecture/decision-records/ADR-034-rendered-conftest-validation-architecture.md)
