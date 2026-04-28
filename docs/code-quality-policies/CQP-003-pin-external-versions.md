# CQP-003: Pin external dependencies to exact versions

**Rule:** Every external dependency is pinned to an exact patch version. Exact equality, not ranges, lower-bounds, or compatible-release operators.

**Why this matters:** Unpinned or range-pinned dependencies make builds non-reproducible and upgrades invisible. A range pin lets a transient resolution change behavior between two builds with no commit in between, and the discrepancy surfaces only when something breaks. Exact pins make every upgrade a diff that is reviewable like any other change.

## Scope

The rule applies to every external-source dependency, regardless of ecosystem:

- Python (`pyproject.toml`, `requirements.txt`, `uv` lockfiles)
- Helm charts (`Chart.yaml`, image references in `values.yaml`)
- Container images (Dockerfile `FROM`, k8s manifests, `image:` fields)
- Terraform providers and modules
- GitHub Actions (SHA pins, not tag pins; tags are mutable refs)
- Pre-commit hook revisions (`.pre-commit-config.yaml` `rev:`)

## Compliant examples

- ✓ `requests = "==2.31.0"` (Python, exact equality)
- ✓ `image: registry.k8s.io/cert-manager/cert-manager-controller:v1.16.2@sha256:abc...` (digest pin alongside the human-readable tag)
- ✓ `uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.1.1` (SHA pin with tag comment for human readability)
- ✓ A pre-commit hook entry with `rev: v0.6.4` (exact tag, not a branch)

## Non-compliant examples

- ✗ `requests = ">=2.31.0"` or `"~=2.31"` (range or compatible-release operator)
- ✗ `image: nginx:latest` (floating tag)
- ✗ `uses: actions/checkout@v4` (tag without SHA; tag is mutable)
- ✗ `rev: main` in a pre-commit config (branch reference)

## Exceptions

(none yet — exceptions documented here with date and reason)

## Sibling enforcement

Mostly statically enforceable per ecosystem. Defaults in this project:

- Python: `uv` lockfile pins transitives; `pyproject.toml` pins direct dependencies.
- GitHub Actions: `zizmor` flags non-SHA `uses:` references.
- Helm and k8s images: image references can be enforced via a `kyverno` policy or a CI check that compares to digests.
- Pre-commit hook revisions: `prek` does not enforce `rev:` exactness; reviewable manually or via a small lint rule.

When a sibling mechanism for a particular ecosystem is missing, this policy is the canonical statement and the rule is checked at review time. Adding a static check retires the corresponding review burden; the entry can then move to ecosystem-specific configuration with the rationale captured in the commit message.
