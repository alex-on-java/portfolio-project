from __future__ import annotations

from datetime import datetime
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


class StageStatus(BaseModel):
    name: str
    namespace: str
    health_status: str | None = None
    conditions: dict[str, bool] = {}


class ConvergenceState(BaseModel):
    consecutive_healthy: int = 0
    first_pending_at: datetime | None = None


class CycleInputs(BaseModel):
    previous_state: ConvergenceState
    previous_commit_sha: str | None = None
    previous_sent_status: tuple[str, str] | None = None
    dry_run: bool = False


class CycleOutputs(BaseModel):
    new_state: ConvergenceState
    new_commit_sha: str | None = None
    new_sent_status: tuple[str, str] | None = None
    result: EvaluationResult
    resource_count: int
