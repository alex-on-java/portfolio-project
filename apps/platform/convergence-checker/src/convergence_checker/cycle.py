from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from convergence_checker import evaluator
from convergence_checker.io_adapters import CommitStatus, NullStatusReporter
from convergence_checker.models import (
    ConvergenceState,
    CycleInputs,
    CycleOutputs,
    EvaluationResult,
    EvaluationVerdict,
)

if TYPE_CHECKING:
    from datetime import datetime

    from convergence_checker.io_adapters import ClusterReader, StatusReporter

log: structlog.stdlib.BoundLogger = structlog.get_logger()

ABSORBED_FAULTS: tuple[type[BaseException], ...] = (Exception,)


@dataclass(frozen=True)
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
    prev_sha: str | None,
    prev_sent: tuple[str, str] | None,
    current_sha: str | None,
) -> tuple[str | None, ConvergenceState, tuple[str, str] | None]:
    if current_sha and current_sha != prev_sha:
        log.info("sha_changed", old=prev_sha, new=current_sha)
        return (current_sha, ConvergenceState(), None)
    return (prev_sha, prev_state, prev_sent)


def _dedup_and_post(
    reporter: StatusReporter,
    sha: str | None,
    result: EvaluationResult,
    previous_sent: tuple[str, str] | None,
    config: CycleConfig,
) -> tuple[str, str] | None:
    if sha is None or isinstance(reporter, NullStatusReporter):
        return previous_sent
    gh_state = _github_state_from_verdict(result.verdict)
    candidate = (gh_state, result.description)
    if candidate == previous_sent:
        return previous_sent
    status = CommitStatus(
        owner_repo=config.owner_repo,
        sha=sha,
        state=gh_state,
        context=config.github_status_context,
        description=result.description,
    )
    try:
        reporter.post(status)
    except ABSORBED_FAULTS:
        log.exception("github_status_failed")
        return previous_sent
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
    effective_sha, effective_state, effective_sent = _apply_sha_change(
        inputs.previous_state,
        inputs.previous_commit_sha,
        inputs.previous_sent_status,
        identity.get("prCommitSha"),
    )

    results = _gather_results(reader)

    result, new_state = evaluator.aggregate(
        results,
        effective_state,
        stability_threshold=config.stability_threshold,
        safety_timeout_seconds=config.safety_timeout_seconds,
    )

    new_sent = _dedup_and_post(reporter, effective_sha, result, effective_sent, config)

    try:
        reader.write_heartbeat(now)
    except ABSORBED_FAULTS:
        log.exception("heartbeat_write_failed")

    return CycleOutputs(
        new_state=new_state,
        new_commit_sha=effective_sha,
        new_sent_status=new_sent,
        result=result,
        resource_count=len(results),
    )
