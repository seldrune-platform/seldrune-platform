import hashlib
import hmac
import json
from unittest.mock import Mock
from uuid import uuid4

import pytest

from backend.app.models.task import Task
from backend.app.services.portable_ci_ingestion import (
    PortableCIIngestionError,
    ingest_portable_ci_evidence,
)


SHA = "d3d57c23b4b03b39fd593973c40b2cb3061ffbc2"
RUN_ID = "d1844fd7-a89b-4556-b842-1f8c45ad96ff"
SIGNING_KEY = "portable-ci-ingestion-test-signing-key"


class FakeRailwayAdapter:
    provider_name = "railway"

    def __init__(self, **overrides):
        self.overrides = overrides

    def fetch_execution(self, *, run_id: str) -> dict:
        value = {
            "provider": "railway",
            "run_id": run_id,
            "status": "success",
            "commit_sha": SHA,
        }
        value.update(self.overrides)
        return value


def _receipt(**overrides) -> dict:
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
            "environment": "production",
            "release": {
                "sha": SHA,
                "source": "seldrune",
            },
        },
    }
    value.update(overrides)
    return value


def _signature(receipt: dict, key: str = SIGNING_KEY) -> str:
    canonical = json.dumps(
        receipt,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = hmac.new(
        key.encode("utf-8"),
        canonical,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def _task() -> Task:
    return Task(
        id=uuid4(),
        organization_id=uuid4(),
        created_by_user_id=uuid4(),
        title="Portable CI evidence target",
        objective="Accept evidence only from authenticated exact-head execution.",
        input_data={"compiled_execution_contract": {"version": "stage-compiler-v1"}},
    )


def test_ingestion_requires_provider_and_signed_exact_head_evidence() -> None:
    session = Mock()
    task = _task()
    receipt = _receipt()

    result = ingest_portable_ci_evidence(
        session,
        task=task,
        actor_user_id=task.created_by_user_id,
        expected_sha=SHA,
        run_id=RUN_ID,
        receipt=receipt,
        signature=_signature(receipt),
        signing_key=SIGNING_KEY,
        provider_adapter=FakeRailwayAdapter(),
    )

    assert result["verified"] is True
    assert result["provider"] == "railway"
    assert result["run_id"] == RUN_ID
    assert result["commit_sha"] == SHA
    evidence = task.input_data["portable_ci_evidence"]
    assert evidence["receipt"] == receipt
    assert evidence["signature"].startswith("sha256=")
    assert evidence["provider"]["commit_sha"] == SHA
    assert evidence["signed_receipt"]["signature_verified"] is True
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(task)


@pytest.mark.parametrize(
    ("adapter", "receipt_mutator", "signature_key", "message"),
    [
        (
            FakeRailwayAdapter(status="failed"),
            None,
            SIGNING_KEY,
            "provider execution is not successful",
        ),
        (
            FakeRailwayAdapter(commit_sha="deadbeef"),
            None,
            SIGNING_KEY,
            "provider execution commit does not match",
        ),
        (
            FakeRailwayAdapter(provider="github"),
            None,
            SIGNING_KEY,
            "identity does not match authenticated adapter",
        ),
        (
            FakeRailwayAdapter(),
            lambda value: value.update(release_sha="deadbeef"),
            SIGNING_KEY,
            "signed portable CI receipt does not match",
        ),
        (
            FakeRailwayAdapter(),
            None,
            "wrong-signing-key",
            "signature mismatch",
        ),
    ],
)
def test_ingestion_fails_closed(
    adapter,
    receipt_mutator,
    signature_key,
    message,
) -> None:
    session = Mock()
    task = _task()
    receipt = _receipt()
    original_signature = _signature(receipt)
    if receipt_mutator is not None:
        receipt_mutator(receipt)

    signature = (
        original_signature
        if signature_key == SIGNING_KEY
        else _signature(receipt, signature_key)
    )

    with pytest.raises(PortableCIIngestionError, match=message):
        ingest_portable_ci_evidence(
            session,
            task=task,
            actor_user_id=task.created_by_user_id,
            expected_sha=SHA,
            run_id=RUN_ID,
            receipt=receipt,
            signature=signature,
            signing_key=SIGNING_KEY,
            provider_adapter=adapter,
        )

    assert "portable_ci_evidence" not in task.input_data
    session.commit.assert_not_called()
