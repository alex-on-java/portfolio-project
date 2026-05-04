from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import jwt
import requests
from cachetools import TTLCache, cached

from convergence_checker.io_adapters import TokenResponse

if TYPE_CHECKING:
    from convergence_checker.io_adapters import TokenProvider

_API_VERSION = "2026-03-10"
_TIMEOUT = 30

_token_cache: TTLCache[object, TokenResponse] = TTLCache(maxsize=1, ttl=3000)


def _headers(token: str, *, bearer: bool = False) -> dict[str, str]:
    prefix = "Bearer" if bearer else "token"
    return {
        "Authorization": f"{prefix} {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": _API_VERSION,
    }


@dataclass(frozen=True)
class GitHubAppTokenProvider:
    app_id: str
    private_key: str
    installation_id: str

    @cached(cache=_token_cache)
    def get(self) -> TokenResponse:
        now = time.time()
        jwt_payload = {
            "iat": int(now) - 60,
            "exp": int(now) + 600,
            "iss": self.app_id,
        }
        encoded_jwt: str = jwt.encode(jwt_payload, self.private_key, algorithm="RS256")
        response = requests.post(
            f"https://api.github.com/app/installations/{self.installation_id}/access_tokens",
            headers=_headers(encoded_jwt, bearer=True),
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        return TokenResponse.model_validate(response.json())


@dataclass(frozen=True)
class GitHubRepository:
    tokens: TokenProvider

    def create_commit_status(
        self,
        owner_repo: str,
        sha: str,
        state: str,
        context: str,
        description: str,
    ) -> None:
        token = self.tokens.get().token
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
