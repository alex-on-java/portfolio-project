# LL-0073: Prefix-Scoped `secretAccessor` IAM Condition Grants Every Secret When the Prefix Is Empty

## Summary

A GCP IAM condition of the form `resource.name.startsWith(prefix)` matches **every** resource when `prefix` is the empty string: the CEL `startsWith("")` is identically true. An empty (or otherwise altered) prefix variable therefore renders a syntactically valid IAM condition that matches every secret in the project. It silently collapses a least-privilege `roles/secretmanager.secretAccessor` grant into a project-wide one. `terraform validate`, `plan`, and `apply` all succeed and flag nothing. Pinning the prefix to its expected literal with a Terraform variable `validation` block turns the silent widening into a plan-time error.

## What Happened

The ESO read identity in `portfolio-project-infra/infra/iam/main.tf` grants `roles/secretmanager.secretAccessor` to the `external-secrets` GSA, conditioned on the secret resource name starting with the project prefix:

```hcl
condition {
  title      = "prefix-scoped-secret-access"
  expression = "resource.name.startsWith(\"projects/${data.google_project.current.number}/secrets/${var.secret_prefix}\")"
}
```

The discriminating substring comes from `var.secret_prefix`. With no constraint on that variable, an empty or altered override would still render a well-formed condition. Instead of `.../secrets/portfolio-project-`, the expression would end at `.../secrets/`, which every secret resource name in the project starts with. The grant would degrade from least-privilege to project-wide, defeating the boundary the condition exists to enforce, and nothing in the Terraform workflow would object.

## Root Cause

CEL evaluates `startsWith(name, "")` as `true` for every `name`: every string starts with the empty string. Because the prefix is interpolated into the expression string, an empty value produces a tautological condition that no longer restricts anything.

IAM conditions are evaluated for satisfaction, not inspected for usefulness. A condition that is always true is perfectly valid, and Terraform has no opinion on whether a condition is meaningfully restrictive. Such a grant therefore widens with zero signal in `plan` or `apply`. The dangerous property is the direction of the failure: an unconstrained `startsWith`/`endsWith`/`matches` argument fails **open**, granting broader access rather than narrower.

## Resolution

Constrain the variable so an empty or unexpected value cannot render a tautological condition (`portfolio-project-infra/infra/iam/variables.tf`):

```hcl
variable "secret_prefix" {
  validation {
    condition     = var.secret_prefix == "portfolio-project-"
    error_message = "secret_prefix must be exactly \"portfolio-project-\"; a blank or altered prefix collapses the IAM condition to a project-wide Secret Manager grant."
  }
}
```

Verified: `terraform validate` succeeds; `terraform plan` reports no changes (the block is config-only and the default already satisfies it); `secret_prefix=""` now fails validation at plan time.

## How to Detect

- Inspect the rendered IAM condition expression, not just the variable: an empty or suspiciously short string after the `.../secrets/` segment means `startsWith` matches broadly.
- Audit any CEL `startsWith`/`endsWith`/`matches` whose argument is interpolated from a variable that has no `validation` constraint; each is a fail-open candidate.
- On a live binding, read the condition expression (`gcloud projects get-iam-policy` with the condition shown) and confirm the discriminating substring is present and non-empty.

## Adoption Rule

When an IAM (or any CEL) condition derives its discriminating substring from a variable, constrain that variable so an empty or unexpected value cannot render a tautological, fail-open condition. Pin the value with a Terraform `validation` block (or equivalent) so the widening surfaces at plan time rather than in a later access audit. A scoped grant whose scope depends on an unvalidated input is only as least-privilege as that input is guaranteed.

## Related Records

ADR-033 records the prefix-scoped ESO read identity this validation protects.
