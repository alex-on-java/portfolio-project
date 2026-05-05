from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from attrs import frozen

from convergence_checker.core import evaluator
from convergence_checker.core.models import (
    ClusterIdentity,
    CommitTracking,
    ConvergenceState,
    CycleInputs,
    CycleOutputs,
    EvaluationResult,
    EvaluationVerdict,
    KnownCommit,
    NoCommit,
    NoSentStatus,
    SentStatus,
    SentStatusTracking,
)
from convergence_checker.core.ports import CommitStatus

if TYPE_CHECKING:
    from datetime import datetime

    from convergence_checker.core.ports import ClusterReader, StatusReporter

log: structlog.stdlib.BoundLogger = structlog.get_logger()


@frozen
class CycleConfig:
    stability_threshold: int
    safety_timeout_seconds: int
    owner_repo: str
    github_status_context: str


def _github_state_from_verdict(verdict: EvaluationVerdict) -> str:
    mapping: dict[EvaluationVerdict, str] = {
        EvaluationVerdict.HEALTHY: "success",
        EvaluationVerdict.PENDING: "pending",
        EvaluationVerdict.FAILURE: "failure",
    }
    return mapping[verdict]


def _apply_sha_change(
    prev_state: ConvergenceState,
    prev_commit: CommitTracking,
    prev_sent: SentStatusTracking,
    identity: ClusterIdentity,
) -> tuple[CommitTracking, ConvergenceState, SentStatusTracking]:
    current_commit = identity.commit
    if isinstance(current_commit, KnownCommit) and current_commit != prev_commit:
        old_sha = prev_commit.sha if isinstance(prev_commit, KnownCommit) else None
        log.info("sha_changed", old=old_sha, new=current_commit.sha)
        return (current_commit, prev_state.reset(), NoSentStatus(reason="commit changed"))
    return (prev_commit, prev_state, prev_sent)


def _dedup_and_post(
    reporter: StatusReporter,
    commit: CommitTracking,
    result: EvaluationResult,
    previous_sent: SentStatusTracking,
    config: CycleConfig,
) -> SentStatusTracking:
    if isinstance(commit, NoCommit):
        return previous_sent
    gh_state = _github_state_from_verdict(result.verdict)
    candidate = SentStatus(state=gh_state, description=result.description)
    if candidate == previous_sent:
        return previous_sent
    status = CommitStatus(
        owner_repo=config.owner_repo,
        sha=commit.sha,
        state=gh_state,
        context=config.github_status_context,
        description=result.description,
    )
    reporter.post(status)
    log.info("github_status_reported", state=gh_state)
    return candidate


def _gather_results(reader: ClusterReader) -> list[EvaluationResult]:
    apps = reader.list_applications()
    stage_namespaces = reader.list_stage_namespaces()
    stages = [s for ns in stage_namespaces for s in reader.list_stages(ns)]
    return [evaluator.evaluate_app(a) for a in apps] + [evaluator.evaluate_stage(s) for s in stages]


def run_cycle(
    inputs: CycleInputs,
    reader: ClusterReader,
    reporter: StatusReporter,
    config: CycleConfig,
    *,
    now: datetime,
) -> CycleOutputs:
    identity = reader.read_cluster_identity()
    effective_commit, effective_state, effective_sent = _apply_sha_change(
        inputs.previous_state,
        inputs.previous_commit,
        inputs.previous_sent_status,
        identity,
    )

    results = _gather_results(reader)

    result, new_state = evaluator.aggregate(
        results,
        effective_state,
        stability_threshold=config.stability_threshold,
        safety_timeout_seconds=config.safety_timeout_seconds,
        now=now,
    )

    new_sent = _dedup_and_post(reporter, effective_commit, result, effective_sent, config)

    reader.write_heartbeat(now)

    return CycleOutputs(
        new_state=new_state,
        new_commit=effective_commit,
        new_sent_status=new_sent,
        result=result,
        resource_count=len(results),
    )
