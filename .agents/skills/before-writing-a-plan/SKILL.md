---
name: before-writing-a-plan
description: |
  Fires right before the agent is about to write a plan to a file; typically signaled by phrases like "Now I have a complete picture, let me write the plan". Use the skill **before writing a single line of the plan**.
---

# Pre-plan Alignment Checkpoint

## Before Writing a Plan

Planning is the highest-leverage phase of any task: a mistake here compounds through every
implementation step that follows. Preparation for the plan matters even more, because the entire
planning effort becomes waste if it rests on a false premise.

A plan file runs hundreds of lines. Once written, it carries implicit authority: a human skimming
it will catch obvious gaps, but a quietly wrong assumption buried deep in the text will sail
through. The cheapest place to catch misalignment is before the plan exists.

## When to Engage

The transition point between exploration and plan writing. You've gathered enough context and are
about to start writing the plan file. Stop. Run this protocol first, in the chat.

## The Protocol

State the following in the chat. Each item should be condensed: information-dense, one line where
one line suffices.

### Framing

1. **Problem statement**: what we are solving
2. **Why it matters**: what makes this important
3. **What we know for sure**: verified facts, confirmed assumptions
4. **Main assumptions**: presuppositions the whole task rests on, including ones inherited from the initial request

### Alignment Lists

**A. Explicitly aligned on** — what agent and user have agreed on during the conversation, including the user's initial requirements.

**B. Reasonably inferred** — what the user hasn't explicitly approved, but follows logically from what was said.

**C. Implied defaults** — what hasn't been discussed at all,  but have reasonable defaults; this includes implementation details.

**D. Needs discussion** — open questions where alignment is still missing.

**E. Assumptions to verify** — things stated or assumed that should be checked against reality before the plan commits to them.

For each item in list E, indicate the research channel (items can need more than one):
- **Docs**: official documentation of the tools and technologies involved
- **OSS code**: source code of open-source dependencies, where documentation may lag behind or omit detail
- **Internet**: GitHub issues, community articles, example projects, etc

Mark **crucial assumptions** separately: those where being wrong would invalidate the plan. For these, verification through a **proof of concept** or interaction with the live system must be used, as per working principle *"Verify Assumptions Against the Actual Target"*. This requires exiting plan mode: flag it to the user.

## What's Next?

After writing pre-plan alignment checkpoint to the chat, stop and let user give it's comments, so you both can align.
This ping-pong could take several turns, so be patient: do not rush to write the plan, wait for the explicit user approval.
In case assumption verification require a PoC creation, user will exit the plan mode on their own.
