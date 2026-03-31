# Plan Sections: Rationale

This document explains the reasoning behind each section of the plan-creation skill.
The SKILL.md file is intentionally concise — it tells the agent *what* to do.
This file explains *why* each instruction exists.

---

## The Self-Containment Constraint

Plans in this project are consumed by implementing agents that have no memory of the conversation that produced them. The plan is the sole communication channel between the planning and implementing phases. If it is incomplete, the implementing agent either asks questions (breaking the workflow, requiring human intervention) or guesses (introducing errors silently). Every section instruction flows from this constraint.

## Timing: "After the pre-plan alignment phase"

The skill is loaded *after* alignment with the user is complete — not before. Loading a template too early leads agents to start filling sections before they understand the problem, producing plans that look structured but contain hollow content. The alignment phase is for understanding; the skill is for writing.

## Problem Statement

"Ground this in specifics, not abstractions" guards against statements like "the current solution is suboptimal" — authoritative-sounding but empty. A zero-context reader should be able to independently verify the problem exists from the description alone.

## Intent

Intent is deliberately separated from motivation (why) and chosen approach (how). These are three distinct questions that agents tend to collapse into a single muddled section. Intent is the directional statement — "add X" or "replace Y with Z" — without justification or implementation details. It bridges the problem to the approach.

## Motivation

This is the most heavily guarded section in the skill, for good reason.

**Why it must be deep:** The plan is not disposable. It serves as a historical record — readable weeks or months later to understand why a decision was made. Shallow motivation ("because we need it") loses this value entirely.

**Why it must come from the user:** The agent cannot be the source of "why." Only the human knows why the work matters. The agent can help articulate it, but the raw material must come from the user.

**Why fabrication is worse than omission:** A blank motivation section is honest — it says "this was not captured." A fabricated one actively misleads. Someone reading the plan later would believe a rationale that was never real. It creates a false historical record — the most dangerous kind of documentation, because it carries implicit authority. This instruction exists because language models produce plausible-sounding motivation with ease, and distinguishing fabricated rationale from genuine user intent is nearly impossible after the fact.

**"Why now and not later":** Most tasks could theoretically wait. Forcing an explicit answer either reveals genuine urgency or exposes that the priority has not been thought through. Either outcome is valuable.

## Context

"Do not rephrase the problem" fights the tendency to pad this section by restating the problem in different words and calling it "context."

"Is there really nothing to add, or is the information simply unknown?" draws a crucial distinction. Concluding "nothing to add" after genuine exploration is legitimate. Defaulting to silence without looking is laziness disguised as brevity. These two outcomes look identical in the plan but have very different implications.

"Context often lies outside the codebase" is a reminder that relevant information may live in external documentation, domain knowledge, compliance requirements, or the user's broader strategy — not just in the code.

## Success Criteria

Binary pass/fail criteria. "Improved" and "better" are not testable — they create an illusion of rigor without enabling actual verification. Each criterion should be checkable by an agent or a human without subjective judgment.

## Chosen Approach

"How this specific approach was arrived at" matters as much as the approach itself. An implementing agent that understands the reasoning can make better judgment calls when encountering ambiguity. Without the reasoning trail, it can only follow the letter of the plan, not its spirit.

## Alternatives Considered

This section serves two purposes: preventing future agents from re-exploring dead ends, and enforcing intellectual honesty about the planning process.

The emphasis on "considered" as the key word addresses a specific failure mode: agents listing alternatives they never actually evaluated. Post-hoc rationalization — inventing three neat rejection reasons to make the plan look thorough — is easy to produce and hard to detect. If alternatives were not genuinely surfaced and weighed, listing them is fiction.

The instruction to reflect when no alternatives were considered is the most nuanced part. Realizing that no alternatives were explored is itself informative: perhaps the first approach is obviously correct, or perhaps tunnel vision occurred. The section becomes a forcing function for self-examination, not just a historical record. If after reflection there are genuinely no alternatives, stating this clearly is honest and useful.

## Scope

The "why" for exclusions prevents future agents from adding back things that were deliberately left out. Without the rationale, an exclusion looks like an oversight rather than a decision — and someone will eventually "fix" it.

## Conducted Research and Experiments

This is provenance tracking. Results feed into Motivation, Context, and Chosen Approach — but a reader should be able to trace *where* those conclusions came from. "We chose approach X" is a claim; "because experiment Y showed Z (see path/to/poc)" is a verifiable claim. The difference matters when revisiting decisions.

## Implementation Steps

"Do not include verbatim code" reflects trust in the implementing agent's competence. The plan is for communicating *thinking* — constraints, sequencing, non-obvious decisions — not for copy-paste. Specifying how a for-loop should look wastes plan space and undermines the implementing agent's judgment.

"Distinguish valuable input from platitudes" fights a specific failure mode: padding implementation steps with generic advice like "follow best practices" or "ensure proper error handling." These sound helpful but communicate nothing actionable. The test is: would a competent agent, reading the codebase, arrive at this detail on their own? If yes, it does not belong in the plan. If no — because the detail is non-obvious, counterintuitive, or depends on context not visible in the code — it must be included, with an explanation of why it matters.

## Skills to Use

A routing table ensuring the implementing agent does not miss workflow steps that exist as separate skills. Without this, agents tend to skip verification, drift checking, and git hygiene — not out of malice, but because they do not know these skills exist.

## Format

Plans are reference documents, not essays. The implementing agent needs to find information quickly — scanning headers and bullets — not read linearly from start to finish.

## Baseline Commit

Anchors the plan to a specific codebase state. Between planning and implementation, the code may change. The implementing agent needs to know what snapshot the plan was written against so it can detect drift — which is exactly what `git-vs-plan-drift-check` does as the first implementation step.
