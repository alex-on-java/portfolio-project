# LL-0020: Kyverno CRD enforces maxLength: 63 on rule names — exceeding it silently loads zero rules

## Summary

When a Kyverno ClusterPolicy rule name exceeds 63 characters, `kyverno apply` silently loads 0 rules from the policy file. There is no error message, no stderr output, and no indication that the policy was rejected. The downstream symptom is a `JSONDecodeError` when the test harness tries to parse empty stdout as JSON.

## What happened

A new Kyverno rule named `require-ephemeral-storage-limit-equals-request-analysis-template` (64 characters) was added to the ClusterPolicy. Running `kyverno apply` against rendered manifests reported "Applying 0 policy rule(s)" — as if the policy file contained no rules at all. The test harness crashed with `JSONDecodeError` on empty stdout, which looked like a test infrastructure problem rather than a policy authoring error.

## Root cause

The Kyverno CRD defines `maxLength: 63` on the `spec.rules[].name` field, matching the DNS label length constraint from RFC 1035. When a rule name exceeds this limit, the YAML is valid but the CRD validation fails during deserialization. The `kyverno apply` CLI does not surface CRD validation errors — it simply skips the policy and proceeds with an empty rule set.

## Resolution

Shortened the rule name from 64 to 46 characters: `ephemeral-storage-limit-eq-request-analysis` (from `require-ephemeral-storage-limit-equals-request-analysis-template`). Established a convention of keeping rule names well under 63 characters.

## How to detect

If `kyverno apply` reports "Applying 0 policy rule(s)" when the policy file clearly contains rules, check the character length of every rule name. Any name at or above 63 characters will cause this silent failure. The error is not logged — the only signal is the zero-rule count in the summary output.
