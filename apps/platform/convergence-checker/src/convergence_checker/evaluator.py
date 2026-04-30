from __future__ import annotations

from datetime import UTC, datetime

from convergence_checker.models import (
    ApplicationStatus,
    ConvergenceState,
    EvaluationResult,
    EvaluationVerdict,
    StageStatus,
)


def evaluate_app(app: ApplicationStatus) -> EvaluationResult:
    if app.health_status == "Degraded":
        return EvaluationResult(
            verdict=EvaluationVerdict.FAILURE,
            description=f"{app.name}: Degraded",
        )

    if app.operation_phase in ("Failed", "Error"):
        return EvaluationResult(
            verdict=EvaluationVerdict.FAILURE,
            description=f"{app.name}: operation {app.operation_phase}",
        )

    if app.health_status == "Healthy" and app.sync_status == "Synced":
        return EvaluationResult(
            verdict=EvaluationVerdict.HEALTHY,
            description=f"{app.name}: Healthy+Synced",
        )

    return EvaluationResult(
        verdict=EvaluationVerdict.PENDING,
        description=f"{app.name}: health={app.health_status} sync={app.sync_status} op={app.operation_phase}",
    )


def evaluate_stage(stage: StageStatus) -> EvaluationResult:
    if stage.health_status == "Unhealthy":
        return EvaluationResult(
            verdict=EvaluationVerdict.FAILURE,
            description=f"{stage.namespace}/{stage.name}: Unhealthy",
        )

    if stage.conditions.get("Healthy") is False:
        return EvaluationResult(
            verdict=EvaluationVerdict.FAILURE,
            description=f"{stage.namespace}/{stage.name}: Healthy condition is False",
        )

    is_healthy = stage.health_status == "Healthy"
    is_ready = stage.conditions.get("Ready") is True
    is_verified = stage.conditions.get("Verified") is True

    if is_healthy and is_ready and is_verified:
        return EvaluationResult(
            verdict=EvaluationVerdict.HEALTHY,
            description=f"{stage.namespace}/{stage.name}: Healthy+Ready+Verified",
        )

    return EvaluationResult(
        verdict=EvaluationVerdict.PENDING,
        description=(
            f"{stage.namespace}/{stage.name}: "
            f"health={stage.health_status} "
            f"ready={stage.conditions.get('Ready')} "
            f"verified={stage.conditions.get('Verified')}"
        ),
    )


def aggregate(
    results: list[EvaluationResult],
    state: ConvergenceState,
    stability_threshold: int,
    safety_timeout_seconds: int,
) -> tuple[EvaluationResult, ConvergenceState]:
    now = datetime.now(tz=UTC)

    failures = [r for r in results if r.verdict == EvaluationVerdict.FAILURE]
    if failures:
        descriptions = "; ".join(f.description for f in failures)
        return (
            EvaluationResult(
                verdict=EvaluationVerdict.FAILURE,
                description=f"Failed: {descriptions}",
            ),
            ConvergenceState(
                consecutive_healthy=0,
                first_pending_at=None,
            ),
        )

    all_healthy = all(r.verdict == EvaluationVerdict.HEALTHY for r in results)
    if all_healthy and results:
        new_count = min(state.consecutive_healthy + 1, stability_threshold * 2)
        if new_count >= stability_threshold:
            return (
                EvaluationResult(
                    verdict=EvaluationVerdict.HEALTHY,
                    description=f"All {len(results)} resources healthy for {new_count} consecutive checks",
                ),
                ConvergenceState(
                    consecutive_healthy=new_count,
                    first_pending_at=None,
                ),
            )
        return (
            EvaluationResult(
                verdict=EvaluationVerdict.PENDING,
                description=f"Healthy {new_count}/{stability_threshold} — awaiting stability",
            ),
            ConvergenceState(
                consecutive_healthy=new_count,
                first_pending_at=None,
            ),
        )

    first_pending = state.first_pending_at or now
    elapsed = (now - first_pending).total_seconds()
    if elapsed > safety_timeout_seconds:
        pending = [r for r in results if r.verdict == EvaluationVerdict.PENDING]
        descriptions = "; ".join(p.description for p in pending)
        return (
            EvaluationResult(
                verdict=EvaluationVerdict.FAILURE,
                description=f"Safety timeout ({safety_timeout_seconds}s) exceeded. Pending: {descriptions}",
            ),
            ConvergenceState(
                consecutive_healthy=0,
                first_pending_at=first_pending,
            ),
        )

    return (
        EvaluationResult(
            verdict=EvaluationVerdict.PENDING,
            description=f"{sum(1 for r in results if r.verdict == EvaluationVerdict.PENDING)} resources pending",
        ),
        ConvergenceState(
            consecutive_healthy=0,
            first_pending_at=first_pending,
        ),
    )
