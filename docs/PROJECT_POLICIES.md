# Project Policies

These are the operational constraints that prevent the most common classes of mistakes in this project's infrastructure-heavy domain — non-reproducible builds, implicit state mutations, and scattered tooling.

## Pin External Dependency Versions
Pin every external dependency to patch version. Flag violations when encountered.

Unpinned dependencies make builds non-reproducible and upgrades invisible.


## Static Checks Run via Pre-commit
`prek` is the single entry point for all static analysis. Before adding a static check to a verification plan, check `.pre-commit-config.yaml` — if the check is already there, `prek run --all-files` covers it. If a useful check is missing from the config, propose adding it rather than running it ad-hoc.

Intentionally excluded checks stay in the config as commented-out entries. The reasoning behind the exclusion goes **only** in the commit message, **not** next to the entry.


## Explicit Context for Infrastructure Targets
Always specify the target explicitly: `kubectl --context <name>`, `docker --context <name>`, etc. Never rely on "current" defaults — implicit targeting risks silent cross-environment side effects, especially when sub-agents operate in parallel.

This is especially important inside scripts, where each command must carry its own context flag.
