from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.factories import app_status, stage_status

if TYPE_CHECKING:
    from convergence_checker.core.models import ApplicationStatus, StageStatus


@pytest.fixture
def healthy_synced_app() -> ApplicationStatus:
    return app_status(
        name="web-app-dev",
        health="Healthy",
        sync="Synced",
        operation="Succeeded",
    )


@pytest.fixture
def degraded_app() -> ApplicationStatus:
    return app_status(
        name="web-app-dev",
        health="Degraded",
        sync="Synced",
        operation="Succeeded",
    )


@pytest.fixture
def progressing_app() -> ApplicationStatus:
    return app_status(
        name="web-app-dev",
        health="Progressing",
        sync="OutOfSync",
        operation="Running",
    )


@pytest.fixture
def healthy_stage() -> StageStatus:
    return stage_status(
        name="workloads-web-app-dev",
        namespace="portfolio-project",
        health="Healthy",
        conditions={"Ready": True, "Healthy": True, "Verified": True},
    )


@pytest.fixture
def unhealthy_stage() -> StageStatus:
    return stage_status(
        name="workloads-web-app-dev",
        namespace="portfolio-project",
        health="Unhealthy",
        conditions={"Ready": False, "Healthy": False},
    )
