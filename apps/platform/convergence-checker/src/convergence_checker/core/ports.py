from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from datetime import datetime

    from convergence_checker.core.models import ApplicationStatus, StageStatus


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    token: str = Field(min_length=1)


@dataclass(frozen=True)
class CommitStatus:
    owner_repo: str
    sha: str
    state: str
    context: str
    description: str


class ClusterIdentityReader(Protocol):
    def read_cluster_identity(self) -> dict[str, str]: ...


class ClusterReader(Protocol):
    def read_cluster_identity(self) -> dict[str, str]: ...
    def list_applications(self) -> list[ApplicationStatus]: ...
    def list_stage_namespaces(self) -> list[str]: ...
    def list_stages(self, namespace: str) -> list[StageStatus]: ...
    def write_heartbeat(self, now: datetime) -> None: ...


class StatusReporter(Protocol):
    def post(self, status: CommitStatus) -> None: ...


class TokenProvider(Protocol):
    def get(self) -> TokenResponse: ...
