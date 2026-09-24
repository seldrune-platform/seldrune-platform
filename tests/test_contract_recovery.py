from uuid import uuid4

import httpx
import pytest

from backend.app.services import contract_recovery
from backend.app.services.contract_recovery import (
    advance_contract_with_recovery,
    classify_contract_blocker,
)
from backend.app.services.external_actions import github_dispatch_workflow


@pytest.mark.parametrize(
    ("status", "reason", "classification"),
    [
        ("verified", "verified_compiled_contract", "complete"),
        ("unverified", "receipt_mismatch", "unverified"),
        ("blocked", "step_limit", "retryable"),
        ("blocked", "acceptance_pending:verify-ci", "retryable"),
        ("blocked", "tool_step_blocked:verify-ci", "retryable"),
        ("blocked", "approval_required:merge-verified-pull-request", "approval"),
        ("blocked", "execution_mode:owner-gated", "approval"),
        ("blocked", "execution_mode:external-resource", "external-resource"),
        ("blocked", "compiled_tools_unavailable:run-ci", "configuration"),
        ("blocked", "binding_unresolved:verify-ci:run_id", "configuration"),
        ("blocked", "acceptance_failed:verify-ci", "failed"),
    ],
)
def test_classify_contract_blocker(
    status: str,
    reason: str,
    classification: str,
) -> None:
    assert classify_contract_blocker(
        status=status,
        reason=reason,
    ) == classification


def test_recovery_retries_pending_then_stops_on_verified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reports = iter(
        [
            {
                "status": "blocked",
                "reason": "acceptance_pending:verify-ci",
                "executed_steps": 1,
                "verified": False,
            },
            {
                "status": "verified",
                "reason": "verified_compiled_contract",
                "executed_steps": 1,
                "verified": True,
                "evidence_refs": ["receipt:contract-chain:test"],
            },
        ]
    )
    calls: list[int] = []

    def fake_advance(*args, **kwargs):
        calls.append(int(kwargs["max_steps"]))
        return next(reports)

    monkeypatch.setattr(
        contract_recovery,
        "advance_compiled_contract",
        fake_advance,
    )

    result = advance_contract_with_recovery(
        object(),
        task=object(),
        actor_user_id=uuid4(),
        max_steps=7,
        max_rounds=3,
    )

    assert calls == [7, 7]
    assert result["status"] == "verified"
    recovery = result["recovery"]
    assert recovery["version"] == "contract-recovery-v1"
    assert recovery["rounds_executed"] == 2
    assert recovery["final_classification"] == "complete"
    assert recovery["retryable_remaining"] is False
    assert recovery["requires_owner_action"] is False


def test_recovery_never_retries_approval_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_advance(*args, **kwargs):
        nonlocal calls
        calls += 1
        return {
            "status": "blocked",
            "reason": "approval_required:merge-verified-pull-request",
            "executed_steps": 0,
            "verified": False,
        }

    monkeypatch.setattr(
        contract_recovery,
        "advance_compiled_contract",
        fake_advance,
    )

    result = advance_contract_with_recovery(
        object(),
        task=object(),
        actor_user_id=uuid4(),
        max_rounds=5,
    )

    assert calls == 1
    assert result["recovery"]["final_classification"] == "approval"
    assert result["recovery"]["requires_owner_action"] is True


def test_github_dispatch_discovers_workflow_run_after_204(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    post_request = httpx.Request(
        "POST",
        "https://api.github.com/repos/seldrune-platform/seldrune-platform/"
        "actions/workflows/ci.yml/dispatches",
    )
    get_request = httpx.Request(
        "GET",
        "https://api.github.com/repos/seldrune-platform/seldrune-platform/"
        "actions/workflows/ci.yml/runs",
    )

    def fake_post(*args, **kwargs):
        return httpx.Response(
            204,
            headers={"x-github-request-id": "request-123"},
            request=post_request,
        )

    def fake_get(*args, **kwargs):
        return httpx.Response(
            200,
            json={
                "workflow_runs": [
                    {
                        "id": 98765,
                        "created_at": "2099-01-01T00:00:00Z",
                        "url": "https://api.github.com/actions/runs/98765",
                        "html_url": "https://github.com/actions/runs/98765",
                    }
                ]
            },
            request=get_request,
        )

    monkeypatch.setattr(
        "backend.app.services.external_actions.httpx.post",
        fake_post,
    )
    monkeypatch.setattr(
        "backend.app.services.external_actions.httpx.get",
        fake_get,
    )

    result = github_dispatch_workflow(
        {
            "owner": "seldrune-platform",
            "repo": "seldrune-platform",
            "workflow_id": "ci.yml",
            "ref": "feature/test",
            "inputs": {},
        },
        "token",
    )

    assert result["workflow_run_id"] == 98765
    assert result["evidence"]["receipt_id"] == "github-workflow:98765"
