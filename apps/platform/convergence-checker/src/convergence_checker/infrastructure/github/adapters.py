from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from convergence_checker.core.ports import CommitStatus, TokenResponse

if TYPE_CHECKING:
    from convergence_checker.infrastructure.github.repository import GitHubRepository


@dataclass(frozen=True)
class GitHubStatusReporter:
    client: GitHubRepository

    def post(self, status: CommitStatus) -> None:
        self.client.create_commit_status(
            owner_repo=status.owner_repo,
            sha=status.sha,
            state=status.state,
            context=status.context,
            description=status.description,
        )


class NullStatusReporter:
    def post(self, _status: CommitStatus) -> None:
        return


@dataclass(frozen=True)
class StaticTokenProvider:
    token: str

    def get(self) -> TokenResponse:
        return TokenResponse(token=self.token)
