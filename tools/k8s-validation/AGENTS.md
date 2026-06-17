# tools/k8s-validation

This directory is a validation engine layer. Its Python code may discover inputs,
render manifests, prepare generic data, cache tool inputs, and invoke upstream
validators such as Conftest, kubeconform, and Kyverno.

Project correctness rules do not belong in domain-specific Python validators.
Put those rules in the tool-native surface instead: Rego policies and tests for
Conftest, policy manifests for Kyverno, schema configuration for kubeconform, or
ordinary tests when behavior must be executed.

Before adding code here, decide which layer it serves:

- Preparation code may collect, normalize, render, route, or invoke.
- Tool configuration may select parsers, schema locations, policies, and data.
- Rules and assertions belong in policy, test, or configuration artifacts.

Do not add a new `*_validator.py` that parses Kubernetes resources and encodes a
specific project contract. If a contract can be expressed by an established
policy, schema, or test engine, extend that engine instead.
