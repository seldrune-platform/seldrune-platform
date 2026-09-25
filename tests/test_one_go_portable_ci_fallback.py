from unittest.mock import Mock
from uuid import uuid4

from backend.app.core.tasking import TaskStatus
from backend.app.core.tools import ToolRunStatus
from backend.app.models.task import Task
from backend.app.services import one_go_controller


SHA = "1d39d92285a721ac9dcc081002d8a87e901c039c"


def _task() -> Task:
    return Task(
        id=uuid4(),
        organization_id=uuid4(),
        created_by_user_id=uuid4(),
        title="One-Go fallback test",
        objective="Hydrate portable CI only from exact-head trusted evidence.",
        input_data={"compiled_execution_contract": {"version": "stage-compiler-v1"}},
    )


def test_auto_fallback_fails_closed_when_configuration_is_missing(
    monkeypatch,
) -> None:
    task = _task()
    session = Mock()

    monkeypatch.setattr(
        one_go_controller,
        "_contract_step_verified_tool_output",
        lambda *args, **kwargs: {"head_sha": SHA},
    )
    for key in (
        "SELDRUNE_RAILWAY_API_TOKEN",
        "SELDRUNE_CI_RECEIPT_HMAC_KEY",
        "SELDRUNE_CI_RAILWAY_PROJECT_ID",
        "SELDRUNE_CI_RAILWAY_SERVICE_ID",
        "SELDRUNE_CI_RAILWAY_ENVIRONMENT_ID",
    ):
        monkeypatch.delenv(key, raising=False)

    hydrated, reason = one_go_controller._try_auto_portable_ci_fallback(
        session,
        task=task,
        actor_user_id=task.created_by_user_id,
    )

    assert hydrated is False
    assert reason.startswith("portable_ci_auto_config_missing:")
    assert "portable_ci_evidence" not in task.input_data


def test_auto_fallback_uses_verified_ci_head_and_retrieval_configuration(
    monkeypatch,
) -> None:
    task = _task()
    session = Mock()
    captured = {}

    monkeypatch.setattr(
        one_go_controller,
        "_contract_step_verified_tool_output",
        lambda *args, **kwargs: {"head_sha": SHA},
    )
    monkeypatch.setenv("SELDRUNE_RAILWAY_API_TOKEN", "railway-token")
    monkeypatch.setenv("SELDRUNE_CI_RECEIPT_HMAC_KEY", "signing-key")
    monkeypatch.setenv("SELDRUNE_CI_RAILWAY_PROJECT_ID", "project")
    monkeypatch.setenv("SELDRUNE_CI_RAILWAY_SERVICE_ID", "service")
    monkeypatch.setenv("SELDRUNE_CI_RAILWAY_ENVIRONMENT_ID", "environment")
    monkeypatch.setenv("SELDRUNE_RAILWAY_TOKEN_KIND", "project")

    def fake_auto_ingest(session_arg, **kwargs):
        captured["session"] = session_arg
        captured.update(kwargs)
        task.input_data = {
            **task.input_data,
            "portable_ci_evidence": {
                "receipt": {"release_sha": SHA},
                "signature": "sha256=test",
            },
        }
        return {"verified": True}

    monkeypatch.setattr(
        one_go_controller,
        "auto_ingest_railway_portable_ci_for_task",
        fake_auto_ingest,
    )

    hydrated, reason = one_go_controller._try_auto_portable_ci_fallback(
        session,
        task=task,
        actor_user_id=task.created_by_user_id,
    )

    assert hydrated is True
    assert reason == "portable_ci_auto_ingested"
    assert captured["expected_sha"] == SHA
    assert captured["railway_token"] == "railway-token"
    assert captured["signing_key"] == "signing-key"
    assert captured["project_id"] == "project"
    assert captured["service_id"] == "service"
    assert captured["environment_id"] == "environment"
    assert captured["token_kind"] == "project"
    session.refresh.assert_called_once_with(task)


def test_auto_fallback_does_not_overwrite_existing_evidence() -> None:
    task = _task()
    task.input_data = {
        **task.input_data,
        "portable_ci_evidence": {
            "receipt": {"release_sha": SHA},
            "signature": "sha256=existing",
        },
    }

    hydrated, reason = one_go_controller._try_auto_portable_ci_fallback(
        Mock(),
        task=task,
        actor_user_id=task.created_by_user_id,
    )

    assert hydrated is False
    assert reason == "portable_ci_evidence_already_present"


def test_auto_fallback_requires_verify_ci_head(monkeypatch) -> None:
    task = _task()
    monkeypatch.setattr(
        one_go_controller,
        "_contract_step_verified_tool_output",
        lambda *args, **kwargs: {"conclusion": "failure"},
    )

    hydrated, reason = one_go_controller._try_auto_portable_ci_fallback(
        Mock(),
        task=task,
        actor_user_id=task.created_by_user_id,
    )

    assert hydrated is False
    assert reason == "verify_ci_head_sha_missing"


def test_verified_tool_output_requires_matching_tool_run_receipt() -> None:
    parent = _task()
    child_id = uuid4()
    run_id = uuid4()
    receipt_id = "github-workflow-state:123:failed"
    child = Task(
        id=child_id,
        organization_id=parent.organization_id,
        created_by_user_id=parent.created_by_user_id,
        title="Verify CI",
        objective="Read hosted CI status.",
        status=TaskStatus.SUCCEEDED.value,
        input_data={
            "contract_parent_task_id": str(parent.id),
            "contract_step_id": "verify-ci",
        },
        output_data={
            "execution_type": "tool",
            "tool_slug": "github-workflow-run-status",
            "evidence": {
                "tool_run_id": str(run_id),
                "receipt_id": receipt_id,
            },
        },
    )
    run = Mock(
        id=run_id,
        organization_id=parent.organization_id,
        task_id=child_id,
        status=ToolRunStatus.SUCCEEDED.value,
        output_data={
            "head_sha": SHA,
            "conclusion": "failure",
            "failure_classification": "hosted_runner_unavailable",
            "evidence": {
                "receipt_id": receipt_id,
                "provider": "github",
            },
        },
    )
    session = Mock()
    session.scalars.return_value = [child]
    session.get.return_value = run

    output = one_go_controller._contract_step_verified_tool_output(
        session,
        parent_task=parent,
        step_id="verify-ci",
        expected_tool_slug="github-workflow-run-status",
    )

    assert output is run.output_data
    assert output["head_sha"] == SHA


def test_verified_tool_output_rejects_receipt_mismatch() -> None:
    parent = _task()
    child_id = uuid4()
    run_id = uuid4()
    child = Task(
        id=child_id,
        organization_id=parent.organization_id,
        created_by_user_id=parent.created_by_user_id,
        title="Verify CI",
        objective="Reject forged CI output.",
        status=TaskStatus.SUCCEEDED.value,
        input_data={
            "contract_parent_task_id": str(parent.id),
            "contract_step_id": "verify-ci",
        },
        output_data={
            "execution_type": "tool",
            "tool_slug": "github-workflow-run-status",
            "evidence": {
                "tool_run_id": str(run_id),
                "receipt_id": "forged-receipt",
            },
        },
    )
    run = Mock(
        id=run_id,
        organization_id=parent.organization_id,
        task_id=child_id,
        status=ToolRunStatus.SUCCEEDED.value,
        output_data={
            "head_sha": SHA,
            "evidence": {
                "receipt_id": "provider-receipt",
                "provider": "github",
            },
        },
    )
    session = Mock()
    session.scalars.return_value = [child]
    session.get.return_value = run

    assert (
        one_go_controller._contract_step_verified_tool_output(
            session,
            parent_task=parent,
            step_id="verify-ci",
            expected_tool_slug="github-workflow-run-status",
        )
        is None
    )


def test_auto_fallback_accepts_new_ci_target_aliases(monkeypatch) -> None:
    task = _task()
    session = Mock()
    captured = {}
    monkeypatch.setattr(
        one_go_controller,
        "_contract_step_verified_tool_output",
        lambda *args, **kwargs: {"head_sha": SHA},
    )
    for key in (
        "SELDRUNE_CI_RAILWAY_PROJECT_ID",
        "SELDRUNE_CI_RAILWAY_SERVICE_ID",
        "SELDRUNE_CI_RAILWAY_ENVIRONMENT_ID",
        "RAILWAY_PROJECT_ID",
        "RAILWAY_SERVICE_ID",
        "RAILWAY_ENVIRONMENT_ID",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SELDRUNE_RAILWAY_API_TOKEN", "railway-token")
    monkeypatch.setenv("SELDRUNE_CI_RECEIPT_HMAC_KEY", "signing-key")
    monkeypatch.setenv("SELDRUNE_RAILWAY_CI_PROJECT_ID", "alias-project")
    monkeypatch.setenv("SELDRUNE_RAILWAY_CI_SERVICE_ID", "alias-service")
    monkeypatch.setenv(
        "SELDRUNE_RAILWAY_CI_ENVIRONMENT_ID",
        "alias-environment",
    )

    def fake_auto_ingest(session_arg, **kwargs):
        captured.update(kwargs)
        return {"verified": True}

    monkeypatch.setattr(
        one_go_controller,
        "auto_ingest_railway_portable_ci_for_task",
        fake_auto_ingest,
    )
    hydrated, reason = one_go_controller._try_auto_portable_ci_fallback(
        session,
        task=task,
        actor_user_id=task.created_by_user_id,
    )

    assert hydrated is True
    assert reason == "portable_ci_auto_ingested"
    assert captured["project_id"] == "alias-project"
    assert captured["service_id"] == "alias-service"
    assert captured["environment_id"] == "alias-environment"
