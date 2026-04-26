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
