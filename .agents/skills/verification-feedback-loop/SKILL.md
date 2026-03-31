---
name: verification-feedback-loop
description: Must be loaded alongside any `*verification*` or `*testing*` skill. This is a meta-skill - not what to test, but how to approach it, how to set up the verification process so no issue slips through.
disable-model-invocation: false
user-invocable: false
---

*To avoid verbosity, below the word "test" (noun and verb) is used as an umbrella term for any verification activity, from linters and tests to manual checks and spinning up the whole cluster.*

Every time you need to test something, there is a well-known temptation (called confirmation bias) to fix what has failed and call it a day. This is understandable, but not acceptable.

This skill enforces a feedback loop: test -> fix -> repeat.
Even if the test takes long, even if you think "I just fixed a variable name, all should be good", you must repeat until all tests pass. And by all I mean explicitly ALL.
Yes, while you are fixing an issue within a single unit test, you don't need to rerun the whole suite, linters and whatnot. But once that unit test is fixed, rerun **everything**.
If you want a simple rule of thumb, here it is: before you can say "task is complete", all applicable verification steps should pass. It doesn't matter how long it takes, do not give up. Don't use shortcuts to claim you've finished.

Here are some popular escape hatches agents like to use, and how to mitigate them.
1. "This is not related to our changes". The most popular one by far.
Because of completion bias (the drive to finish the task ASAP), agents tend to claim any issue as "unrelated" if there's any way to justify it.
Mitigation: you need to prove that this is the case. For example, check out the branch to the state before your changes and verify the issue is present. If the issue doesn't manifest in that state, then it's related and should be fixed. Yes, it wasn't in the plan, but that's exactly because it wasn't reachable before your changes. However, in most cases it's easier to just fix it, because proving it's unrelated takes longer.
2. "For this step I need [something], which is not available; but I ran linters and they passed, so everything should work". The reason behind this behavior is the same as above.
Mitigation: first, double-check that it's really not present. If not, ask an Explorer agent to find anything related (e.g., scripts for testing, dedicated skills, documents, instructions).
Only after that can you claim it's not available. And even then, the fact it's not available doesn't mean you can say "work is done". It's not done, full stop. You faced a blocker and can't move forward, and that is what should be written in your report to the user.
