from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import structlog
from pydantic import BaseModel, ConfigDict, Field

from convergence_checker.models import (
    ApplicationStatus,
    StageStatus,
)

if TYPE_CHECKING:
    from datetime import datetime

    from convergence_checker.github_repository import GitHubRepository
    from convergence_checker.k8s_repository import K8sRepository

log: structlog.stdlib.BoundLogger = structlog.get_logger()


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    token: str = Field(min_length=1)


@dataclass(frozen=True)
class CommitStatus:
    owner_repo: str
    sha: str
    state: str
    context: str
    description: str


class ClusterIdentityReader(Protocol):
    def read_cluster_identity(self) -> dict[str, str]: ...


class ClusterReader(Protocol):
    def read_cluster_identity(self) -> dict[str, str]: ...
    def list_applications(self) -> list[ApplicationStatus]: ...
    def list_stage_namespaces(self) -> list[str]: ...
    def list_stages(self, namespace: str) -> list[StageStatus]: ...
    def write_heartbeat(self, now: datetime) -> None: ...


class StatusReporter(Protocol):
    def post(self, status: CommitStatus) -> None: ...


class TokenProvider(Protocol):
    def get(self) -> TokenResponse: ...


@dataclass(frozen=True)
class K8sClusterIdentityReader:
    repo: K8sRepository
    namespace: str
    configmap_name: str

    def read_cluster_identity(self) -> dict[str, str]:
        return self.repo.read_configmap(
            name=self.configmap_name,
            namespace=self.namespace,
        )


@dataclass(frozen=True)
class K8sClusterReader:
    identity_reader: ClusterIdentityReader
    repo: K8sRepository
    own_namespace: str
    argocd_namespace: str
    heartbeat_configmap_name: str
    field_manager_name: str

    def read_cluster_identity(self) -> dict[str, str]:
        return self.identity_reader.read_cluster_identity()

    def list_applications(self) -> list[ApplicationStatus]:
        return [
            ApplicationStatus(
                name=dto.metadata.name,
                health_status=dto.status.health.status,
                sync_status=dto.status.sync.status,
                operation_phase=dto.status.operation_state.phase,
            )
            for dto in self.repo.list_applications(self.argocd_namespace)
        ]

    def list_stage_namespaces(self) -> list[str]:
        return [p.metadata.name for p in self.repo.list_projects()]

    def list_stages(self, namespace: str) -> list[StageStatus]:
        return [
            StageStatus(
                name=dto.metadata.name,
                namespace=dto.metadata.namespace,
                health_status=dto.status.health.status,
                conditions={
                    c.type: c.status == "True" for c in (dto.status.conditions or []) if c.status in ("True", "False")
                },
            )
            for dto in self.repo.list_stages(namespace)
        ]

    def write_heartbeat(self, now: datetime) -> None:
        self.repo.patch_configmap(
            name=self.heartbeat_configmap_name,
            namespace=self.own_namespace,
            data={"last-success": now.isoformat()},
            field_manager=self.field_manager_name,
        )


@dataclass(frozen=True)
class GitHubStatusReporter:
    client: GitHubRepository

    def post(self, status: CommitStatus) -> None:
        self.client.create_commit_status(
            owner_repo=status.owner_repo,
            sha=status.sha,
            state=status.state,
            context=status.context,
            description=status.description,
        )


class NullStatusReporter:
    def post(self, _status: CommitStatus) -> None:
        return


@dataclass(frozen=True)
class StaticTokenProvider:
    token: str

    def get(self) -> TokenResponse:
        return TokenResponse(token=self.token)
