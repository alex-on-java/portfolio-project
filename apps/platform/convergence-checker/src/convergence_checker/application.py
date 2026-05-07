from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import sleep
from typing import TYPE_CHECKING, Protocol

import structlog
from kubernetes.client.exceptions import ApiException
from requests import RequestException

from convergence_checker.domain import (
    ApplicationSnapshot,
    ConvergenceState,
    GithubState,
    PostedStatus,
    StageSnapshot,
    classify_application,
    classify_stage,
    evaluate_summary,
    should_post_status,
    summarize_resources,
    truncate_description,
)

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class ClusterIdentity:
    pr_commit_sha: str | None
    argocd_namespace: str


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    check_interval_seconds: int
    stability_threshold: int
    safety_timeout_seconds: int


class ClusterReader(Protocol):
    def read_cluster_identity(self) -> ClusterIdentity: ...

    def list_applications(self, namespace: str) -> tuple[ApplicationSnapshot, ...]: ...

    def list_projects(self) -> tuple[str, ...]: ...

    def list_stages(self, namespaces: tuple[str, ...]) -> tuple[StageSnapshot, ...]: ...


class StatusReporter(Protocol):
    def enabled(self) -> bool: ...

    def post_status(self, *, sha: str, state: str, description: str) -> None: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


class ConvergenceChecker:
    def __init__(
        self,
        *,
        settings: RuntimeSettings,
        cluster_reader: ClusterReader,
        write_heartbeat: Callable[[datetime], None],
        status_reporter: StatusReporter,
        clock: Callable[[], datetime],
    ) -> None:
        self._settings = settings
        self._cluster_reader = cluster_reader
        self._write_heartbeat = write_heartbeat
        self._status_reporter = status_reporter
        self._clock = clock
        self._state = ConvergenceState()
        self._log = structlog.get_logger()

    @property
    def state(self) -> ConvergenceState:
        return self._state

    def run_forever(self) -> None:
        while True:
            started_at = self._clock()
            self.evaluate_once()
            elapsed = (self._clock() - started_at).total_seconds()
            remaining = self._settings.check_interval_seconds - elapsed
            if remaining > 0:
                sleep(remaining)

    def evaluate_once(self) -> None:
        observed_at = self._clock()
        try:
            identity = self._cluster_reader.read_cluster_identity()
            self._state = self._state.with_sha(identity.pr_commit_sha)
            applications = self._cluster_reader.list_applications(identity.argocd_namespace)
            project_namespaces = self._cluster_reader.list_projects()
            stages = self._cluster_reader.list_stages(project_namespaces)
        except (ApiException, RuntimeError, TypeError, ValueError):
            self._log.exception("evaluation_skipped")
            return

        classifications = tuple(classify_application(application) for application in applications) + tuple(
            classify_stage(stage) for stage in stages
        )
        summary = summarize_resources(classifications)
        result, next_state = evaluate_summary(
            summary=summary,
            previous=self._state,
            observed_at=observed_at,
            stability_threshold=self._settings.stability_threshold,
            safety_timeout_seconds=self._settings.safety_timeout_seconds,
        )
        self._state = next_state

        description = truncate_description(result.description)
        if result.github_state is not None and self._status_reporter.enabled():
            self._post_status(identity.pr_commit_sha, result.github_state, description)

        try:
            self._write_heartbeat(observed_at)
        except (ApiException, RuntimeError):
            self._log.exception("heartbeat_write_failed")

        self._log.info(
            "evaluation",
            verdict=result.verdict.value,
            description=description,
            consecutive_converged=result.consecutive_converged,
            resources=result.resource_count,
        )

    def _post_status(self, sha: str | None, github_state: GithubState, description: str) -> None:
        if not should_post_status(self._state, sha, github_state, description):
            return
        if sha is None or sha == "":
            return
        try:
            self._status_reporter.post_status(sha=sha, state=github_state, description=description)
        except (RequestException, RuntimeError, TypeError, ValueError):
            self._log.exception("github_status_post_failed", sha=sha, state=github_state, description=description)
            return
        self._state = self._state.remember_post(
            PostedStatus(sha=sha, state=github_state, description=description),
        )
