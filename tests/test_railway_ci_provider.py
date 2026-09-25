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


def test_ingest_helper_routes_through_railway_adapter(monkeypatch) -> None:
    captured = {}

    def fake_ingest(session, **kwargs):
        captured["session"] = session
        captured.update(kwargs)
        return {"verified": True, "provider": "railway"}

    monkeypatch.setattr(
        railway_ci_provider,
        "ingest_portable_ci_evidence",
        fake_ingest,
    )

    session = object()
    task = object()
    receipt = {"version": "seldrune-ci-v1"}
    result = railway_ci_provider.ingest_railway_portable_ci_evidence(
        session,
        task=task,
        actor_user_id=None,
        expected_sha=SHA,
        deployment_id=RUN_ID,
        receipt=receipt,
        signature="sha256=signature",
        signing_key="receipt-signing-key",
        railway_token="railway-account-token",
        token_kind="workspace",
    )

    assert result == {"verified": True, "provider": "railway"}
    assert captured["session"] is session
    assert captured["task"] is task
    assert captured["expected_sha"] == SHA
    assert captured["run_id"] == RUN_ID
    assert captured["receipt"] is receipt
    assert captured["signature"] == "sha256=signature"
    assert captured["signing_key"] == "receipt-signing-key"
    adapter = captured["provider_adapter"]
    assert isinstance(adapter, RailwayPortableCIProvider)
    assert adapter.provider_name == "railway"


def test_fetch_receipt_bundle_reads_signed_marker_from_authenticated_logs(
    monkeypatch,
) -> None:
    receipt = {
        "version": "seldrune-ci-v1",
        "status": "success",
        "release_sha": SHA,
        "checks": ["pytest"],
        "ready": {"ready": True},
    }
    receipt_json = railway_ci_provider.json.dumps(
        receipt,
        separators=(",", ":"),
        sort_keys=True,
    )
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured["variables"] = json["variables"]
        return FakeResponse(
            {
                "data": {
                    "deploymentLogs": [
                        {"message": "PostgreSQL ready"},
                        {
                            "message": (
                                "SELDRUNE_CI_RECEIPT_JSON="
                                + receipt_json
                            )
                        },
                        {
                            "message": (
                                "SELDRUNE_CI_RECEIPT_SIGNATURE="
                                "sha256=abc123"
                            )
                        },
                    ]
                }
            }
        )

    monkeypatch.setattr(railway_ci_provider.httpx, "post", fake_post)
    adapter = RailwayPortableCIProvider(token="railway-token")

    result = adapter.fetch_receipt_bundle(run_id=RUN_ID)

    assert result == {
        "receipt": receipt,
        "signature": "sha256=abc123",
    }
    assert captured["variables"] == {
        "deploymentId": RUN_ID,
        "limit": 500,
    }


@pytest.mark.parametrize(
    ("logs", "message"),
    [
        ([], "did not emit a portable CI receipt"),
        (
            [
                {
                    "message": (
                        "SELDRUNE_CI_RECEIPT_JSON="
                        '{"status":"success"}'
                    )
                }
            ],
            "did not emit a signed portable CI receipt",
        ),
        (
            [
                {
                    "message": (
                        "SELDRUNE_CI_RECEIPT_JSON="
                        '{"status":"success"}'
                    )
                },
                {
                    "message": (
                        "SELDRUNE_CI_RECEIPT_SIGNATURE=unsigned"
                    )
                },
            ],
            "did not emit a signed portable CI receipt",
        ),
    ],
)
def test_fetch_receipt_bundle_fails_closed(monkeypatch, logs, message) -> None:
    monkeypatch.setattr(
        railway_ci_provider.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse(
            {"data": {"deploymentLogs": logs}}
        ),
    )
    adapter = RailwayPortableCIProvider(token="railway-token")

    with pytest.raises(RailwayCIProviderError, match=message):
        adapter.fetch_receipt_bundle(run_id=RUN_ID)


def test_ingest_run_retrieves_receipt_before_ingestion(monkeypatch) -> None:
    receipt = {"version": "seldrune-ci-v1"}
    captured = {}

    def fake_bundle(self, *, run_id):
        captured["bundle_run_id"] = run_id
        return {
            "receipt": receipt,
            "signature": "sha256=signed",
        }

    def fake_ingest(session, **kwargs):
        captured["session"] = session
        captured.update(kwargs)
        return {"verified": True, "provider": "railway"}

    monkeypatch.setattr(
        RailwayPortableCIProvider,
        "fetch_receipt_bundle",
        fake_bundle,
    )
    monkeypatch.setattr(
        railway_ci_provider,
        "ingest_portable_ci_evidence",
        fake_ingest,
    )

    session = object()
    task = object()
    result = railway_ci_provider.ingest_railway_portable_ci_run(
        session,
        task=task,
        actor_user_id=None,
        expected_sha=SHA,
        deployment_id=RUN_ID,
        signing_key="receipt-signing-key",
        railway_token="railway-account-token",
    )

    assert result == {"verified": True, "provider": "railway"}
    assert captured["bundle_run_id"] == RUN_ID
    assert captured["session"] is session
    assert captured["task"] is task
    assert captured["expected_sha"] == SHA
    assert captured["run_id"] == RUN_ID
    assert captured["receipt"] is receipt
    assert captured["signature"] == "sha256=signed"


def test_find_successful_deployment_matches_exact_commit(monkeypatch) -> None:
    def fake_post(url, *, headers, json, timeout):
        return FakeResponse(
            {
                "data": {
                    "deployments": {
                        "edges": [
                            {
                                "node": {
                                    "id": "wrong-failed",
                                    "status": "FAILED",
                                    "meta": {"commitHash": SHA},
                                }
                            },
                            {
                                "node": {
                                    "id": "wrong-sha",
                                    "status": "SUCCESS",
                                    "meta": {"commitHash": "deadbeef"},
                                }
                            },
                            {
                                "node": {
                                    "id": RUN_ID,
                                    "status": "SUCCESS",
                                    "meta": {"commitHash": SHA},
                                }
                            },
                        ]
                    }
                }
            }
        )

    monkeypatch.setattr(railway_ci_provider.httpx, "post", fake_post)
    adapter = RailwayPortableCIProvider(token="railway-token")

    result = adapter.find_successful_deployment(
        expected_sha=SHA,
        project_id="project",
        service_id="service",
        environment_id="environment",
    )

    assert result["run_id"] == RUN_ID
    assert result["commit_sha"] == SHA
    assert result["status"] == "success"


def test_find_successful_deployment_fails_when_no_exact_match(monkeypatch) -> None:
    monkeypatch.setattr(
        railway_ci_provider.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse(
            {
                "data": {
                    "deployments": {
                        "edges": [
                            {
                                "node": {
                                    "id": "other",
                                    "status": "SUCCESS",
                                    "meta": {"commitHash": "deadbeef"},
                                }
                            }
                        ]
                    }
                }
            }
        ),
    )
    adapter = RailwayPortableCIProvider(token="railway-token")

    with pytest.raises(
        RailwayCIProviderError,
        match="no successful Railway deployment matches expected_sha",
    ):
        adapter.find_successful_deployment(
            expected_sha=SHA,
            project_id="project",
            service_id="service",
            environment_id="environment",
        )
