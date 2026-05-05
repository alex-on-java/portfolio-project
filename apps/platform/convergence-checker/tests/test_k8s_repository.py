from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from kubernetes import client as k8s_client
from pydantic import ValidationError

from convergence_checker.infrastructure.kubernetes.repository import (
    K8sApplication,
    K8sProject,
    K8sRepository,
    K8sStage,
)

# ---------------------------------------------------------------------------
# K8sApplication DTO parsing
# ---------------------------------------------------------------------------


class TestK8sApplicationParsing:
    def test_happy_path_all_fields_present(self) -> None:
        app = K8sApplication.model_validate(
            {
                "metadata": {"name": "web-app-dev", "namespace": "argocd"},
                "status": {
                    "health": {"status": "Healthy"},
                    "sync": {"status": "Synced"},
                    "operationState": {"phase": "Succeeded"},
                },
            }
        )
        assert app.metadata.name == "web-app-dev"
        assert app.status.health.status == "Healthy"
        assert app.status.sync.status == "Synced"
        assert app.status.operation_state.phase == "Succeeded"

    def test_missing_status_block_yields_none_fields(self) -> None:
        app = K8sApplication.model_validate({"metadata": {"name": "test"}})
        assert app.metadata.name == "test"
        assert app.status.health.status is None
        assert app.status.sync.status is None
        assert app.status.operation_state.phase is None

    def test_extra_fields_in_status_are_ignored(self) -> None:
        app = K8sApplication.model_validate(
            {
                "metadata": {"name": "test"},
                "status": {
                    "health": {"status": "Progressing"},
                    "sync": {"status": "OutOfSync"},
                    "conditions": None,
                    "unexpected": "value",
                },
            }
        )
        assert app.status.health.status == "Progressing"
        assert app.status.sync.status == "OutOfSync"

    def test_empty_status_string_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            K8sApplication.model_validate(
                {
                    "metadata": {"name": "test"},
                    "status": {"health": {"status": ""}},
                }
            )

    def test_whitespace_status_string_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            K8sApplication.model_validate(
                {
                    "metadata": {"name": "test"},
                    "status": {"sync": {"status": " "}},
                }
            )

    def test_missing_metadata_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            K8sApplication.model_validate({})

    def test_non_dict_metadata_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            K8sApplication.model_validate({"metadata": "not-a-dict"})

    def test_non_dict_status_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            K8sApplication.model_validate({"metadata": {"name": "n"}, "status": ["unexpected", "list"]})


# ---------------------------------------------------------------------------
# K8sStage DTO parsing
# ---------------------------------------------------------------------------


class TestK8sStageParsing:
    def test_happy_path_all_conditions_true(self) -> None:
        stage = K8sStage.model_validate(
            {
                "metadata": {"name": "workloads-web-app-dev", "namespace": "portfolio-project"},
                "status": {
                    "health": {"status": "Healthy"},
                    "conditions": [
                        {"type": "Ready", "status": "True"},
                        {"type": "Healthy", "status": "True"},
                        {"type": "Verified", "status": "True"},
                    ],
                },
            }
        )
        assert stage.metadata.name == "workloads-web-app-dev"
        assert stage.metadata.namespace == "portfolio-project"
        assert stage.status.health.status == "Healthy"
        assert stage.status.conditions is not None
        assert len(stage.status.conditions) == 3
        assert all(c.status == "True" for c in stage.status.conditions)

    def test_unhealthy_with_false_conditions(self) -> None:
        stage = K8sStage.model_validate(
            {
                "metadata": {"name": "test", "namespace": "ns"},
                "status": {
                    "health": {"status": "Unhealthy"},
                    "conditions": [
                        {"type": "Ready", "status": "False"},
                        {"type": "Healthy", "status": "False"},
                    ],
                },
            }
        )
        assert stage.status.health.status == "Unhealthy"
        assert stage.status.conditions is not None
        assert stage.status.conditions[0].status == "False"

    def test_missing_status_block_yields_none_health_and_none_conditions(self) -> None:
        stage = K8sStage.model_validate({"metadata": {"name": "test", "namespace": "ns"}})
        assert stage.status.health.status is None
        assert stage.status.conditions is None

    def test_empty_conditions_list(self) -> None:
        stage = K8sStage.model_validate(
            {
                "metadata": {"name": "test", "namespace": "ns"},
                "status": {"health": {"status": "Healthy"}, "conditions": []},
            }
        )
        assert stage.status.conditions == []

    def test_null_conditions_parsed_as_none(self) -> None:
        stage = K8sStage.model_validate(
            {
                "metadata": {"name": "test", "namespace": "ns"},
                "status": {"conditions": None},
            }
        )
        assert stage.status.conditions is None

    def test_unknown_condition_status_accepted_in_dto(self) -> None:
        stage = K8sStage.model_validate(
            {
                "metadata": {"name": "test", "namespace": "ns"},
                "status": {
                    "conditions": [
                        {"type": "Ready", "status": "True"},
                        {"type": "Healthy", "status": "Unknown"},
                    ]
                },
            }
        )
        assert stage.status.conditions is not None
        statuses = {c.type: c.status for c in stage.status.conditions}
        assert statuses == {"Ready": "True", "Healthy": "Unknown"}

    def test_blank_condition_status_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            K8sStage.model_validate(
                {
                    "metadata": {"name": "test", "namespace": "ns"},
                    "status": {"conditions": [{"type": "Ready", "status": ""}]},
                }
            )

    def test_malformed_condition_missing_required_fields_raises(self) -> None:
        with pytest.raises(ValidationError):
            K8sStage.model_validate(
                {
                    "metadata": {"name": "test", "namespace": "ns"},
                    "status": {"conditions": [{"bad": "entry"}]},
                }
            )

    def test_missing_metadata_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            K8sStage.model_validate({})

    def test_non_dict_metadata_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            K8sStage.model_validate({"metadata": ["not", "a", "dict"], "status": {}})

    def test_non_dict_status_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            K8sStage.model_validate({"metadata": {"name": "n", "namespace": "ns"}, "status": "not-a-dict"})


# ---------------------------------------------------------------------------
# K8sProject DTO parsing
# ---------------------------------------------------------------------------


class TestK8sProjectParsing:
    def test_happy_path(self) -> None:
        project = K8sProject.model_validate({"metadata": {"name": "portfolio-project"}})
        assert project.metadata.name == "portfolio-project"

    def test_missing_metadata_raises(self) -> None:
        with pytest.raises(ValidationError):
            K8sProject.model_validate({})


# ---------------------------------------------------------------------------
# K8sRepository methods
# ---------------------------------------------------------------------------


class TestK8sRepositoryPatchConfigmap:
    def test_propagates_field_manager_and_data_to_sdk(self) -> None:
        core = MagicMock(spec=k8s_client.CoreV1Api)
        custom = MagicMock(spec=k8s_client.CustomObjectsApi)
        repo = K8sRepository(core_api=core, custom_api=custom)

        repo.patch_configmap(
            name="any-cm",
            namespace="any-ns",
            data={"k": "v"},
            field_manager="test-manager",
        )

        core.patch_namespaced_config_map.assert_called_once()
        kwargs = core.patch_namespaced_config_map.call_args.kwargs
        assert kwargs["field_manager"] == "test-manager"
        assert kwargs["name"] == "any-cm"
        assert kwargs["namespace"] == "any-ns"
        assert kwargs["body"].data == {"k": "v"}


class TestK8sRepositoryReadConfigmap:
    def test_returns_configmap_data(self) -> None:
        core = MagicMock(spec=k8s_client.CoreV1Api)
        core.read_namespaced_config_map.return_value = MagicMock(data={"key": "value"})
        repo = K8sRepository(core_api=core, custom_api=MagicMock())

        result = repo.read_configmap(name="cm", namespace="ns")

        assert result == {"key": "value"}
        core.read_namespaced_config_map.assert_called_once_with(name="cm", namespace="ns")

    def test_none_data_returns_empty_dict(self) -> None:
        core = MagicMock(spec=k8s_client.CoreV1Api)
        core.read_namespaced_config_map.return_value = MagicMock(data=None)
        repo = K8sRepository(core_api=core, custom_api=MagicMock())

        assert repo.read_configmap(name="cm", namespace="ns") == {}


class TestK8sRepositoryListApplications:
    def test_parses_items_into_k8s_application_dtos(self) -> None:
        custom = MagicMock(spec=k8s_client.CustomObjectsApi)
        custom.list_namespaced_custom_object.return_value = {
            "items": [
                {
                    "metadata": {"name": "app-A"},
                    "status": {
                        "health": {"status": "Healthy"},
                        "sync": {"status": "Synced"},
                        "operationState": {"phase": "Succeeded"},
                    },
                }
            ]
        }
        repo = K8sRepository(core_api=MagicMock(), custom_api=custom)

        apps = repo.list_applications("argocd")

        assert len(apps) == 1
        assert apps[0].metadata.name == "app-A"
        assert apps[0].status.health.status == "Healthy"
        custom.list_namespaced_custom_object.assert_called_once_with(
            group="argoproj.io",
            version="v1alpha1",
            namespace="argocd",
            plural="applications",
        )

    def test_empty_items_list_returns_empty(self) -> None:
        custom = MagicMock(spec=k8s_client.CustomObjectsApi)
        custom.list_namespaced_custom_object.return_value = {"items": []}
        repo = K8sRepository(core_api=MagicMock(), custom_api=custom)

        assert repo.list_applications("argocd") == []


class TestK8sRepositoryListStages:
    def test_parses_items_into_k8s_stage_dtos(self) -> None:
        custom = MagicMock(spec=k8s_client.CustomObjectsApi)
        custom.list_namespaced_custom_object.return_value = {
            "items": [
                {
                    "metadata": {"name": "stage-A", "namespace": "proj"},
                    "status": {
                        "health": {"status": "Healthy"},
                        "conditions": [{"type": "Ready", "status": "True"}],
                    },
                }
            ]
        }
        repo = K8sRepository(core_api=MagicMock(), custom_api=custom)

        stages = repo.list_stages("proj")

        assert len(stages) == 1
        assert stages[0].metadata.name == "stage-A"
        assert stages[0].metadata.namespace == "proj"
        custom.list_namespaced_custom_object.assert_called_once_with(
            group="kargo.akuity.io",
            version="v1alpha1",
            namespace="proj",
            plural="stages",
        )


class TestK8sRepositoryListProjects:
    def test_parses_items_into_k8s_project_dtos(self) -> None:
        custom = MagicMock(spec=k8s_client.CustomObjectsApi)
        custom.list_cluster_custom_object.return_value = {
            "items": [
                {"metadata": {"name": "project-A"}},
                {"metadata": {"name": "project-B"}},
            ]
        }
        repo = K8sRepository(core_api=MagicMock(), custom_api=custom)

        projects = repo.list_projects()

        assert len(projects) == 2
        assert [p.metadata.name for p in projects] == ["project-A", "project-B"]
        custom.list_cluster_custom_object.assert_called_once_with(
            group="kargo.akuity.io",
            version="v1alpha1",
            plural="projects",
        )
