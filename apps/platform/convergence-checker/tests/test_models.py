from __future__ import annotations

from convergence_checker.models import ApplicationStatus, StageStatus


class TestApplicationStatusFromResource:
    def test_healthy_synced_succeeded(self) -> None:
        resource: dict[str, object] = {
            "metadata": {"name": "web-app-dev", "namespace": "argocd"},
            "status": {
                "health": {"status": "Healthy"},
                "sync": {"status": "Synced"},
                "operationState": {"phase": "Succeeded"},
            },
        }
        app = ApplicationStatus.from_resource(resource)
        assert app.name == "web-app-dev"
        assert app.health_status == "Healthy"
        assert app.sync_status == "Synced"
        assert app.operation_phase == "Succeeded"

    def test_missing_status(self) -> None:
        resource: dict[str, object] = {"metadata": {"name": "test"}}
        app = ApplicationStatus.from_resource(resource)
        assert app.name == "test"
        assert app.health_status is None
        assert app.sync_status is None
        assert app.operation_phase is None

    def test_empty_resource(self) -> None:
        app = ApplicationStatus.from_resource({})
        assert app.name == "<unknown>"

    def test_null_conditions(self) -> None:
        resource: dict[str, object] = {
            "metadata": {"name": "test"},
            "status": {
                "health": {"status": "Progressing"},
                "sync": {"status": "OutOfSync"},
                "conditions": None,
            },
        }
        app = ApplicationStatus.from_resource(resource)
        assert app.health_status == "Progressing"
        assert app.sync_status == "OutOfSync"

    def test_non_dict_metadata_yields_unknown_name(self) -> None:
        resource: dict[str, object] = {"metadata": "not-a-dict", "status": {"health": {"status": "Healthy"}}}
        app = ApplicationStatus.from_resource(resource)
        assert app.name == "<unknown>"
        assert app.health_status == "Healthy"

    def test_non_dict_status_yields_no_fields(self) -> None:
        resource: dict[str, object] = {"metadata": {"name": "n"}, "status": ["unexpected", "list"]}
        app = ApplicationStatus.from_resource(resource)
        assert app.name == "n"
        assert app.health_status is None
        assert app.sync_status is None
        assert app.operation_phase is None


class TestStageStatusFromResource:
    def test_healthy_with_conditions(self) -> None:
        resource: dict[str, object] = {
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
        stage = StageStatus.from_resource(resource)
        assert stage.name == "workloads-web-app-dev"
        assert stage.namespace == "portfolio-project"
        assert stage.health_status == "Healthy"
        assert stage.conditions == {"Ready": True, "Healthy": True, "Verified": True}

    def test_unhealthy_with_false_conditions(self) -> None:
        resource: dict[str, object] = {
            "metadata": {"name": "test", "namespace": "ns"},
            "status": {
                "health": {"status": "Unhealthy"},
                "conditions": [
                    {"type": "Ready", "status": "False"},
                    {"type": "Healthy", "status": "False"},
                ],
            },
        }
        stage = StageStatus.from_resource(resource)
        assert stage.health_status == "Unhealthy"
        assert stage.conditions["Ready"] is False
        assert stage.conditions["Healthy"] is False

    def test_missing_status(self) -> None:
        resource: dict[str, object] = {"metadata": {"name": "test", "namespace": "ns"}}
        stage = StageStatus.from_resource(resource)
        assert stage.health_status is None
        assert stage.conditions == {}

    def test_empty_conditions_list(self) -> None:
        resource: dict[str, object] = {
            "metadata": {"name": "test", "namespace": "ns"},
            "status": {"health": {"status": "Healthy"}, "conditions": []},
        }
        stage = StageStatus.from_resource(resource)
        assert stage.conditions == {}

    def test_unknown_condition_excluded(self) -> None:
        resource: dict[str, object] = {
            "metadata": {"name": "test", "namespace": "ns"},
            "status": {
                "conditions": [
                    {"type": "Ready", "status": "True"},
                    {"type": "Healthy", "status": "Unknown"},
                ],
            },
        }
        stage = StageStatus.from_resource(resource)
        assert stage.conditions == {"Ready": True}
        assert "Healthy" not in stage.conditions

    def test_malformed_condition_skipped(self) -> None:
        resource: dict[str, object] = {
            "metadata": {"name": "test", "namespace": "ns"},
            "status": {
                "conditions": [
                    {"type": "Ready", "status": "True"},
                    {"bad": "entry"},
                    "not-a-dict",
                ],
            },
        }
        stage = StageStatus.from_resource(resource)
        assert stage.conditions == {"Ready": True}

    def test_non_dict_metadata_yields_unknown_name_and_namespace(self) -> None:
        resource: dict[str, object] = {"metadata": ["not", "a", "dict"], "status": {}}
        stage = StageStatus.from_resource(resource)
        assert stage.name == "<unknown>"
        assert stage.namespace == "<unknown>"

    def test_non_dict_status_yields_no_health_no_conditions(self) -> None:
        resource: dict[str, object] = {"metadata": {"name": "n", "namespace": "ns"}, "status": "not-a-dict"}
        stage = StageStatus.from_resource(resource)
        assert stage.name == "n"
        assert stage.namespace == "ns"
        assert stage.health_status is None
        assert stage.conditions == {}
