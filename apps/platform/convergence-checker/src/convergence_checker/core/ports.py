from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from attrs import frozen

if TYPE_CHECKING:
    from datetime import datetime

    from convergence_checker.core.models import ApplicationStatus, ClusterIdentity, StageStatus


@frozen
class CommitStatus:
    owner_repo: str
    sha: str
    state: str
    context: str
    description: str


class ClusterIdentityReader(Protocol):
    def read_cluster_identity(self) -> ClusterIdentity: ...


class ClusterReader(Protocol):
    def read_cluster_identity(self) -> ClusterIdentity: ...
    def list_applications(self) -> list[ApplicationStatus]: ...
    def list_stage_namespaces(self) -> list[str]: ...
    def list_stages(self, namespace: str) -> list[StageStatus]: ...
    def write_heartbeat(self, now: datetime) -> None: ...


class StatusReporter(Protocol):
    def post(self, status: CommitStatus) -> None: ...
