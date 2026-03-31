---
name: plan-creation
description: Every time you are about to write a plan, load this skill. It helps you avoid missing important sections and keeps the plan self-contained. Load this skill after the pre-plan alignment phase has passed.
disable-model-invocation: false
user-invocable: false
---

Create an implementation plan that is fully self-contained — an agent with zero prior context must be able to execute it without asking clarifying questions.

## Plan Sections

Each section serves a specific purpose for zero-context agents:
 - **Problem Statement**: what is wrong, missing, or insufficient. Ground this in specifics, not abstractions.
 - **Intent**: what exactly is going to be done to address the problem, at a high level.
 - **Motivation**: the **deep** WHY. Not a restatement of the task or intent, but the actual motivation: what need or pain drives it, why it matters, why it is being solved now rather than later, and the consequences of postponing it. This section should be deep enough to serve as a historical record of reasoning. This is the most crucial section and it must never be skipped. Motivation always comes from the user — if they have not provided it explicitly, it MUST be elicited from them. Do **not fabricate motivation**; that is worse than omitting the section entirely.
 - **Context**: surrounding context of the problem. Do not rephrase the problem — add meaningful information. If there is genuinely nothing to add, skip this section. But consider carefully: is there really nothing to add, or is the information simply unknown? Context often lies outside the codebase, so go the extra mile to find it.
 - **Success Criteria**: concrete, verifiable conditions that define "done". Each criterion must be testable — no subjective language like "improved" or "better".
 - **Chosen Approach**: what is being done and how this specific approach was arrived at.
 - **Alternatives Considered**: what other approaches were evaluated and why each was rejected. This prevents future agents from re-exploring dead ends. **Important**: "considered" is the key word. If alternatives were not genuinely surfaced and explicitly ruled out — by the user or by the planning agent with evidence — they cannot be called "considered." That said, the absence of prior consideration is not an excuse to skip the section; it is an occasion to reflect on why the chosen approach was reached without exploring alternatives. If there are genuinely no alternatives, state this clearly — be honest with the reader.
 - **Scope**: explicit in/out boundaries. What is deliberately excluded and why.
 - **Conducted Research and Experiments**: optional. If internet research was conducted or a PoC was built, record the fact and link to artifacts (PoC paths, research sub-agent transcripts). Results themselves belong in the sections above; this section tracks provenance.
 - **Implementation Steps**: what needs to be done and in what order. Do not include verbatim code — the implementation agent is capable of writing code on its own. There is no need to specify how a for-loop should look. Implementation details that genuinely matter MUST be included, with an explanation of why they matter. Think carefully to distinguish valuable input from platitudes.
 - **Skills to Use**: list clearly what skills should be used and when:
    - `git-vs-plan-drift-check` as the very first step (state arguments in plan explicitly)
    - appropriate `*verification*` or `*testing*` skills to verify the work
    - git-related skills
    - skills for CI, deployment, etc.

## Format
The plan must be scannable: use headers, short bullets, and bold for key terms.

## Baseline Commit
This is the HEAD commit at skill load time:
!`git rev-parse HEAD`
