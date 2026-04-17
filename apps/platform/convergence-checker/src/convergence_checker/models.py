from __future__ import annotations

from datetime import datetime  # noqa: TC003  # Pydantic resolves annotations at runtime
from enum import StrEnum

from pydantic import BaseModel


class EvaluationVerdict(StrEnum):
    HEALTHY = "healthy"
    PENDING = "pending"
    FAILURE = "failure"


class EvaluationResult(BaseModel):
    verdict: EvaluationVerdict
    description: str


class ApplicationStatus(BaseModel):
    name: str
    health_status: str | None = None
    sync_status: str | None = None
    operation_phase: str | None = None

    @classmethod
    def from_resource(cls, resource: dict[str, object]) -> ApplicationStatus:
        metadata = resource.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        name_raw = metadata.get("name", "<unknown>")
        name = str(name_raw)

        status = resource.get("status", {})
        if not isinstance(status, dict):
            status = {}

        health = status.get("health", {})
        health_status = health.get("status") if isinstance(health, dict) else None

        sync = status.get("sync", {})
        sync_status = sync.get("status") if isinstance(sync, dict) else None

        op_state = status.get("operationState", {})
        operation_phase = op_state.get("phase") if isinstance(op_state, dict) else None

        return cls(
            name=name,
            health_status=str(health_status) if health_status is not None else None,
            sync_status=str(sync_status) if sync_status is not None else None,
            operation_phase=str(operation_phase) if operation_phase is not None else None,
        )


class StageStatus(BaseModel):
    name: str
    namespace: str
    health_status: str | None = None
    conditions: dict[str, bool] = {}

    @classmethod
    def from_resource(cls, resource: dict[str, object]) -> StageStatus:
        metadata = resource.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        name = str(metadata.get("name", "<unknown>"))
        namespace = str(metadata.get("namespace", "<unknown>"))

        status = resource.get("status", {})
        if not isinstance(status, dict):
            status = {}

        health = status.get("health", {})
        health_status = health.get("status") if isinstance(health, dict) else None

        conditions_raw = status.get("conditions", [])
        conditions: dict[str, bool] = {}
        if isinstance(conditions_raw, list):
            for cond in conditions_raw:
                if isinstance(cond, dict):
                    ctype = cond.get("type")
                    cstatus = cond.get("status")
                    if isinstance(ctype, str) and isinstance(cstatus, str) and cstatus in ("True", "False"):
                        conditions[ctype] = cstatus == "True"

        return cls(
            name=name,
            namespace=namespace,
            health_status=str(health_status) if health_status is not None else None,
            conditions=conditions,
        )


class ConvergenceState(BaseModel):
    consecutive_healthy: int = 0
    first_pending_at: datetime | None = None
    last_commit_sha: str | None = None
