# LL-0019: ArgoCD fasttemplate preserves missing keys as literal text — accidental safety from an unmaintained library

## Summary

ArgoCD's legacy fasttemplate engine (`valyala/fasttemplate`) renders missing template parameters as literal `{{param}}` text rather than empty strings or error values. This makes systems using fasttemplate-based ApplicationSets accidentally fail-closed — invalid literal text is rejected by downstream controllers like ExternalDNS and cert-manager. The behavior is undocumented, untestable, and provided by an unmaintained library.

## What happened

During migration from fasttemplate to Go templates (ADR-011), research into the safety properties of the existing template engine revealed that fail-closed behavior was accidental. ExternalDNS and cert-manager reject `{{branch-prefix}}` as an invalid domain/zone name, which happened to prevent silent misconfiguration. This was treated as a safety property, but it was never deliberately designed as one.

## Root cause

`valyala/fasttemplate` source code in ArgoCD's `applicationset/utils/utils.go` contains:

```go
fmt.Fprintf(w, "{{%s}}", tag)
```

When a tag is not found in the replacement map, the library writes back the original `{{tag}}` text unchanged. This is an implementation choice in the library, not a documented API contract. The library is no longer actively maintained.

## Resolution

Migrate to Go templates with `missingkey=error`. This option causes the ApplicationSet controller to error explicitly when any referenced annotation is absent — fail-closed by design, not by accident. The safety property becomes explicit, testable, and independent of any third-party library behavior.

## How to detect

If relying on fasttemplate-based ApplicationSets for implicit safety:

1. Check whether any template parameter could be absent (e.g., missing cluster annotations).
2. Verify that the literal `{{param}}` text would actually be rejected by the downstream system — not all consumers treat it as invalid.
3. Consider whether Go template migration with `missingkey=error` would convert the accidental property into an explicit one.
