import pytest

from backend.app.services.portable_ci_evidence import (
    PortableCIEvidenceError,
    validate_portable_ci_evidence,
)


SHA = "09bc082b943c4d44025b4f13fed6052c30033d5c"


def _execution(**overrides):
    value = {
        "authenticated": True,
        "provider": "railway",
        "run_id": "7456f61f-42be-4b8c-8f35-a25db9e7aef0",
        "status": "success",
        "commit_sha": SHA,
    }
    value.update(overrides)
    return value


def _receipt(**overrides):
    value = {
        "version": "seldrune-ci-v1",
        "status": "success",
        "release_sha": SHA,
        "checks": [
            "postgres-ready",
            "ruff",
            "pytest",
            "alembic-upgrade-head",
            "production-ready",
        ],
        "ready": {
            "ready": True,
            "status": "ready",
            "release": {"sha": SHA, "source": "seldrune"},
        },
    }
    value.update(overrides)
    return value


def test_validates_authenticated_commit_bound_portable_ci_evidence() -> None:
    output = validate_portable_ci_evidence(
        expected_sha=SHA,
        provider_execution=_execution(),
        receipt=_receipt(),
    )

    assert output["verified"] is True
    assert output["provider"] == "railway"
    assert output["commit_sha"] == SHA
    assert output["checks"] == [
        "alembic-upgrade-head",
        "postgres-ready",
        "production-ready",
        "pytest",
        "ruff",
    ]
    assert output["evidence"]["receipt_id"].endswith(SHA)


@pytest.mark.parametrize(
    ("execution", "receipt", "message"),
    [
        (_execution(authenticated=False), _receipt(), "authenticated adapter"),
        (_execution(status="failed"), _receipt(), "not successful"),
        (_execution(commit_sha="deadbeef"), _receipt(), "commit does not match"),
        (_execution(), _receipt(release_sha="deadbeef"), "release_sha does not match"),
        (_execution(), _receipt(status="failed"), "receipt is not successful"),
        (
            _execution(),
            _receipt(checks=["ruff", "pytest"]),
            "missing checks",
        ),
        (
            _execution(),
            _receipt(ready={"ready": False, "status": "starting"}),
            "readiness was not verified",
        ),
    ],
)
def test_rejects_untrusted_or_incomplete_evidence(execution, receipt, message) -> None:
    with pytest.raises(PortableCIEvidenceError, match=message):
        validate_portable_ci_evidence(
            expected_sha=SHA,
            provider_execution=execution,
            receipt=receipt,
        )
