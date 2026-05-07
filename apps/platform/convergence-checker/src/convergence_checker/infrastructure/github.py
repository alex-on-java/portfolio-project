from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import jwt
import requests

if TYPE_CHECKING:
    from collections.abc import Callable

    from convergence_checker.infrastructure.config import GithubAppSettings

GITHUB_API_BASE_URL = "https://api.github.com"
STATUS_CONTEXT = "GitOps Convergence Gate"


class GithubAppTokenProvider:
    def __init__(
        self,
        *,
        app_id: str,
        private_key: str,
        installation_id: str,
        session: requests.Session,
        base_url: str = GITHUB_API_BASE_URL,
    ) -> None:
        self._app_id = app_id
        self._private_key = private_key
        self._installation_id = installation_id
        self._session = session
        self._base_url = base_url
        self._cached_token: tuple[str, datetime] | None = None

    def token(self) -> str:
        now = datetime.now(UTC)
        if self._cached_token is not None:
            token_value, expires_at = self._cached_token
            if expires_at - now > timedelta(minutes=5):
                return token_value

        jwt_token = self._jwt(now)
        response = self._session.post(
            f"{self._base_url}/app/installations/{self._installation_id}/access_tokens",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {jwt_token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        token = _required_string(payload, "token")
        expires_at = datetime.fromisoformat(_required_string(payload, "expires_at"))
        self._cached_token = (token, expires_at)
        return token

    def clear_cache(self) -> None:
        self._cached_token = None

    def _jwt(self, now: datetime) -> str:
        payload = {
            "iat": int((now - timedelta(seconds=60)).timestamp()),
            "exp": int((now + timedelta(minutes=9)).timestamp()),
            "iss": self._app_id,
        }
        return jwt.encode(payload, self._private_key, algorithm="RS256")


class DisabledGithubStatusReporter:
    def enabled(self) -> bool:
        return False

    def post_status(self, *, sha: str, state: str, description: str) -> None:
        _ = (sha, state, description)
        msg = "GitHub status posting is disabled"
        raise RuntimeError(msg)


class GithubStatusReporter:
    def __init__(
        self,
        *,
        owner_repo: str,
        token_provider: Callable[[], str],
        session: requests.Session,
        base_url: str = GITHUB_API_BASE_URL,
    ) -> None:
        self._owner_repo = owner_repo
        self._get_token = token_provider
        self._session = session
        self._base_url = base_url

    @classmethod
    def from_settings(cls, settings: GithubAppSettings) -> GithubStatusReporter | DisabledGithubStatusReporter:
        session = requests.Session()
        if not settings.posting_enabled:
            return DisabledGithubStatusReporter()
        if settings.app_id is None or settings.private_key is None or settings.installation_id is None:
            return DisabledGithubStatusReporter()
        token_provider = GithubAppTokenProvider(
            app_id=settings.app_id,
            private_key=settings.private_key,
            installation_id=settings.installation_id,
            session=session,
        )
        return cls(owner_repo=settings.owner_repo, token_provider=token_provider.token, session=session)

    def enabled(self) -> bool:
        return True

    def post_status(self, *, sha: str, state: str, description: str) -> None:
        response = self._session.post(
            f"{self._base_url}/repos/{self._owner_repo}/statuses/{sha}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._get_token()}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={
                "state": state,
                "context": STATUS_CONTEXT,
                "description": description,
            },
            timeout=10,
        )
        response.raise_for_status()


def _required_string(payload: object, key: str) -> str:
    if not isinstance(payload, dict):
        msg = "GitHub response payload must be an object"
        raise TypeError(msg)
    value = payload.get(key)
    if not isinstance(value, str) or value == "":
        msg = f"GitHub response missing required string key: {key}"
        raise ValueError(msg)
    return value
