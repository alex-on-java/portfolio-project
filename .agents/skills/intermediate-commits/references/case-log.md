# Case Log

Append-only precedent log for situations the decision tree does not clearly cover. When the
decision tree leaves ambiguity, check this file for similar cases before asking the human.

If no similar case exists, use `AskUserQuestion` to resolve the ambiguity, then append the
outcome here so future agents benefit.

## Entry Format

```
### <short title>

**Situation:** What happened and why the decision tree was insufficient.
**Question posed:** What was asked.
**Resolution:** What the human decided and the reasoning behind it.
```

---

### Level of detail for resource calibration commits

**Situation:** Agent wrote an intermediate commit that included detailed resource profiles
tiered by workload type (controllers vs webhooks vs batch jobs), with explicit rationale
for each tier — headroom multipliers, measured usage, and risk factors. The decision tree
does not address how much implementation-level detail belongs in an intermediate commit
versus being deferred to the squash commit.

**Question posed:** Was this level of detail warranted for an intermediate commit?

**Resolution:** Yes. Intermediate commits capture context at peak — the agent just measured
actual usage and calibrated values. This detail is expensive to reconstruct later and is
exactly the kind of implementation reasoning that gets lost across agent handoffs. The
decision tree's "describe the discovery with evidence" branch applies: the tiered profiles
are evidence-backed implementation decisions, not fabricated motivation.

---

### Amending vs creating a new commit for a same-branch fix

**Situation:** Two consecutive commits were logically one change — the first set resource
values, the second raised them because the platform enforced a higher minimum floor. The
agent created a second commit instead of amending the first. The decision tree covers
"fix for a previous commit" but does not say whether to amend or create a new commit.

**Question posed:** Should the agent have amended the first commit instead of creating a
second?

**Resolution:** Create a new commit, not amend. Each intermediate commit is a snapshot of
what the agent knew at that point in time. The second commit captures a genuine discovery
(the platform enforces a floor that wasn't anticipated). Amending would merge two moments
of understanding into one, erasing the learning sequence. The squash skill is responsible
for consolidating — intermediate commits preserve the timeline.
