from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from convergence_checker.github_client import GitHubAppClient

_TEST_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAy+/lO89A/DJ9MVgeViYovrp0mjtXhN31qEy92Upn3T8iGmUu
jqvhoVYXr4jq0SPm62we6+HOkbsC2OYxJRLJxXZOv2bFhtNvDcP2nAwgo8OJjScr
yfGjpsBwerm3qno60ROA2JdLwRpH3VXbiHTReps7rLh8PV7DDAtSzgb9C/52J0SO
0zHpTAROwI3sH7LYbK9aS2peMW8jY9nscEfw04yWkOXpy8b9PTKJPrnXEoeo260l
R4DWqrhTXLW7QjvBcSYKfeShDJgWbrdsxNF3TxQTNNpJZH1TpqiyKnEJfTNL2nOd
s1An3iVAs4m51udQq7vqHWOTSOSwexx2u71E7wIDAQABAoIBAASf0TlAPjoLiCZs
HycXC6R5vVM83Vjlp8eHdmSXdWHL/S957N/yUbJ/kRgJl11/rIUuataiUsO8aMpJ
ERFvwCCDSdzVibCHrygHI8xZfH5tsey42A0Rfeb9IYw+3JqwuSzQKK3yY2wxBRZ7
BU2gFykGnRZnQvXwLRcNqK2gSmK7sqLGYEvTnactimzCH9ziROX+nTFClhHVLwhm
xEUB7xPA/VNjnMoSf3Qsp1gUFzPdEA+1m8G/gN62FwOZpoAzXpKCYcvryXOveUXi
JG69HRDPt/X/ura5JHN+18F2LBNOTCiB7JEqNDAG1xVaVJv6ceM01srKCJHl/ngl
LkNdWc0CgYEA64efmTBDy+6UGS++KrPvRl6ZlmeBvKkjcD2Gr4PxR8Swt0lBK+D8
11OZhXAZ6mx/BGwaDVf1nGthaffJRZNmqZ9hdJ9jiemi7KCD+2FfPkPxJSvcyJFM
OIHTT3zTdsPXtS9Clk2GxUkpHk9JjSQQQrlVMBpzM3eRZ6m41Kd+JW0CgYEA3alb
N21U5TF6AFJTv959rT9Bf6fOXsrfOQaRD/Y6X+rB2JKemHl0aVhMvDV4b6gkMvNN
Pp2Q/1BaZRGzDF3cKpuiv8Ex2Yu/brCCRKXgVfp0O1Ou/Sc+wwFGylJTajdTqSxb
+lGQw1QGhLk0CUXj6VyYISiqwR9j2sMwg5RuxksCgYB0HCP9rOF/Q1oXIIYrHxEy
K6ijkNtQWkFyL6KaG/1yV/CWKrLKItwCeuAP/DeKbXogf/pH4bjfJ8CaMOE0P3o4
3K16hKjZcCg1ZtwprNL7KxtSK9FnvtlIchft86d7wQgx9d5pokZyM6LlokisH780
ZZEtaZypHqS76duIWhnB8QKBgQDS3mwCXKYoq1rOt4MownZ4u/aJhI/UqdaVn2Oc
9bcuzFvAtireDpzqIrBNU+jQ//n/5mmTqb3oxP5Zq+7TUu9CMXEwTpAnzsQ8fvpO
aCb0ZCDy13dfKViRlsNLceoc36ldBPAzQCkhSOwykyWntK9Or2GiGdfnhP8vfATJ
CAoh5QKBgBI3s+vcUxX8/P7v+2eZMv+Dxq9Jf2AuDr8U58cUYobGM7aTpe0PMUR8
/S+3lalRfxDrmc2+ZqRTOnM0HckpIvsCjmu8ui+ZcZFliav1i1BFQz5Hga3VtSdH
m44TQYW8NGAVUpMuQKBxkKvE14LCTaYiIkrnZHOVBMKuamD42dIs
-----END RSA PRIVATE KEY-----"""


class TestGitHubAppClient:
    def test_jwt_generation(self) -> None:
        client = GitHubAppClient(
            app_id="12345",
            private_key=_TEST_PRIVATE_KEY,
            installation_id="67890",
        )
        now = int(time.time())

        with patch("convergence_checker.github_client.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"token": "ghs_test_token"}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            token = client._ensure_token()  # noqa: SLF001

        assert token == "ghs_test_token"  # noqa: S105

        call_args = mock_post.call_args
        auth_header = call_args.kwargs.get("headers", call_args[1].get("headers", {}))
        bearer_token = auth_header["Authorization"].removeprefix("Bearer ")

        private_key = load_pem_private_key(_TEST_PRIVATE_KEY.encode(), password=None)
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        decoded = jwt.decode(bearer_token, public_pem, algorithms=["RS256"])
        assert decoded["iss"] == "12345"
        assert decoded["iat"] >= now - 120
        assert decoded["exp"] >= now

    def test_token_caching(self) -> None:
        client = GitHubAppClient(
            app_id="12345",
            private_key=_TEST_PRIVATE_KEY,
            installation_id="67890",
        )

        with patch("convergence_checker.github_client.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"token": "ghs_cached"}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            token1 = client._ensure_token()  # noqa: SLF001
            token2 = client._ensure_token()  # noqa: SLF001

        assert token1 == token2
        assert mock_post.call_count == 1

    def test_create_commit_status(self) -> None:
        client = GitHubAppClient(
            app_id="12345",
            private_key=_TEST_PRIVATE_KEY,
            installation_id="67890",
        )

        with patch("convergence_checker.github_client.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"token": "ghs_test"}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            client.create_commit_status(
                owner_repo="owner/repo",
                sha="abc123",
                state="success",
                context="GitOps Convergence Gate",
                description="All healthy",
            )

        assert mock_post.call_count == 2
        status_call = mock_post.call_args_list[1]
        assert "statuses/abc123" in status_call.args[0]
        body = status_call.kwargs.get("json", status_call[1].get("json", {}))
        assert body["state"] == "success"
        assert body["context"] == "GitOps Convergence Gate"
