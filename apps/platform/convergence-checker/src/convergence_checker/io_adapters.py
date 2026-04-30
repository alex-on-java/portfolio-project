from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import structlog

from convergence_checker import k8s_client as k8s
from convergence_checker.models import (
    ApplicationStatus,
    StageStatus,
)

if TYPE_CHECKING:
    from datetime import datetime

    from kubernetes import client as k8s_client

    from convergence_checker.github_client import GitHubAppClient

log: structlog.stdlib.BoundLogger = structlog.get_logger()


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
    def get(self) -> str: ...


@dataclass(frozen=True)
class K8sClusterIdentityReader:
    core_api: k8s_client.CoreV1Api
    namespace: str
    configmap_name: str

    def read_cluster_identity(self) -> dict[str, str]:
        return k8s.read_configmap(
            self.core_api,
            name=self.configmap_name,
            namespace=self.namespace,
        )


@dataclass(frozen=True)
class K8sClusterReader:
    identity_reader: ClusterIdentityReader
    core_api: k8s_client.CoreV1Api
    custom_api: k8s_client.CustomObjectsApi
    own_namespace: str
    argocd_namespace: str
    heartbeat_configmap_name: str
    field_manager_name: str

    def read_cluster_identity(self) -> dict[str, str]:
        return self.identity_reader.read_cluster_identity()

    def list_applications(self) -> list[ApplicationStatus]:
        raw_items = k8s.list_applications(self.custom_api, self.argocd_namespace)
        return [ApplicationStatus.from_resource(r) for r in raw_items]

    def list_stage_namespaces(self) -> list[str]:
        projects = k8s.list_projects(self.custom_api)
        namespaces: list[str] = []
        for project in projects:
            metadata = project.get("metadata", {})
            if isinstance(metadata, dict):
                name = metadata.get("name")
                if isinstance(name, str):
                    namespaces.append(name)
        return namespaces

    def list_stages(self, namespace: str) -> list[StageStatus]:
        raw_items = k8s.list_stages(self.custom_api, namespace)
        return [StageStatus.from_resource(r) for r in raw_items]

    def write_heartbeat(self, now: datetime) -> None:
        k8s.patch_configmap(
            self.core_api,
            name=self.heartbeat_configmap_name,
            namespace=self.own_namespace,
            data={"last-success": now.isoformat()},
            field_manager=self.field_manager_name,
        )


@dataclass(frozen=True)
class GitHubStatusReporter:
    client: GitHubAppClient

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

    def get(self) -> str:
        return self.token
