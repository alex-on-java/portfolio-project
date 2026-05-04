from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from convergence_checker.core.models import ApplicationStatus, StageStatus

if TYPE_CHECKING:
    from datetime import datetime

    from convergence_checker.core.ports import ClusterIdentityReader
    from convergence_checker.infrastructure.kubernetes.repository import K8sRepository


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
