This project exists to demonstrate production-grade architecture with weighted engineering decisions. No deadlines means no shortcuts — there's always time to do it properly.


## Working Principles

### The 10× Litmus Test
Before committing to an approach, ask: would this decision still hold at 10× the current scale?

*Why this matters*: the cost of a sound decision and a "good enough" decision is often similar today, but diverges dramatically at scale. Catching this early is a choice; catching it later is a rewrite.


### Verify Assumptions Against the Actual Target
Documentation describes intended behavior; live tests reveal actual behavior on the specific version and configuration in use. Before committing to an approach, build a minimal throwaway test against the actual target — this applies to infrastructure, new technologies, and unfamiliar APIs alike.

*Why this matters*: a wrong assumption discovered after implementation becomes a foundation for workarounds. Discovered before — it's a data point, and humans can weigh alternatives while the cost of changing course is still low.


### Linting Is Hygiene, Not Evidence
Linting keeps things tidy; tests keep you honest. Static checks confirm that code is well-formed, but say nothing about whether it actually works. When planning verification, the attention should be proportional to the confidence each check provides.

*Why this matters*: a thorough-looking list of static checks can create an illusion of rigor. Clean code that doesn't work is still broken.


### Workarounds Are Broken Windows
Completion bias, the drive to close a task regardless of obstacles, makes workarounds feel like progress. They can be — during exploration, any workaround to get data or validate a hypothesis is fair game. The danger is when they get committed into the codebase: a tactical win, a strategic loss.

Sometimes workarounds are inevitable — that's a human decision, informed by the full picture of pros and cons.

*Why this matters*: a workaround in the code signals to the next agent that this is an acceptable pattern. "That's just how things are done around here" — and they accumulate.


### Commit Messages as Decision Records
`git log` deserves as much attention as the code itself during exploration. Commits in this project capture **why** a change was made, not just what changed, including the alternatives that were considered and rejected.

*Why this matters*: the reasoning behind past decisions reveals connections across the project that aren't visible in the code.


### Comments Fossilize Context
A comment explaining why code was written a certain way carries implicit authority: it sits next to the code as if it's still true. But the system around it changes independently, and the comment stays, asserting a context that may no longer exist. The commit message is a better home for the "why."

*Why this matters*: a commit message is inherently tied to a point in time and a changeset. A comment is tied to neither.


### Leave The Code Better Than You Found It
When something looks off during exploration, double-check the commit history first (it may reveal a deliberate choice), then flag it to a human, even if it's unrelated to the current task.

*Why this matters*: entropy is the default direction of any codebase. The bystander effect applies: if everyone assumes the next agent will flag it, no one does.


### Explicit Over Implicit When It Doesn't Hurt
Making a value or behavior explicit is valuable when it represents a deliberate choice grounded in the project's needs.

*Why this matters*: the act of choosing explicitly forces deliberation: what should this be for *us*, and why? Explicitness applied indiscriminately dilutes that signal. The goal is visible decisions, not visible defaults.

---

Important files to read:
	- [Project policies the agent should always follow](docs/PROJECT_POLICIES.md)
