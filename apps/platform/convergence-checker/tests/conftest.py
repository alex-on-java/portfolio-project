from __future__ import annotations

import pytest

from convergence_checker.models import ApplicationStatus, StageStatus


@pytest.fixture
def healthy_synced_app() -> ApplicationStatus:
    return ApplicationStatus(
        name="web-app-dev",
        health_status="Healthy",
        sync_status="Synced",
        operation_phase="Succeeded",
    )


@pytest.fixture
def degraded_app() -> ApplicationStatus:
    return ApplicationStatus(
        name="web-app-dev",
        health_status="Degraded",
        sync_status="Synced",
        operation_phase="Succeeded",
    )


@pytest.fixture
def progressing_app() -> ApplicationStatus:
    return ApplicationStatus(
        name="web-app-dev",
        health_status="Progressing",
        sync_status="OutOfSync",
        operation_phase="Running",
    )


@pytest.fixture
def healthy_stage() -> StageStatus:
    return StageStatus(
        name="workloads-web-app-dev",
        namespace="portfolio-project",
        health_status="Healthy",
        conditions={"Ready": True, "Healthy": True, "Verified": True},
    )


@pytest.fixture
def unhealthy_stage() -> StageStatus:
    return StageStatus(
        name="workloads-web-app-dev",
        namespace="portfolio-project",
        health_status="Unhealthy",
        conditions={"Ready": False, "Healthy": False},
    )
