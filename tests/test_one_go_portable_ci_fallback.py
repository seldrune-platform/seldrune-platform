from unittest.mock import Mock
from uuid import uuid4

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
        "_contract_step_tool_output",
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
        "_contract_step_tool_output",
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
        "_contract_step_tool_output",
        lambda *args, **kwargs: {"conclusion": "failure"},
    )

    hydrated, reason = one_go_controller._try_auto_portable_ci_fallback(
        Mock(),
        task=task,
        actor_user_id=task.created_by_user_id,
    )

    assert hydrated is False
    assert reason == "verify_ci_head_sha_missing"
