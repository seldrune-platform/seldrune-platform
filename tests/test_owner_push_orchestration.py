from unittest.mock import MagicMock
from uuid import uuid4

from backend.app.services.owner_push_delivery import PushDeliveryResult
from backend.app.services.owner_push_orchestration import deliver_owner_attention_pushes


def test_owner_push_delivery_endpoint_is_explicit(client) -> None:
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    path = schema.json()["paths"][
        "/api/v1/organizations/{organization_id}/owner-attention/push-delivery"
    ]
    assert set(path) == {"post"}


def test_delivery_returns_without_query_when_not_configured(monkeypatch) -> None:
    session = MagicMock()
    monkeypatch.setattr(
        "backend.app.services.owner_push_orchestration.delivery_configured",
        lambda: False,
    )

    summary = deliver_owner_attention_pushes(session, uuid4(), uuid4(), {})

    assert summary.configured is False
    assert summary.attempted == 0
    session.scalars.assert_not_called()


def test_delivery_isolates_failures_and_removes_only_stale(monkeypatch) -> None:
    session = MagicMock()
    delivered = MagicMock(name="delivered")
    stale = MagicMock(name="stale")
    failed = MagicMock(name="failed")
    session.scalars.return_value = [delivered, stale, failed]
    results = iter(
        [
            PushDeliveryResult(delivered=True),
            PushDeliveryResult(delivered=False, stale=True, status_code=410),
            PushDeliveryResult(delivered=False, stale=False, status_code=503),
        ]
    )
    monkeypatch.setattr(
        "backend.app.services.owner_push_orchestration.delivery_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "backend.app.services.owner_push_orchestration.send_owner_attention_push",
        lambda subscription, envelope: next(results),
    )

    summary = deliver_owner_attention_pushes(
        session,
        uuid4(),
        uuid4(),
        {"fingerprint": "a" * 64, "notification": {"has_attention": True}},
    )

    assert summary.configured is True
    assert summary.attempted == 3
    assert summary.delivered == 1
    assert summary.failed == 2
    assert summary.stale_removed == 1
    session.delete.assert_called_once_with(stale)
    session.commit.assert_called_once()


def test_non_stale_failures_do_not_mutate_registry(monkeypatch) -> None:
    session = MagicMock()
    session.scalars.return_value = [MagicMock()]
    monkeypatch.setattr(
        "backend.app.services.owner_push_orchestration.delivery_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "backend.app.services.owner_push_orchestration.send_owner_attention_push",
        lambda subscription, envelope: PushDeliveryResult(
            delivered=False,
            stale=False,
            status_code=500,
        ),
    )

    summary = deliver_owner_attention_pushes(session, uuid4(), uuid4(), {})

    assert summary.failed == 1
    assert summary.stale_removed == 0
    session.delete.assert_not_called()
    session.commit.assert_not_called()
