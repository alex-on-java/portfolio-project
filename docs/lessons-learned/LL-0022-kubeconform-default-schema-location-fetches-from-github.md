# LL-0022: kubeconform default schema location downloads schemas from GitHub on every run

## Summary

kubeconform's `default` schema location is not a local built-in set of schemas. It is a URL template pointing to `yannh/kubernetes-json-schema` on GitHub, causing kubeconform to download approximately 243 schema files over the network on every invocation. This makes validation non-deterministic (dependent on network availability) and slow for pre-commit hooks.

## What happened

The validation engine initially used kubeconform's `default` schema location alongside custom CRD schema paths. Pre-commit hook runs were slow and occasionally failed on network timeouts. Investigation revealed that `default` translates to an HTTPS URL template that fetches schemas from GitHub for every K8s builtin GVK encountered in the input.

## Root cause

kubeconform treats `default` as a shorthand for `https://raw.githubusercontent.com/yannh/kubernetes-json-schema/master/{{.NormalizedKubernetesVersion}}-standalone{{.StrictSuffix}}/{{.ResourceKind}}{{.KindSuffix}}.json`. This is the documented behavior, but the word "default" implies a bundled or cached resource to most users. The engine's offline-after-initial-setup requirement (fast, deterministic pre-commit hooks with no network dependency after first run) is incompatible with this behavior.

## Resolution

Replaced the `default` schema location with a targeted download pipeline: the engine identifies the ~16 builtin K8s GVKs actually present in rendered manifests, downloads only those schema files once to `.cache/k8s-schemas/v{version}-standalone-strict/`, and points kubeconform at the local directory. Subsequent runs complete with zero network calls.

## How to detect

If kubeconform runs are slow or fail intermittently with network errors, check whether the schema locations include `default`. Replace with explicit local paths to downloaded schemas for offline operation.
