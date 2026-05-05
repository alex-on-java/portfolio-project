from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal

from attrs import field, frozen

if TYPE_CHECKING:
    from datetime import datetime


class EvaluationVerdict(StrEnum):
    HEALTHY = "healthy"
    PENDING = "pending"
    FAILURE = "failure"


@frozen
class EvaluationResult:
    verdict: EvaluationVerdict
    description: str


@frozen
class ReportedStatus:
    value: str

    def render(self) -> str:
        return self.value


@frozen
class MissingStatus:
    source: str

    def render(self) -> str:
        return f"missing {self.source}"


type ResourceStatus = ReportedStatus | MissingStatus


@frozen
class NoOperationPhase:
    def render(self) -> str:
        return "no operation"


type OperationPhase = ReportedStatus | NoOperationPhase


def reported_status(value: str) -> ReportedStatus:
    return ReportedStatus(value=value)


def missing_status(source: str) -> MissingStatus:
    return MissingStatus(source=source)


def _status_matches(status: ResourceStatus | OperationPhase, expected: str) -> bool:
    return isinstance(status, ReportedStatus) and status.value == expected


@frozen
class ApplicationStatus:
    name: str
    health_status: ResourceStatus
    sync_status: ResourceStatus
    operation_phase: OperationPhase

    def is_degraded(self) -> bool:
        return _status_matches(self.health_status, "Degraded")

    def has_failed_operation(self) -> bool:
        return any(_status_matches(self.operation_phase, phase) for phase in ("Failed", "Error"))

    def is_healthy_synced(self) -> bool:
        return _status_matches(self.health_status, "Healthy") and _status_matches(self.sync_status, "Synced")

    def pending_description(self) -> str:
        return (
            f"{self.name}: "
            f"health={self.health_status.render()} "
            f"sync={self.sync_status.render()} "
            f"op={self.operation_phase.render()}"
        )

    def failure_description(self) -> str:
        if self.is_degraded():
            return f"{self.name}: Degraded"
        if isinstance(self.operation_phase, ReportedStatus):
            return f"{self.name}: operation {self.operation_phase.value}"
        return self.pending_description()

    def healthy_description(self) -> str:
        return f"{self.name}: Healthy+Synced"


@frozen
class ConditionTrue:
    def render(self) -> str:
        return "True"


@frozen
class ConditionFalse:
    def render(self) -> str:
        return "False"


@frozen
class ConditionUnknown:
    value: str

    def render(self) -> str:
        return self.value


type StageCondition = ConditionTrue | ConditionFalse | ConditionUnknown


def _immutable_conditions(conditions: dict[str, StageCondition]) -> MappingProxyType[str, StageCondition]:
    return MappingProxyType(dict(conditions))


def _condition_is_true(condition: StageCondition | None) -> bool:
    return isinstance(condition, ConditionTrue)


def _condition_is_false(condition: StageCondition | None) -> bool:
    return isinstance(condition, ConditionFalse)


def _render_condition(condition: StageCondition | None) -> str:
    if condition is None:
        return "missing"
    return condition.render()


@frozen
class StageStatus:
    name: str
    namespace: str
    health_status: ResourceStatus
    conditions: MappingProxyType[str, StageCondition] = field(converter=_immutable_conditions)

    def is_unhealthy(self) -> bool:
        return _status_matches(self.health_status, "Unhealthy")

    def has_failed_healthy_condition(self) -> bool:
        return _condition_is_false(self.conditions.get("Healthy"))

    def is_healthy_ready_verified(self) -> bool:
        return (
            _status_matches(self.health_status, "Healthy")
            and _condition_is_true(self.conditions.get("Ready"))
            and _condition_is_true(self.conditions.get("Verified"))
        )

    def failure_description(self) -> str:
        if self.is_unhealthy():
            return f"{self.namespace}/{self.name}: Unhealthy"
        return f"{self.namespace}/{self.name}: Healthy condition is False"

    def healthy_description(self) -> str:
        return f"{self.namespace}/{self.name}: Healthy+Ready+Verified"

    def pending_description(self) -> str:
        return (
            f"{self.namespace}/{self.name}: "
            f"health={self.health_status.render()} "
            f"ready={_render_condition(self.conditions.get('Ready'))} "
            f"verified={_render_condition(self.conditions.get('Verified'))}"
        )


@frozen
class HealthyStreak:
    consecutive_checks: int = 0

    def incremented(self, *, stability_threshold: int) -> HealthyStreak:
        return HealthyStreak(
            consecutive_checks=min(self.consecutive_checks + 1, stability_threshold * 2),
        )


@frozen
class PendingPeriod:
    first_observed_at: datetime


type ConvergenceProgress = HealthyStreak | PendingPeriod


@frozen
class ConvergenceState:
    progress: ConvergenceProgress = field(factory=HealthyStreak)

    @property
    def consecutive_healthy(self) -> int:
        if isinstance(self.progress, HealthyStreak):
            return self.progress.consecutive_checks
        return 0

    @property
    def phase(self) -> Literal["healthy_streak", "pending"]:
        if isinstance(self.progress, HealthyStreak):
            return "healthy_streak"
        return "pending"

    def reset(self) -> ConvergenceState:
        return ConvergenceState()

    def record_healthy(self, *, stability_threshold: int) -> ConvergenceState:
        streak = self.progress if isinstance(self.progress, HealthyStreak) else HealthyStreak()
        return ConvergenceState(progress=streak.incremented(stability_threshold=stability_threshold))

    def record_pending(self, *, now: datetime) -> ConvergenceState:
        if isinstance(self.progress, PendingPeriod):
            return self
        return ConvergenceState(progress=PendingPeriod(first_observed_at=now))

    def pending_timed_out(self, *, now: datetime, safety_timeout_seconds: int) -> bool:
        progress = self.progress
        if not isinstance(progress, PendingPeriod):
            return False
        return (now - progress.first_observed_at).total_seconds() > safety_timeout_seconds

    def pending_since(self) -> datetime:
        progress = self.progress
        if not isinstance(progress, PendingPeriod):
            msg = "Convergence state is not pending"
            raise TypeError(msg)
        return progress.first_observed_at


@frozen
class KnownCommit:
    sha: str


@frozen
class NoCommit:
    reason: str


type CommitTracking = KnownCommit | NoCommit


@frozen
class SentStatus:
    state: str
    description: str

    def as_tuple(self) -> tuple[str, str]:
        return (self.state, self.description)


@frozen
class NoSentStatus:
    reason: str = "not sent yet"


type SentStatusTracking = SentStatus | NoSentStatus


@frozen
class ClusterIdentity:
    argocd_namespace: str
    commit: CommitTracking


@frozen
class CycleInputs:
    previous_state: ConvergenceState
    previous_commit: CommitTracking
    previous_sent_status: SentStatusTracking


@frozen
class CycleOutputs:
    new_state: ConvergenceState
    new_commit: CommitTracking
    new_sent_status: SentStatusTracking
    result: EvaluationResult
    resource_count: int
