from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Literal, Self

if TYPE_CHECKING:
    from datetime import datetime

GithubState = Literal["pending", "success", "failure"]


class ResourceKind(Enum):
    APPLICATION = "application"
    STAGE = "stage"


class ResourceState(Enum):
    BROKEN = "broken"
    CONVERGED = "converged"
    IN_PROGRESS = "in-progress"


class Verdict(Enum):
    BROKEN = "broken"
    CONVERGED = "converged"
    IN_PROGRESS = "in-progress"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class ApplicationSnapshot:
    name: str
    health: str | None
    sync: str | None
    operation: str | None


@dataclass(frozen=True, slots=True)
class StageSnapshot:
    namespace: str
    name: str
    health: str | None
    healthy_condition: bool | None
    ready_condition: bool | None
    verified_condition: bool | None


@dataclass(frozen=True, slots=True)
class ResourceClassification:
    kind: ResourceKind
    identity: tuple[str, ...]
    state: ResourceState
    description: str


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    verdict: Verdict
    github_state: GithubState | None
    description: str
    resource_count: int
    consecutive_converged: int
    should_write_heartbeat: bool


@dataclass(frozen=True, slots=True)
class PostedStatus:
    sha: str
    state: GithubState
    description: str


@dataclass(frozen=True, slots=True)
class ConvergenceState:
    consecutive_converged: int = 0
    first_in_progress_at: datetime | None = None
    last_posted: PostedStatus | None = None
    last_seen_sha: str | None = None

    def with_sha(self, sha: str | None) -> Self:
        if sha == self.last_seen_sha:
            return self
        return type(self)(last_seen_sha=sha)

    def remember_post(self, posted: PostedStatus) -> Self:
        return type(self)(
            consecutive_converged=self.consecutive_converged,
            first_in_progress_at=self.first_in_progress_at,
            last_posted=posted,
            last_seen_sha=self.last_seen_sha,
        )


@dataclass(frozen=True, slots=True)
class ClassificationSummary:
    state: ResourceState
    broken: tuple[ResourceClassification, ...]
    in_progress: tuple[ResourceClassification, ...]
    converged: tuple[ResourceClassification, ...]
    total: int


def classify_application(application: ApplicationSnapshot) -> ResourceClassification:
    identity = (application.name,)
    if application.health == "Degraded":
        return ResourceClassification(
            ResourceKind.APPLICATION,
            identity,
            ResourceState.BROKEN,
            f"{application.name}: Degraded",
        )
    if application.operation in {"Failed", "Error"}:
        return ResourceClassification(
            ResourceKind.APPLICATION,
            identity,
            ResourceState.BROKEN,
            f"{application.name}: operation {application.operation}",
        )
    if application.health == "Healthy" and application.sync == "Synced":
        return ResourceClassification(
            ResourceKind.APPLICATION,
            identity,
            ResourceState.CONVERGED,
            f"{application.name}: Healthy+Synced",
        )
    return ResourceClassification(
        ResourceKind.APPLICATION,
        identity,
        ResourceState.IN_PROGRESS,
        f"{application.name}: health={_text(application.health)} "
        f"sync={_text(application.sync)} op={_text(application.operation)}",
    )


def classify_stage(stage: StageSnapshot) -> ResourceClassification:
    identity = (stage.namespace, stage.name)
    qualified_name = f"{stage.namespace}/{stage.name}"
    if stage.health == "Unhealthy":
        return ResourceClassification(
            ResourceKind.STAGE,
            identity,
            ResourceState.BROKEN,
            f"{qualified_name}: Unhealthy",
        )
    if stage.healthy_condition is False:
        return ResourceClassification(
            ResourceKind.STAGE,
            identity,
            ResourceState.BROKEN,
            f"{qualified_name}: Healthy condition is False",
        )
    if stage.health == "Healthy" and stage.ready_condition is True and stage.verified_condition is True:
        return ResourceClassification(
            ResourceKind.STAGE,
            identity,
            ResourceState.CONVERGED,
            f"{qualified_name}: Healthy+Ready+Verified",
        )
    return ResourceClassification(
        ResourceKind.STAGE,
        identity,
        ResourceState.IN_PROGRESS,
        f"{qualified_name}: health={_text(stage.health)} ready={_bool_text(value=stage.ready_condition)} "
        f"verified={_bool_text(value=stage.verified_condition)}",
    )


def summarize_resources(resources: tuple[ResourceClassification, ...]) -> ClassificationSummary:
    sorted_resources = tuple(sorted(resources, key=_resource_sort_key))
    broken = tuple(resource for resource in sorted_resources if resource.state == ResourceState.BROKEN)
    in_progress = tuple(resource for resource in sorted_resources if resource.state == ResourceState.IN_PROGRESS)
    converged = tuple(resource for resource in sorted_resources if resource.state == ResourceState.CONVERGED)

    if broken:
        state = ResourceState.BROKEN
    elif in_progress:
        state = ResourceState.IN_PROGRESS
    else:
        state = ResourceState.CONVERGED

    return ClassificationSummary(state, broken, in_progress, converged, len(resources))


def evaluate_summary(
    *,
    summary: ClassificationSummary,
    previous: ConvergenceState,
    observed_at: datetime,
    stability_threshold: int,
    safety_timeout_seconds: int,
) -> tuple[EvaluationResult, ConvergenceState]:
    if summary.state == ResourceState.BROKEN:
        description = "Failed: " + "; ".join(resource.description for resource in summary.broken)
        next_state = ConvergenceState(last_posted=previous.last_posted, last_seen_sha=previous.last_seen_sha)
        return _result(Verdict.BROKEN, "failure", description, summary.total, next_state), next_state

    if summary.state == ResourceState.IN_PROGRESS:
        first_in_progress_at = previous.first_in_progress_at or observed_at
        elapsed = (observed_at - first_in_progress_at).total_seconds()
        next_state = ConvergenceState(
            consecutive_converged=0,
            first_in_progress_at=first_in_progress_at,
            last_posted=previous.last_posted,
            last_seen_sha=previous.last_seen_sha,
        )
        if elapsed > safety_timeout_seconds:
            description = f"Safety timeout ({safety_timeout_seconds}s) exceeded. Pending: " + "; ".join(
                resource.description for resource in summary.in_progress
            )
            return _result(Verdict.BROKEN, "failure", description, summary.total, next_state), next_state
        description = f"{len(summary.in_progress)} resources pending"
        return _result(Verdict.IN_PROGRESS, "pending", description, summary.total, next_state), next_state

    capped_count = min(previous.consecutive_converged + 1, stability_threshold * 2)
    next_state = ConvergenceState(
        consecutive_converged=capped_count,
        first_in_progress_at=None,
        last_posted=previous.last_posted,
        last_seen_sha=previous.last_seen_sha,
    )
    if capped_count >= stability_threshold:
        description = f"All {summary.total} resources healthy for {capped_count} consecutive checks"
        return _result(Verdict.CONVERGED, "success", description, summary.total, next_state), next_state

    description = f"Healthy {capped_count}/{stability_threshold} — awaiting stability"
    return _result(Verdict.IN_PROGRESS, "pending", description, summary.total, next_state), next_state


def should_post_status(state: ConvergenceState, sha: str | None, github_state: GithubState, description: str) -> bool:
    if sha is None or sha == "":
        return False
    return state.last_posted != PostedStatus(sha=sha, state=github_state, description=description)


def truncate_description(description: str) -> str:
    return description[:140]


def _result(
    verdict: Verdict,
    github_state: GithubState,
    description: str,
    resource_count: int,
    state: ConvergenceState,
) -> EvaluationResult:
    return EvaluationResult(
        verdict=verdict,
        github_state=github_state,
        description=description,
        resource_count=resource_count,
        consecutive_converged=state.consecutive_converged,
        should_write_heartbeat=True,
    )


def _resource_sort_key(resource: ResourceClassification) -> tuple[int, tuple[str, ...]]:
    order = 0 if resource.kind == ResourceKind.APPLICATION else 1
    return order, resource.identity


def _text(value: str | None) -> str:
    if value is None:
        return "null"
    return value


def _bool_text(*, value: bool | None) -> str:
    if value is None:
        return "null"
    return str(value).lower()
