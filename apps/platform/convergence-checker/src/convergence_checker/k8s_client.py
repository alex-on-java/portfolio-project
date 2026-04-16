from __future__ import annotations

from typing import Any

from kubernetes import client as k8s_client


def list_applications(api: k8s_client.CustomObjectsApi, namespace: str) -> list[dict[str, Any]]:
    response: dict[str, Any] = api.list_namespaced_custom_object(
        group="argoproj.io",
        version="v1alpha1",
        namespace=namespace,
        plural="applications",
    )
    items: list[dict[str, Any]] = response.get("items", [])
    return items


def list_stages(api: k8s_client.CustomObjectsApi, namespace: str) -> list[dict[str, Any]]:
    response: dict[str, Any] = api.list_namespaced_custom_object(
        group="kargo.akuity.io",
        version="v1alpha1",
        namespace=namespace,
        plural="stages",
    )
    items: list[dict[str, Any]] = response.get("items", [])
    return items


def list_projects(api: k8s_client.CustomObjectsApi) -> list[dict[str, Any]]:
    response: dict[str, Any] = api.list_cluster_custom_object(
        group="kargo.akuity.io",
        version="v1alpha1",
        plural="projects",
    )
    items: list[dict[str, Any]] = response.get("items", [])
    return items


def read_configmap(
    api: k8s_client.CoreV1Api,
    name: str,
    namespace: str,
) -> dict[str, str]:
    cm: k8s_client.V1ConfigMap = api.read_namespaced_config_map(name=name, namespace=namespace)
    return dict(cm.data) if cm.data else {}


def patch_configmap(
    api: k8s_client.CoreV1Api,
    name: str,
    namespace: str,
    data: dict[str, str],
) -> None:
    body = k8s_client.V1ConfigMap(data=data)
    api.patch_namespaced_config_map(name=name, namespace=namespace, body=body)
