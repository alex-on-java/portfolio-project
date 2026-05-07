# Code Design Principles

Design choices that shape the code itself, distinct from the agent-mindset guidance in WORKING_PRINCIPLES.md and the tactical commit-time rules in code-quality-policies/. These are heuristics to weigh during design, where two competing approaches both satisfy every existing policy and only judgment can settle the choice. Each principle states a default; deviation is allowed when the situation justifies it, not when it merely saves keystrokes.


## Validate at the Edge, Trust Within
External inputs cross the boundary exactly once and emerge as well-formed domain values. The category of "external" is open: configuration, environment, API responses, observed state, files, message payloads, anything the application does not itself produce. The list is illustrative, not closed; the rule is the same shape regardless of where the input came from. Code past the boundary does not re-validate what the boundary already guaranteed.

*Why this matters*: scattered validation is invisible duplication. Agents add "one more check, just to be safe," and over time the boundary's contract erodes into "everywhere validates everything a little." A single sharp edge keeps the trust topology legible: outside the edge, anything is suspect; inside, types mean what they say.


## The Edge Assembles a Complete Setup
The same boundary that validates inputs is also the place where the interior's initial state is assembled. The interior never re-derives, defaults, or back-fills what the boundary could have provided. Whether the codebase calls this layer "boot," "main," "entry-point," "container init," or "root component" is incidental; the responsibility is the same shape.

*Why this matters*: when the interior does first-time discovery for itself, the boundary's job becomes ambiguous and the interior grows defensive scaffolding for "what if this is not ready yet." A clean handoff makes the interior's preconditions explicit: if it ran at all, it has what it needs. Errors then live where the operator has the most context to act on them, rather than surfacing in the middle of operations the interior was supposed to be running cleanly.


## Immutable Data Structures by Default
Data structures are immutable by default, regardless of whether they represent domain values, configuration, intermediate results, or transport payloads. The carveout is narrow and load-bearing: deviate only when immutability would meaningfully harm the clarity of the code that uses the structure, not because mutation saves a few keystrokes. Convenience is not a sufficient justification.

*Why this matters*: mutability silently couples otherwise-independent code paths. When two consumers share a value, a mutation by one leaks into the other's view, and the bug surfaces under conditions no test exercised. Immutability makes data flow visible: copies are explicit, equality is structural, and "did this change?" becomes answerable without a runtime audit.


## Domain and Transport Stay Separate
Code that models the domain (entities, rules, identity, valid states) does not know how that domain is fetched, transported, or persisted. Code that handles transport, parsing, or external APIs does not know about the domain's rules. The two layers are written as if they have never heard of each other.

*Why this matters*: this is not really about being able to swap an adapter, although that is the textbook framing. The deeper cost of coupling the two is that external concerns leak into domain reasoning (a serialization quirk shapes how the domain thinks about a value), and domain concerns leak into transport (a business rule embeds itself in a parser). Both directions corrupt the layer that absorbed the foreign concept. Changes that should have been local then cascade across the system, because the layers no longer have independent lives.


## Absent Dependencies Fail Loudly
A dependency the system needs to function correctly produces an explicit, immediate failure when it is missing or misconfigured. Silent fallbacks (null objects, default constructors, no-op passthroughs, sensible-looking zero values) turn missing setup into invisible degradation, where the system reports success for work it did not actually do.

*Why this matters*: silent fallbacks shift the failure mode from "loud at startup" to "silent forever." The operator finds out only when the consequence has already landed, in a context with far less debugging signal than the place where the dependency was supposed to be wired. Loud failure at the earliest possible moment is the cheapest, most reliable form of runtime feedback the system can produce, and the cost of a startup-time error is almost always lower than the cost of a downstream surprise.


## Data Structures Mirror the Domain They Model
A data structure encodes a claim about the world: which entities are distinct, which are the same, which can change, which cannot. When the structure is narrower than the domain (fewer dimensions of identity, fewer states, fewer relationships), the gap is invisible until reality expands into it.

*Why this matters*: code reviews catch logic errors; they rarely catch expressivity errors, because the missing dimension never produces a failing test on the data the developer had in front of them. The bug surfaces only when the domain grows in a direction the structure cannot represent, in production, on data the original author never saw. Keeping structure isomorphic to domain costs almost nothing up front and removes an entire class of "it worked locally" failures.


## Distinct States, Distinct Representations
A single value carries one meaning, not several. When the same representation (an absence, an empty value, a default, a zero) is reused to encode multiple distinct states, such as "not yet computed," "computed and intentionally empty," and "computation failed," the consumer has no structural way to tell them apart. Disambiguation drifts into convention and out-of-band context, neither of which the type system can enforce.

*Why this matters*: overloaded values force every reader to remember which interpretation applies in which call site, and that rule lives nowhere checkable. Eventually two readers disagree, or a path that should have surfaced a failure looks indistinguishable from one that completed successfully with no result. Distinct states deserve distinct representations, even when most of them are inhabited rarely. The cost of carrying an explicit shape is small; the cost of a misread overloaded value is silent and load-bearing.
