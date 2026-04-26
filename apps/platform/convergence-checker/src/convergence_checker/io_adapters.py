from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol

import structlog
from kubernetes import client as k8s_client

from convergence_checker import k8s_client as k8s
from convergence_checker.models import (
    ApplicationStatus,
    ConvergenceState,
    StageStatus,
)

if TYPE_CHECKING:
    from datetime import datetime

    from convergence_checker.github_client import GitHubAppClient

log: structlog.stdlib.BoundLogger = structlog.get_logger()


class ClusterReader(Protocol):
    def read_cluster_identity(self) -> dict[str, str]: ...
    def list_applications(self) -> list[ApplicationStatus]: ...
    def list_stage_namespaces(self) -> list[str]: ...
    def list_stages(self, namespace: str) -> list[StageStatus]: ...
    def read_state(self) -> ConvergenceState: ...
    def write_state(self, state: ConvergenceState) -> None: ...
    def write_heartbeat(self, now: datetime) -> None: ...


class StatusReporter(Protocol):
    def post(
        self,
        *,
        owner_repo: str,
        sha: str,
        state: str,
        context: str,
        description: str,
    ) -> None: ...


class TokenProvider(Protocol):
    def get(self) -> str: ...


@dataclass(frozen=True)
class K8sClusterReader:
    core_api: k8s_client.CoreV1Api
    custom_api: k8s_client.CustomObjectsApi
    own_namespace: str
    cluster_identity_namespace: str
    cluster_identity_configmap_name: str
    state_configmap_name: str
    heartbeat_configmap_name: str
    argocd_namespace: str | None = None

    def with_argocd_namespace(self, argocd_namespace: str) -> K8sClusterReader:
        return replace(self, argocd_namespace=argocd_namespace)

    def read_cluster_identity(self) -> dict[str, str]:
        return k8s.read_configmap(
            self.core_api,
            name=self.cluster_identity_configmap_name,
            namespace=self.cluster_identity_namespace,
        )

    def list_applications(self) -> list[ApplicationStatus]:
        if self.argocd_namespace is None:
            msg = "argocd_namespace must be bound before calling list_applications"
            raise RuntimeError(msg)
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

    def read_state(self) -> ConvergenceState:
        try:
            data = k8s.read_configmap(
                self.core_api,
                name=self.state_configmap_name,
                namespace=self.own_namespace,
            )
            raw = data.get("state")
            if raw:
                return ConvergenceState.model_validate_json(raw)
        except (KeyError, ValueError, k8s_client.ApiException):
            log.debug("state_configmap_not_found_or_invalid")
        return ConvergenceState()

    def write_state(self, state: ConvergenceState) -> None:
        k8s.patch_configmap(
            self.core_api,
            name=self.state_configmap_name,
            namespace=self.own_namespace,
            data={"state": state.model_dump_json()},
        )

    def write_heartbeat(self, now: datetime) -> None:
        k8s.patch_configmap(
            self.core_api,
            name=self.heartbeat_configmap_name,
            namespace=self.own_namespace,
            data={"last-success": now.isoformat()},
        )


@dataclass(frozen=True)
class GitHubStatusReporter:
    client: GitHubAppClient

    def post(
        self,
        *,
        owner_repo: str,
        sha: str,
        state: str,
        context: str,
        description: str,
    ) -> None:
        self.client.create_commit_status(
            owner_repo=owner_repo,
            sha=sha,
            state=state,
            context=context,
            description=description,
        )


class NullStatusReporter:
    def post(
        self,
        *,
        owner_repo: str,  # noqa: ARG002
        sha: str,  # noqa: ARG002
        state: str,  # noqa: ARG002
        context: str,  # noqa: ARG002
        description: str,  # noqa: ARG002
    ) -> None:
        return


@dataclass(frozen=True)
class StaticTokenProvider:
    token: str

    def get(self) -> str:
        return self.token
