from __future__ import annotations

import time

import jwt
import requests

_API_VERSION = "2026-03-10"
_TIMEOUT = 30
_TOKEN_REFRESH_AFTER_SECONDS = 3000


def _headers(token: str, *, bearer: bool = False) -> dict[str, str]:
    prefix = "Bearer" if bearer else "token"
    return {
        "Authorization": f"{prefix} {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": _API_VERSION,
    }


class GitHubAppClient:
    def __init__(self, app_id: str, private_key: str, installation_id: str) -> None:
        self._app_id = app_id
        self._private_key = private_key
        self._installation_id = installation_id
        self._token: str | None = None
        self._token_expires_at: float = 0

    def _ensure_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expires_at:
            return self._token

        jwt_payload = {
            "iat": int(now) - 60,
            "exp": int(now) + 600,
            "iss": self._app_id,
        }
        encoded_jwt: str = jwt.encode(jwt_payload, self._private_key, algorithm="RS256")

        response = requests.post(
            f"https://api.github.com/app/installations/{self._installation_id}/access_tokens",
            headers=_headers(encoded_jwt, bearer=True),
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        self._token = response.json()["token"]
        self._token_expires_at = now + _TOKEN_REFRESH_AFTER_SECONDS
        return self._token

    def create_commit_status(
        self,
        owner_repo: str,
        sha: str,
        state: str,
        context: str,
        description: str,
    ) -> None:
        token = self._ensure_token()
        response = requests.post(
            f"https://api.github.com/repos/{owner_repo}/statuses/{sha}",
            headers=_headers(token),
            json={
                "state": state,
                "context": context,
                "description": description[:140],
            },
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
