from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kubernetes import client as k8s
from pydantic import BaseModel, ConfigDict, Field

type ConfigMapData = dict[str, str]


class _Meta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    namespace: str = ""


class _Health(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: str | None = None


class _AppSync(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: str | None = None


class _AppOperationState(BaseModel):
    model_config = ConfigDict(extra="ignore")
    phase: str | None = None


class _AppStatus(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    health: _Health = Field(default_factory=_Health)
    sync: _AppSync = Field(default_factory=_AppSync)
    operation_state: _AppOperationState = Field(default_factory=_AppOperationState, alias="operationState")


class K8sApplication(BaseModel):
    model_config = ConfigDict(extra="ignore")
    metadata: _Meta
    status: _AppStatus = Field(default_factory=_AppStatus)


class _Condition(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str
    status: str


class _StageStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    health: _Health = Field(default_factory=_Health)
    conditions: list[_Condition] | None = None


class K8sStage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    metadata: _Meta
    status: _StageStatus = Field(default_factory=_StageStatus)


class K8sProject(BaseModel):
    model_config = ConfigDict(extra="ignore")
    metadata: _Meta


@dataclass(frozen=True)
class K8sRepository:
    core_api: k8s.CoreV1Api
    custom_api: k8s.CustomObjectsApi

    def list_applications(self, namespace: str) -> list[K8sApplication]:
        response: dict[str, Any] = self.custom_api.list_namespaced_custom_object(
            group="argoproj.io",
            version="v1alpha1",
            namespace=namespace,
            plural="applications",
        )
        return [K8sApplication.model_validate(item) for item in response.get("items", [])]

    def list_stages(self, namespace: str) -> list[K8sStage]:
        response: dict[str, Any] = self.custom_api.list_namespaced_custom_object(
            group="kargo.akuity.io",
            version="v1alpha1",
            namespace=namespace,
            plural="stages",
        )
        return [K8sStage.model_validate(item) for item in response.get("items", [])]

    def list_projects(self) -> list[K8sProject]:
        response: dict[str, Any] = self.custom_api.list_cluster_custom_object(
            group="kargo.akuity.io",
            version="v1alpha1",
            plural="projects",
        )
        return [K8sProject.model_validate(item) for item in response.get("items", [])]

    def read_configmap(self, name: str, namespace: str) -> ConfigMapData:
        cm: k8s.V1ConfigMap = self.core_api.read_namespaced_config_map(name=name, namespace=namespace)
        return dict(cm.data) if cm.data else {}

    def patch_configmap(
        self,
        name: str,
        namespace: str,
        data: ConfigMapData,
        field_manager: str,
    ) -> None:
        body = k8s.V1ConfigMap(data=data)
        self.core_api.patch_namespaced_config_map(
            name=name,
            namespace=namespace,
            body=body,
            field_manager=field_manager,
        )
