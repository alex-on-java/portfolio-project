# LL-0074: Tag-Only Validation Reads the Digest Tail as the Image Tag

## Summary

Container image policy must parse an optional digest suffix before it validates the image tag. A reference such as `postgres:18.3@sha256:<digest>` still has tag `18.3`. The digest after `@` is a stronger immutable pin, not part of the tag. If a policy extracts the tag from the whole image string, it can read the digest tail as the tag and reject a valid pinned image.

## What Happened

The image-pinning policy originally treated image references as tag-only strings. It split on `/` and `:`, then validated the last colon-delimited segment as the tag. That worked for simple references such as `nginx:1.27.4`, but it did not model Docker references that carry both a tag and a digest. The gap surfaced when rendered image pinning reused the same helper package on manifests with digest-pinned images.

## Root Cause

The old parser did not split the optional digest before tag validation. A digest also contains a colon:

```text
name:tag@sha256:<64 lowercase hex characters>
```

Splitting the whole reference on `:` therefore loses the boundary between the human-readable tag and the digest algorithm. The policy needs to parse the optional `@sha256:...` suffix first, validate that suffix as a digest, and then validate the left side as a tagged image reference.

## Resolution

The shared container image helper accepts a valid digest pin before ordinary tag validation. It splits on `@`, requires exactly one digest suffix, requires `sha256:<64 lowercase hex characters>`, and requires a tag on the left side.

The Rego tests keep three regression cases:

- `postgres:18.3@sha256:<64 hex>` is accepted.
- `postgres@sha256:<64 hex>` is rejected because it has no tag.
- `postgres:18.3@sha256:not-a-digest` is rejected because the digest is malformed.

Both the raw source adapter and the rendered manifest adapter call the same helper. That keeps source and rendered validation consistent.

## How to Detect

Suspect this bug when a policy failure names an invalid tag for an image that contains both `:<tag>` and `@sha256:<digest>`. The reported tag may resemble the digest tail instead of the human-readable tag.

A regression fixture needs all three cases from the resolution above, because together they separate genuine immutable pins from strings that happen to contain `sha256`.

## Adoption Rule

When checking container image pins, parse the optional digest first. If a valid digest pin is present, validate the digest grammar and require a left-side tag. Do not send the whole reference through tag-only validation.

The broad rule that external dependencies must be pinned stays in force; this lesson adds the parser detail on top of it: `tag@sha256` is a valid stronger image reference, and policy must not reject it as a malformed tag.

## Related Records

- [ADR-034](../architecture/decision-records/ADR-034-rendered-conftest-validation-architecture.md)
