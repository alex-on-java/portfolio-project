# CQP-006: Prefer policy engines over bespoke validators

**Rule:** Do not build a custom validation program for artifact semantics when an
established policy, schema, or test engine can own the rule. Local code may
prepare inputs and invoke tools, but project-specific correctness belongs in the
tool-native rule surface: policy files, tests, schemas, or configuration.

**Why this matters:** A custom validator becomes a private validation engine even
when it starts small. It usually grows its own parsing logic, rule vocabulary,
failure language, fixture style, and extension pattern. The next change then has
to answer a question that should already be obvious: should this rule be Python,
Bash, JavaScript, Java, Rego, schema configuration, or a test? That uncertainty
is expensive because each answer creates a different place to look and a
different way to prove correctness.

The harmful shape is the combination, not the implementation language. A script
that discovers inputs, parses them, makes project-specific judgements, formats
custom failures, and becomes the place future checks are added has crossed from
adapter into validation engine. Once that happens, the normal policy or test
tool no longer carries the contract. Reviewers have to audit both the rule and
the private engine around it, and future agents get a copyable example of the
wrong extension point.

## Scope

The rule applies to repository checks over committed or rendered artifacts:

- Kubernetes manifests and rendered GitOps output
- Terraform, Helm, Kustomize, CI, package, and tool configuration
- Generated contract data used by validation tools
- Source files whose correctness can be expressed with an existing linter,
  schema validator, policy engine, or test runner

It applies independently of language. Replacing a bespoke Python validator with
a bespoke shell, JavaScript, Java, or Go validator does not satisfy the rule if
the new program still owns the project-specific policy.

## Layer Boundary

Validation should keep three responsibilities separate:

- **Preparation:** discover files, render generated artifacts, normalize data,
  build caches, route inputs, and invoke tools.
- **Tool execution:** run the established validator or test runner that owns the
  evaluation model.
- **Rules and configuration:** define what is correct in the tool-native surface.

Preparation code is allowed when it stays boring. It can answer "which inputs
does this tool need?" It must not quietly answer "is this project artifact
correct?"

## Compliant Examples

- ✓ A runner renders Kustomize and Helm output once, passes the combined
  manifests to Conftest, and Rego policies define the Kubernetes contract.
- ✓ A schema-preparation module downloads or generates schemas, then kubeconform
  validates resources against those schemas.
- ✓ A Terraform source file is checked by a tool that parses HCL, with the
  project relationship expressed as policy or a native test.
- ✓ A shell script is verified by executing it through a test harness
  with a fake external command on `PATH`; the expected behavior lives in the
  test, not in a source-text scanner.
- ✓ A tiny adapter fills a gap no existing tool exposes, and it stays limited to
  the missing mechanical check rather than becoming a home for unrelated domain
  rules.

## Non-compliant Examples

- ✗ A custom program renders YAML, parses the result, checks project-specific
  Kubernetes semantics, and formats bespoke failure messages when Conftest or
  another policy engine can express the same rule.
- ✗ A source scanner reads Terraform or YAML as text and asserts project-specific
  resource relationships with substring or regular-expression checks when a
  structured parser and policy/test surface are available.
- ✗ A validator mixes sibling-repository discovery, tool invocation, artifact
  parsing, domain constants, and correctness assertions in one domain-named
  command.
- ✗ A new check is added to an existing custom validator because it is nearby,
  even though a standard tool already owns that class of rule.
- ✗ A bespoke validator is rewritten in another language while preserving the
  same private parsing, policy, and failure model.

## Exceptions

- **Preparation and orchestration.** A local runner is acceptable when it only
  discovers, renders, converts, caches, routes, invokes, and reports an
  output from an established tool.
- **Behavioral targets.** Some claims must be proved by running the real target
  or a controlled double of it. In that case, use a normal test harness and put
  the assertion in tests.
- **Runtime controllers.** A component that evaluates live system state and
  publishes a runtime decision is product logic, not a static artifact
  validator. It should still keep parsing, evaluation, and reporting boundaries
  clear.
- **Small missing-tool checks.** A narrowly scoped local check can be acceptable
  when no established tool exposes the invariant. If the check starts acquiring
  multiple domains, a rule language, or its own fixture style, revisit the
  design.

## Review Heuristic

Ask where the next similar rule would go. If the answer is "add more code to
this custom validator," the boundary is probably wrong. If the answer is "add a
policy, schema, config entry, or test for the existing tool," the boundary is
probably healthy.

Also ask what the custom code knows. Knowing how to prepare input is fine.
Knowing domain facts that decide pass or fail is the signal to move the rule
into a policy, schema, configuration, or test surface.

## Sibling Enforcement

No automated check today. This policy is enforced during review of new
validators, pre-commit hooks, CI scripts, and validation tooling changes.

When reviewing such a change, name the three layers explicitly: preparation,
tool execution, and rules. If one custom artifact owns all three, require a
design change or a written exception.
