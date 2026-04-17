# LL-0025: Silent `continue` in config extraction masks the root cause of misconfigurations

## Summary

Config-extraction loops that silently `continue` past unknown items (`if chart not in known: continue`) hide user errors: a typo in the config file produces no local diagnostic, and the failure surfaces far downstream as a cryptic coverage-gap or missing-resource error with no hint of the original cause. Raising `ValueError` with a precise diagnostic at the extraction site surfaces the typo at parse time.

## What happened

A typo in `settings.yaml`'s `from_charts[].chart` field (a chart name that did not match any configured chart) was silently skipped by an early `continue` branch in `extract_from_charts()` in `tools/k8s-validation/src/k8s_validator/schemas.py`. The failure appeared later as a generic "CRD schema coverage gap" from the `coverage_gate` pytest fixture, with no mention of the chart name responsible. Debugging walked backwards through the validator, the schema generator, and the cache layout before the typo was located at the original config site.

## Root cause

`continue` is a **permissive** default — it trades diagnostic clarity for execution robustness. Inside a config-extraction loop, that trade is inverted: the caller has *already* expressed intent to process this item; silently skipping it is precisely the kind of behaviour a user expects the program *not* to do on their behalf. The cost of the skip is paid by whoever has to unpick the downstream failure, not by the code that skipped.

## Resolution

Replaced the silent `continue` with an explicit raise that surfaces the offending config item and the set of known values:

```python
if chart not in known_charts:
    raise ValueError(
        f"unknown chart {chart!r} in from_charts; "
        f"known charts: {sorted(known_charts)}"
    )
```

The typo is now caught at config parse time with a message naming both the offending item and the valid alternatives.

## How to detect

Signs a silent `continue` is hiding a root cause:

- A config-driven pipeline fails downstream without naming the config item responsible.
- The downstream error message references internal program state (cache coverage, resource counts) rather than user input.
- Running with one known-good config and one known-bad config produces structurally identical downstream errors.

When auditing config-extraction code for this class of bug, search for `continue` inside loops that iterate over user-supplied lists; replace permissive skips with explicit raises whose messages name the offending field and the valid set.
