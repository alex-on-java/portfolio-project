from __future__ import annotations

from typing import TYPE_CHECKING

from convergence_checker.core.models import (
    ApplicationStatus,
    ConvergenceState,
    EvaluationResult,
    EvaluationVerdict,
    StageStatus,
)

if TYPE_CHECKING:
    from datetime import datetime


def evaluate_app(app: ApplicationStatus) -> EvaluationResult:
    if app.is_degraded():
        return EvaluationResult(
            verdict=EvaluationVerdict.FAILURE,
            description=app.failure_description(),
        )

    if app.has_failed_operation():
        return EvaluationResult(
            verdict=EvaluationVerdict.FAILURE,
            description=app.failure_description(),
        )

    if app.is_healthy_synced():
        return EvaluationResult(
            verdict=EvaluationVerdict.HEALTHY,
            description=app.healthy_description(),
        )

    return EvaluationResult(
        verdict=EvaluationVerdict.PENDING,
        description=app.pending_description(),
    )


def evaluate_stage(stage: StageStatus) -> EvaluationResult:
    if stage.is_unhealthy():
        return EvaluationResult(
            verdict=EvaluationVerdict.FAILURE,
            description=stage.failure_description(),
        )

    if stage.has_failed_healthy_condition():
        return EvaluationResult(
            verdict=EvaluationVerdict.FAILURE,
            description=stage.failure_description(),
        )

    if stage.is_healthy_ready_verified():
        return EvaluationResult(
            verdict=EvaluationVerdict.HEALTHY,
            description=stage.healthy_description(),
        )

    return EvaluationResult(
        verdict=EvaluationVerdict.PENDING,
        description=stage.pending_description(),
    )


def aggregate(
    results: list[EvaluationResult],
    state: ConvergenceState,
    stability_threshold: int,
    safety_timeout_seconds: int,
    *,
    now: datetime,
) -> tuple[EvaluationResult, ConvergenceState]:
    failures = [r for r in results if r.verdict == EvaluationVerdict.FAILURE]
    if failures:
        descriptions = "; ".join(f.description for f in failures)
        return (
            EvaluationResult(
                verdict=EvaluationVerdict.FAILURE,
                description=f"Failed: {descriptions}",
            ),
            state.reset(),
        )

    all_healthy = all(r.verdict == EvaluationVerdict.HEALTHY for r in results)
    if all_healthy and results:
        new_state = state.record_healthy(stability_threshold=stability_threshold)
        new_count = new_state.consecutive_healthy
        if new_count >= stability_threshold:
            return (
                EvaluationResult(
                    verdict=EvaluationVerdict.HEALTHY,
                    description=f"All {len(results)} resources healthy for {new_count} consecutive checks",
                ),
                new_state,
            )
        return (
            EvaluationResult(
                verdict=EvaluationVerdict.PENDING,
                description=f"Healthy {new_count}/{stability_threshold} — awaiting stability",
            ),
            new_state,
        )

    pending_state = state.record_pending(now=now)
    if pending_state.pending_timed_out(now=now, safety_timeout_seconds=safety_timeout_seconds):
        pending = [r for r in results if r.verdict == EvaluationVerdict.PENDING]
        descriptions = "; ".join(p.description for p in pending)
        return (
            EvaluationResult(
                verdict=EvaluationVerdict.FAILURE,
                description=f"Safety timeout ({safety_timeout_seconds}s) exceeded. Pending: {descriptions}",
            ),
            pending_state,
        )

    return (
        EvaluationResult(
            verdict=EvaluationVerdict.PENDING,
            description=f"{sum(1 for r in results if r.verdict == EvaluationVerdict.PENDING)} resources pending",
        ),
        pending_state,
    )
