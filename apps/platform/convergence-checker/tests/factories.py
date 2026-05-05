from __future__ import annotations

from typing import TYPE_CHECKING

from convergence_checker.core.models import (
    ApplicationStatus,
    ConditionFalse,
    ConditionTrue,
    ConditionUnknown,
    ConvergenceState,
    HealthyStreak,
    KnownCommit,
    MissingStatus,
    NoCommit,
    NoOperationPhase,
    NoSentStatus,
    PendingPeriod,
    ReportedStatus,
    ResourceStatus,
    SentStatus,
    StageCondition,
    StageStatus,
)

if TYPE_CHECKING:
    from datetime import datetime


def _resource_status(value: str | None, *, source: str) -> ResourceStatus:
    if value is None:
        return MissingStatus(source=source)
    return ReportedStatus(value=value)


def _condition_from_value(*, value: bool | str) -> StageCondition:
    if value is True:
        return ConditionTrue()
    if value is False:
        return ConditionFalse()
    return ConditionUnknown(value=value)


def app_status(
    *,
    name: str = "test",
    health: str | None,
    sync: str | None,
    operation: str | None,
) -> ApplicationStatus:
    return ApplicationStatus(
        name=name,
        health_status=_resource_status(health, source="application health"),
        sync_status=_resource_status(sync, source="application sync"),
        operation_phase=NoOperationPhase() if operation is None else ReportedStatus(value=operation),
    )


def stage_status(
    *,
    name: str = "test",
    namespace: str = "ns",
    health: str | None,
    conditions: dict[str, bool | str] | None = None,
) -> StageStatus:
    return StageStatus(
        name=name,
        namespace=namespace,
        health_status=_resource_status(health, source="stage health"),
        conditions={name: _condition_from_value(value=value) for name, value in (conditions or {}).items()},
    )


def healthy_streak(count: int = 0) -> ConvergenceState:
    return ConvergenceState(progress=HealthyStreak(consecutive_checks=count))


def pending_since(first_observed_at: datetime) -> ConvergenceState:
    return ConvergenceState(progress=PendingPeriod(first_observed_at=first_observed_at))


def known_commit(sha: str) -> KnownCommit:
    return KnownCommit(sha=sha)


def no_commit() -> NoCommit:
    return NoCommit(reason="test")


def sent_status(state: str, description: str) -> SentStatus:
    return SentStatus(state=state, description=description)


def no_sent_status() -> NoSentStatus:
    return NoSentStatus()


def no_operation_phase() -> NoOperationPhase:
    return NoOperationPhase()
