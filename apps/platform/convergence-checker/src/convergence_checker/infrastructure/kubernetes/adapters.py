from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

from adaptix.conversion import ConversionRetort, link_function
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from convergence_checker.core.models import (
    ApplicationStatus,
    ClusterIdentity,
    ConditionFalse,
    ConditionTrue,
    ConditionUnknown,
    KnownCommit,
    MissingStatus,
    NoCommit,
    NoOperationPhase,
    OperationPhase,
    ReportedStatus,
    ResourceStatus,
    StageCondition,
    StageStatus,
)
from convergence_checker.infrastructure.kubernetes.repository import K8sApplication, K8sStage

if TYPE_CHECKING:
    from datetime import datetime

    from convergence_checker.core.ports import ClusterIdentityReader
    from convergence_checker.infrastructure.kubernetes.repository import K8sRepository

type NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ClusterIdentityConfigMap(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    argocd_namespace: NonBlankString = Field(alias="argocdNamespace")
    pr_commit_sha: NonBlankString | None = Field(default=None, alias="prCommitSha")


def _map_cluster_identity(data: dict[str, str]) -> ClusterIdentity:
    dto = ClusterIdentityConfigMap.model_validate(data)
    commit = (
        KnownCommit(sha=dto.pr_commit_sha) if dto.pr_commit_sha is not None else NoCommit(reason="prCommitSha absent")
    )
    return ClusterIdentity(argocd_namespace=dto.argocd_namespace, commit=commit)


def _resource_status(value: str | None, *, source: str) -> ResourceStatus:
    if value is None:
        return MissingStatus(source=source)
    return ReportedStatus(value=value)


def _operation_phase(value: str | None) -> OperationPhase:
    if value is None:
        return NoOperationPhase()
    return ReportedStatus(value=value)


def _stage_condition(value: str) -> StageCondition:
    if value == "True":
        return ConditionTrue()
    if value == "False":
        return ConditionFalse()
    return ConditionUnknown(value=value)


def _stage_conditions(dto: K8sStage) -> dict[str, StageCondition]:
    conditions = dto.status.conditions
    return {condition.type: _stage_condition(condition.status) for condition in conditions or []}


_APPLICATION_RETORT = ConversionRetort(
    recipe=[
        link_function(lambda dto: dto.metadata.name, "name"),
        link_function(
            lambda dto: _resource_status(dto.status.health.status, source="application health"), "health_status"
        ),
        link_function(lambda dto: _resource_status(dto.status.sync.status, source="application sync"), "sync_status"),
        link_function(lambda dto: _operation_phase(dto.status.operation_state.phase), "operation_phase"),
    ],
)

_STAGE_RETORT = ConversionRetort(
    recipe=[
        link_function(lambda dto: dto.metadata.name, "name"),
        link_function(lambda dto: dto.metadata.namespace, "namespace"),
        link_function(lambda dto: _resource_status(dto.status.health.status, source="stage health"), "health_status"),
        link_function(_stage_conditions, "conditions"),
    ],
)


@dataclass(frozen=True)
class K8sClusterIdentityReader:
    repo: K8sRepository
    namespace: str
    configmap_name: str

    def read_cluster_identity(self) -> ClusterIdentity:
        data = self.repo.read_configmap(
            name=self.configmap_name,
            namespace=self.namespace,
        )
        return _map_cluster_identity(data)


@dataclass(frozen=True)
class K8sClusterReader:
    identity_reader: ClusterIdentityReader
    repo: K8sRepository
    own_namespace: str
    argocd_namespace: str
    heartbeat_configmap_name: str
    field_manager_name: str

    def read_cluster_identity(self) -> ClusterIdentity:
        return self.identity_reader.read_cluster_identity()

    def list_applications(self) -> list[ApplicationStatus]:
        converter = _APPLICATION_RETORT.get_converter(K8sApplication, ApplicationStatus)
        return [converter(dto) for dto in self.repo.list_applications(self.argocd_namespace)]

    def list_stage_namespaces(self) -> list[str]:
        return [p.metadata.name for p in self.repo.list_projects()]

    def list_stages(self, namespace: str) -> list[StageStatus]:
        converter = _STAGE_RETORT.get_converter(K8sStage, StageStatus)
        return [converter(dto) for dto in self.repo.list_stages(namespace)]

    def write_heartbeat(self, now: datetime) -> None:
        self.repo.patch_configmap(
            name=self.heartbeat_configmap_name,
            namespace=self.own_namespace,
            data={"last-success": now.isoformat()},
            field_manager=self.field_manager_name,
        )
