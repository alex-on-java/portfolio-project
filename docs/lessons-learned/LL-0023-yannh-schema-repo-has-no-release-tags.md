# LL-0023: `yannh/kubernetes-json-schema` publishes no release tags — SHA pin is the only stable reference

## Summary

The schema repository that feeds the K8s manifest validation engine, `yannh/kubernetes-json-schema`, does not publish Git tags or GitHub releases. Its `master` branch is the only published reference and is regenerated daily by an automated workflow. Any pinning scheme other than a commit SHA produces non-reproducible schema downloads.

## What happened

The schema-download pipeline in `tools/k8s-validation/src/k8s_validator/schemas.py` started out referencing `yannh/kubernetes-json-schema@master`. Two consecutive local runs produced different schema sets without any local change, breaking the "offline after initial setup" invariant — fresh downloads kept appearing because `master` had moved.

## Root cause

`yannh/kubernetes-json-schema` is regenerated from upstream Kubernetes release schemas by a scheduled GitHub Actions workflow. The repository carries no Git tags, no GitHub releases, and no archival branches — every reference other than a commit SHA is mutable and evolves daily. Common dependency-pinning habits (tag, release, major-version branch) silently fail against this shape.

## Resolution

Pinned `schemas.k8s_schema_repo_url` in `tools/k8s-validation/settings.yaml` to a specific commit SHA (`50b79917c7f9c60d528e5ba6d113aa845a4b6fbf`). Any future upgrade is a conscious SHA bump, auditable in git history. Dependabot and similar tools do not cover this kind of non-versioned reference — the bump cadence must be human-driven.

## How to detect

Signs that an external reference is mutable and needs SHA pinning:

- Two runs of a download pipeline produce different byte-content without any local change to the input configuration.
- `git ls-remote --tags <url>` returns an empty list, and the GitHub Releases page is empty.
- The project README or workflow shows a scheduled job that rewrites the default branch.

Before pinning to a tag or branch, run `git ls-remote --tags <url>` against the upstream repository; if no tags exist, the only stable pin is a commit SHA.
