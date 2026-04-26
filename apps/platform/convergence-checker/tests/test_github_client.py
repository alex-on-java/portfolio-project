from __future__ import annotations

from unittest.mock import MagicMock, patch

from convergence_checker.github_client import GitHubAppClient
from convergence_checker.io_adapters import StaticTokenProvider


class TestGitHubAppClient:
    def test_create_commit_status(self) -> None:
        client = GitHubAppClient(StaticTokenProvider("ghs_test"))

        with patch("convergence_checker.github_client.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            client.create_commit_status(
                owner_repo="owner/repo",
                sha="abc123",
                state="success",
                context="GitOps Convergence Gate",
                description="All healthy",
            )

        assert mock_post.call_count == 1
        status_call = mock_post.call_args_list[0]
        assert "statuses/abc123" in status_call.args[0]
        body = status_call.kwargs.get("json", status_call[1].get("json", {}))
        assert body["state"] == "success"
        assert body["context"] == "GitOps Convergence Gate"
