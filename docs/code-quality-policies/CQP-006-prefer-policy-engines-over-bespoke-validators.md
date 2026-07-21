# CQP-006: Prefer policy engines over bespoke validators

**Rule:** Express project-specific correctness rules for repository artifacts in the native rule format of an established policy, schema, or test engine: policy files, tests, schemas, or configuration. Local code may prepare inputs and invoke tools, but it must not decide whether an artifact is correct.

**Why this matters:** A custom validator becomes a private validation engine even when it starts small. It grows its own parsing logic, rule vocabulary, failure language, fixture style, and extension pattern, and each of those is one more thing a reviewer must audit and one more place the next rule could land. Per artifact class, the question of where a rule lives and how its correctness is proved should have a single obvious answer; a bespoke engine multiplies the answers.

A script crosses the line from adapter to validation engine when it combines input discovery, parsing, project-specific judgements, custom failure formatting, and the role of default home for future checks. Once that happens the established tool no longer carries the contract: reviewers must audit both the rule and the private engine around it, and future agents inherit a copyable example of the wrong extension point.

## Scope

The rule applies to repository checks over committed or rendered artifacts:

- Kubernetes manifests and rendered GitOps output
- Terraform, Helm, Kustomize, CI, package, and tool configuration
- Generated contract data used by validation tools
- Source files whose correctness an existing linter, schema validator, policy engine, or test runner can express

It applies independently of implementation language. Rewriting a bespoke Python validator in shell, Go, or any other language does not satisfy the rule while the new program still owns the project-specific policy.

## Layer boundary

Validation keeps three responsibilities separate:

- **Preparation:** discover files, render generated artifacts, normalize data, build caches, route inputs, and invoke tools.
- **Tool execution:** run the established validator or test runner that owns the evaluation model.
- **Rules and configuration:** define what is correct, in the tool's own rule format.

Preparation code earns its keep by staying mechanical. It may know which inputs a tool needs and in what form; domain facts that decide pass or fail belong in the rules layer.

## Compliant examples

- ✓ A runner renders Kustomize and Helm output once, passes the combined manifests to Conftest, and Rego policies define the Kubernetes contract.
- ✓ A schema-preparation module downloads or generates schemas, then kubeconform validates resources against those schemas.
- ✓ A Terraform source file is checked by a tool that parses HCL, with the project relationship expressed as policy or a native test.
- ✓ A shell script is verified by executing it through a test harness with a fake external command on `PATH`; the expected behavior lives in the test rather than in a source-text scanner.
- ✓ A tiny adapter fills a gap no existing tool exposes, and it stays limited to the missing mechanical check rather than becoming a home for unrelated domain rules.

## Non-compliant examples

- ✗ A custom program renders YAML, parses the result, checks project-specific Kubernetes semantics, and formats bespoke failure messages when Conftest or another policy engine can express the same rule.
- ✗ A source scanner reads Terraform or YAML as text and asserts project-specific resource relationships with substring or regular-expression checks when a structured parser and a policy or test engine are available.
- ✗ A validator mixes sibling-repository discovery, tool invocation, artifact parsing, domain constants, and correctness assertions in one domain-named command.
- ✗ A new check is added to an existing custom validator because it is nearby, even though a standard tool already owns that class of rule.
- ✗ A bespoke validator is rewritten in another language while preserving the same private parsing, policy, and failure model.

## Exceptions

- **Preparation and orchestration.** A local runner is acceptable when it only discovers, renders, converts, caches, routes, invokes, and reports an output from an established tool.
- **Behavioral targets.** Some claims must be proved by running the real target or a controlled double of it. In that case, use a normal test harness and put the assertion in tests.
- **Runtime controllers.** A component that evaluates live system state and publishes a runtime decision is product logic and sits outside this rule; it should still keep parsing, evaluation, and reporting boundaries clear.
- **Small missing-tool checks.** A narrowly scoped local check can be acceptable when no established tool exposes the invariant. If the check starts acquiring multiple domains, a rule language, or its own fixture style, revisit the design.

## Review heuristic

Ask where the next similar rule would go. A healthy boundary routes it into the rule format of the existing tool; a broken one routes it into more code in the custom validator. What the custom code knows is the second signal: knowledge of inputs and invocation is preparation, while knowledge of domain facts that decide pass or fail means a rule has leaked out of its layer.

## Sibling enforcement

No automated check today. This policy is enforced during review of new validators, pre-commit hooks, CI scripts, and validation tooling changes. When reviewing such a change, name the three layers from *Layer boundary* explicitly; if one custom artifact owns all three, require a design change or a written exception.
