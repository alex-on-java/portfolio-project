from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, cast

from kubernetes import client, config

from convergence_checker.application import ClusterIdentity
from convergence_checker.domain import ApplicationSnapshot, StageSnapshot

if TYPE_CHECKING:
    from datetime import datetime

    from convergence_checker.infrastructure.config import KubernetesSettings

ARGOCD_GROUP = "argoproj.io"
KARGO_GROUP = "kargo.akuity.io"
CRD_VERSION = "v1alpha1"
APPLICATIONS_PLURAL = "applications"
PROJECTS_PLURAL = "projects"
STAGES_PLURAL = "stages"


class KubernetesGateway:
    def __init__(
        self,
        *,
        core_api: client.CoreV1Api,
        custom_api: client.CustomObjectsApi,
        settings: KubernetesSettings,
    ) -> None:
        self._core_api = core_api
        self._custom_api = custom_api
        self._settings = settings

    @classmethod
    def in_cluster(cls, settings: KubernetesSettings) -> KubernetesGateway:
        config.load_incluster_config()
        return cls(core_api=client.CoreV1Api(), custom_api=client.CustomObjectsApi(), settings=settings)

    def read_cluster_identity(self) -> ClusterIdentity:
        configmap = self._core_api.read_namespaced_config_map(
            name=self._settings.cluster_identity_configmap_name,
            namespace=self._settings.cluster_identity_namespace,
        )
        data = configmap.data or {}
        return ClusterIdentity(
            pr_commit_sha=_optional_non_empty(data.get("prCommitSha")),
            argocd_namespace=_optional_non_empty(data.get("argocdNamespace")) or "argocd",
        )

    def list_applications(self, namespace: str) -> tuple[ApplicationSnapshot, ...]:
        payload = self._custom_api.list_namespaced_custom_object(
            group=ARGOCD_GROUP,
            version=CRD_VERSION,
            namespace=namespace,
            plural=APPLICATIONS_PLURAL,
        )
        return tuple(_parse_application(item) for item in _items(payload))

    def list_projects(self) -> tuple[str, ...]:
        payload = self._custom_api.list_cluster_custom_object(
            group=KARGO_GROUP,
            version=CRD_VERSION,
            plural=PROJECTS_PLURAL,
        )
        return tuple(
            sorted(
                name for name in (_string_at(item, "metadata", "name") for item in _items(payload)) if name is not None
            ),
        )

    def list_stages(self, namespaces: tuple[str, ...]) -> tuple[StageSnapshot, ...]:
        stages: list[StageSnapshot] = []
        for namespace in namespaces:
            payload = self._custom_api.list_namespaced_custom_object(
                group=KARGO_GROUP,
                version=CRD_VERSION,
                namespace=namespace,
                plural=STAGES_PLURAL,
            )
            stages.extend(_parse_stage(item) for item in _items(payload))
        return tuple(stages)

    def write(self, observed_at: datetime) -> None:
        body = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": self._settings.heartbeat_configmap_name,
                "namespace": self._settings.heartbeat_namespace,
            },
            "data": {"last-success": observed_at.isoformat()},
        }
        self._core_api.patch_namespaced_config_map(
            name=self._settings.heartbeat_configmap_name,
            namespace=self._settings.heartbeat_namespace,
            body=body,
            field_manager=self._settings.field_manager_name,
            force=True,
            _content_type="application/apply-patch+yaml",
        )


def _parse_application(item: Mapping[str, Any]) -> ApplicationSnapshot:
    name = _string_at(item, "metadata", "name") or "<unknown>"
    return ApplicationSnapshot(
        name=name,
        health=_string_at(item, "status", "health", "status"),
        sync=_string_at(item, "status", "sync", "status"),
        operation=_string_at(item, "status", "operationState", "phase"),
    )


def _parse_stage(item: Mapping[str, Any]) -> StageSnapshot:
    namespace = _string_at(item, "metadata", "namespace") or "<unknown>"
    name = _string_at(item, "metadata", "name") or "<unknown>"
    conditions = _stage_conditions(item)
    return StageSnapshot(
        namespace=namespace,
        name=name,
        health=_string_at(item, "status", "health", "status"),
        healthy_condition=conditions.get("Healthy"),
        ready_condition=conditions.get("Ready"),
        verified_condition=conditions.get("Verified"),
    )


def _stage_conditions(item: Mapping[str, Any]) -> dict[str, bool]:
    status = _mapping_at(item, "status")
    conditions = status.get("conditions") if status is not None else None
    if not isinstance(conditions, list):
        return {}

    extracted: dict[str, bool] = {}
    for condition in conditions:
        if not isinstance(condition, Mapping):
            continue
        condition_type = condition.get("type")
        condition_status = condition.get("status")
        if isinstance(condition_type, str) and condition_status in {"True", "False"}:
            extracted[condition_type] = condition_status == "True"
    return extracted


def _items(payload: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(payload, Mapping):
        return ()
    items = payload.get("items")
    if not isinstance(items, list):
        return ()
    return tuple(cast("Mapping[str, Any]", item) for item in items if isinstance(item, Mapping))


def _string_at(mapping: Mapping[str, Any], *path: str) -> str | None:
    current: object = mapping
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    if isinstance(current, str):
        return current
    return None


def _mapping_at(mapping: Mapping[str, Any], *path: str) -> Mapping[str, Any] | None:
    current: object = mapping
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    if isinstance(current, Mapping):
        return cast("Mapping[str, Any]", current)
    return None


def _optional_non_empty(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return value
