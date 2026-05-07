from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import responses
from requests import Session

from convergence_checker.infrastructure.config import GithubAppSettings
from convergence_checker.infrastructure.github import STATUS_CONTEXT, GithubAppTokenProvider, GithubStatusReporter

if TYPE_CHECKING:
    import pytest


@responses.activate
def test_status_reporter_posts_commit_status_without_target_url() -> None:
    responses.post("https://api.example.test/repos/example/project/statuses/abc123", json={}, status=201)
    token_calls = 0

    def token_provider() -> str:
        nonlocal token_calls
        token_calls += 1
        return "installation-token"

    reporter = GithubStatusReporter(
        owner_repo="example/project",
        token_provider=token_provider,
        session=Session(),
        base_url="https://api.example.test",
    )

    reporter.post_status(sha="abc123", state="success", description="All 1 resources healthy for 5 consecutive checks")

    request = responses.calls[0].request
    assert request.headers["Authorization"] == "Bearer installation-token"
    assert request.body is not None
    assert _json_body(request.body) == {
        "state": "success",
        "context": STATUS_CONTEXT,
        "description": "All 1 resources healthy for 5 consecutive checks",
    }
    assert token_calls == 1


@responses.activate
def test_token_provider_caches_installation_token(monkeypatch: pytest.MonkeyPatch) -> None:
    responses.post(
        "https://api.example.test/app/installations/456/access_tokens",
        json={
            "token": "installation-token",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        },
        status=201,
    )
    monkeypatch.setattr("jwt.encode", lambda *_args, **_kwargs: "jwt-token")
    provider = GithubAppTokenProvider(
        app_id="123",
        private_key="private-key",
        installation_id="456",
        session=Session(),
        base_url="https://api.example.test",
    )

    assert provider.token() == "installation-token"
    assert provider.token() == "installation-token"

    assert len(responses.calls) == 1
    assert responses.calls[0].request.headers["Authorization"] == "Bearer jwt-token"


def test_from_settings_returns_disabled_reporter_without_complete_credentials() -> None:
    reporter = GithubStatusReporter.from_settings(
        GithubAppSettings(owner_repo="example/project", app_id="123", private_key=None, installation_id="456"),
    )

    assert not reporter.enabled()


def _json_body(body: bytes | str) -> dict[str, Any]:
    if isinstance(body, bytes):
        return json.loads(body.decode("utf-8"))
    return json.loads(body)
