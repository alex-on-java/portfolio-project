from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from convergence_checker.infrastructure.config import KubernetesSettings
from convergence_checker.infrastructure.kubernetes import KubernetesGateway


class FakeCoreApi:  # pylint: disable=too-few-public-methods
    def __init__(self) -> None:
        self.api_client = FakeApiClient()

    def read_namespaced_config_map(self, *, name: str, namespace: str) -> SimpleNamespace:
        assert name == "identity-cm"
        assert namespace == "identity-ns"
        return SimpleNamespace(data={"prCommitSha": "sha-a", "argocdNamespace": "argo-system", "ignored": "value"})


class FakeApiClient:  # pylint: disable=too-few-public-methods
    def __init__(self) -> None:
        self.call_api_calls: list[dict[str, object]] = []

    def call_api(
        self,
        resource_path: str,
        method: str,
        path_params: dict[str, str],
        query_params: list[tuple[str, object]],
        header_params: dict[str, str],
        **kwargs: object,
    ) -> None:
        self.call_api_calls.append(
            {
                "resource_path": resource_path,
                "method": method,
                "path_params": path_params,
                "query_params": query_params,
                "header_params": header_params,
                **kwargs,
            },
        )


class FakeCustomApi:
    def list_namespaced_custom_object(self, *, group: str, version: str, namespace: str, plural: str) -> dict[str, Any]:
        if plural == "applications":
            assert group == "argoproj.io"
            assert version == "v1alpha1"
            assert namespace == "argo-system"
            return {
                "items": [
                    {
                        "metadata": {"name": "app-a"},
                        "status": {
                            "health": {"status": "Healthy"},
                            "sync": {"status": "Synced"},
                            "operationState": {"phase": "Succeeded"},
                        },
                    },
                    {"metadata": {"name": "app-b"}, "status": None},
                ],
            }
        assert plural == "stages"
        assert group == "kargo.akuity.io"
        assert version == "v1alpha1"
        assert namespace == "project-a"
        return {
            "items": [
                {
                    "metadata": {"namespace": "project-a", "name": "stage-a"},
                    "status": {
                        "health": {"status": "Healthy"},
                        "conditions": [
                            {"type": "Ready", "status": "True"},
                            {"type": "Healthy", "status": "True"},
                            {"type": "Verified", "status": "False"},
                            {"type": 123, "status": "True"},
                        ],
                    },
                },
            ],
        }

    def list_cluster_custom_object(self, *, group: str, version: str, plural: str) -> dict[str, Any]:
        assert group == "kargo.akuity.io"
        assert version == "v1alpha1"
        assert plural == "projects"
        return {"items": [{"metadata": {"name": "project-b"}}, {"metadata": {"name": "project-a"}}]}


def test_kubernetes_gateway_reads_and_normalizes_unstructured_resources() -> None:
    gateway = KubernetesGateway(core_api=FakeCoreApi(), custom_api=FakeCustomApi(), settings=_settings())

    identity = gateway.read_cluster_identity()
    applications = gateway.list_applications(identity.argocd_namespace)
    projects = gateway.list_projects()
    stages = gateway.list_stages(("project-a",))

    assert identity.pr_commit_sha == "sha-a"
    assert identity.argocd_namespace == "argo-system"
    assert applications[0].name == "app-a"
    assert applications[0].health == "Healthy"
    assert applications[1].health is None
    assert projects == ("project-a", "project-b")
    assert stages[0].namespace == "project-a"
    assert stages[0].ready_condition is True
    assert stages[0].verified_condition is False


def test_kubernetes_gateway_writes_heartbeat_with_server_side_apply_content_type() -> None:
    core_api = FakeCoreApi()
    gateway = KubernetesGateway(core_api=core_api, custom_api=FakeCustomApi(), settings=_settings())

    gateway.write(datetime(2026, 5, 7, 12, 30, tzinfo=UTC))

    assert core_api.api_client.call_api_calls == [
        {
            "resource_path": "/api/v1/namespaces/{namespace}/configmaps/{name}",
            "method": "PATCH",
            "path_params": {"namespace": "observability", "name": "heartbeat-cm"},
            "query_params": [("fieldManager", "field-owner"), ("force", True)],
            "header_params": {"Accept": "application/json", "Content-Type": "application/apply-patch+yaml"},
            "body": {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {"name": "heartbeat-cm", "namespace": "observability"},
                "data": {"last-success": "2026-05-07T12:30:00+00:00"},
            },
            "response_type": "V1ConfigMap",
            "auth_settings": ["BearerToken"],
            "_return_http_data_only": True,
        },
    ]


def _settings() -> KubernetesSettings:
    return KubernetesSettings(
        cluster_identity_namespace="identity-ns",
        cluster_identity_configmap_name="identity-cm",
        heartbeat_namespace="observability",
        heartbeat_configmap_name="heartbeat-cm",
        field_manager_name="field-owner",
    )
