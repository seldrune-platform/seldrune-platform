import pytest

from backend.app.services import railway_ci_provider
from backend.app.services.railway_ci_provider import (
    RailwayCIProviderError,
    RailwayPortableCIProvider,
)


SHA = "90146d478420702dd94c30a97955dc219359ff2b"
RUN_ID = "2123df77-4342-40c8-9ed1-92a5bc5b62b7"


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def test_fetch_execution_uses_authenticated_bearer_and_exact_deployment(
    monkeypatch,
) -> None:
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return FakeResponse(
            {
                "data": {
                    "deployment": {
                        "id": RUN_ID,
                        "status": "SUCCESS",
                        "meta": {
                            "commitHash": SHA,
                            "branch": "feature/authenticated-ci-ingestion",
                        },
                    }
                }
            }
        )

    monkeypatch.setattr(railway_ci_provider.httpx, "post", fake_post)
    adapter = RailwayPortableCIProvider(
        token="railway-account-token",
        token_kind="account",
    )

    result = adapter.fetch_execution(run_id=RUN_ID)

    assert result == {
        "provider": "railway",
        "run_id": RUN_ID,
        "status": "success",
        "commit_sha": SHA,
        "provider_status": "SUCCESS",
    }
    assert captured["url"] == railway_ci_provider.RAILWAY_GRAPHQL_URL
    assert captured["headers"]["Authorization"] == "Bearer railway-account-token"
    assert "Project-Access-Token" not in captured["headers"]
    assert captured["json"]["variables"] == {"id": RUN_ID}


def test_project_token_uses_project_access_header(monkeypatch) -> None:
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured["headers"] = headers
        return FakeResponse(
            {
                "data": {
                    "deployment": {
                        "id": RUN_ID,
                        "status": "FAILED",
                        "meta": {"commitHash": SHA},
                    }
                }
            }
        )

    monkeypatch.setattr(railway_ci_provider.httpx, "post", fake_post)
    adapter = RailwayPortableCIProvider(
        token="railway-project-token",
        token_kind="project",
    )

    result = adapter.fetch_execution(run_id=RUN_ID)

    assert result["status"] == "failed"
    assert captured["headers"]["Project-Access-Token"] == (
        "railway-project-token"
    )
    assert "Authorization" not in captured["headers"]


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {
                "errors": [
                    {
                        "message": "Not Authorized",
                        "extensions": {"code": "INTERNAL_SERVER_ERROR"},
                    }
                ],
                "data": None,
            },
            "Not Authorized",
        ),
        (
            {"data": {"deployment": None}},
            "deployment was not found",
        ),
        (
            {
                "data": {
                    "deployment": {
                        "id": RUN_ID,
                        "status": "SUCCESS",
                        "meta": {},
                    }
                }
            },
            "commit hash is missing",
        ),
    ],
)
def test_fetch_execution_fails_closed(monkeypatch, payload, message) -> None:
    monkeypatch.setattr(
        railway_ci_provider.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse(payload),
    )
    adapter = RailwayPortableCIProvider(token="railway-token")

    with pytest.raises(RailwayCIProviderError, match=message):
        adapter.fetch_execution(run_id=RUN_ID)
