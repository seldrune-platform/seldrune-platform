from copy import deepcopy
from datetime import UTC, datetime

from backend.app.services.owner_attention_notification import (
    build_owner_attention_notification_envelope,
)
from backend.app.services.owner_attention_snapshot import owner_attention_fingerprint


def _attention() -> dict:
    now = datetime.now(UTC)
    return {
        "summary": {
            "total": 3,
            "critical": 1,
            "reviews": 1,
            "approvals": 1,
            "warnings": 0,
        },
        "items": [
            {
                "kind": "critical_incident",
                "category": "incident",
                "severity": "critical",
                "attention_rank": 400,
                "title": "Sensitive client incident title",
                "detail": "Sensitive incident detail",
                "meta": "Sensitive internal metadata",
                "resource_type": "task_failed",
                "resource_id": "secret-resource-id",
                "occurred_at": now,
                "action": {"kind": "navigate", "label": "Open incidents", "href": "#incident-title"},
            },
            {
                "kind": "pending_strategy_review",
                "category": "strategy_review",
                "severity": "review",
                "attention_rank": 325,
                "title": "Sensitive strategy title",
                "detail": "Sensitive strategy evidence",
                "meta": "Private strategy metadata",
                "resource_type": "executive_priority",
                "resource_id": "priority-1",
                "occurred_at": now,
                "action": {"kind": "navigate", "label": "Open Review Drift", "href": "/console-assets/executive-brief.html"},
            },
            {
                "kind": "command_approval",
                "category": "command_approval",
                "severity": "approval",
                "attention_rank": 250,
                "title": "Secret acquisition objective",
                "detail": "Private governed command detail",
                "meta": "",
                "resource_type": "owner_command",
                "resource_id": "command-1",
                "occurred_at": now,
                "action": {"kind": "review_command", "label": "Review command", "command_id": "command-1"},
            },
        ],
        "read_only": True,
        "governance": {
            "approval_gate_bypassed": False,
            "strategy_review_gate_bypassed": False,
            "execution_triggered": False,
        },
    }


def test_notification_envelope_is_counts_only_and_privacy_safe() -> None:
    envelope = build_owner_attention_notification_envelope(_attention())

    assert envelope["notification_version"] == 1
    assert envelope["urgency"] == "critical"
    assert envelope["body"] == "Owner attention: 1 critical, 1 review, 1 approval."
    assert envelope["target"] == "/console#action-inbox"
    assert envelope["summary"] == {
        "critical": 1,
        "reviews": 1,
        "approvals": 1,
        "warnings": 0,
        "total": 3,
    }
    serialized = repr(envelope)
    assert "Sensitive client incident title" not in serialized
    assert "Sensitive incident detail" not in serialized
    assert "secret-resource-id" not in serialized
    assert "Secret acquisition objective" not in serialized
    assert envelope["privacy"]["detail_level"] == "counts_only"
    assert envelope["privacy"]["contains_resource_titles"] is False
    assert envelope["privacy"]["contains_command_objectives"] is False


def test_notification_envelope_reuses_stable_attention_fingerprint() -> None:
    attention = _attention()
    fingerprint = owner_attention_fingerprint(attention)

    unchanged = build_owner_attention_notification_envelope(
        attention,
        previous_fingerprint=fingerprint.upper(),
    )
    assert unchanged["fingerprint"] == fingerprint
    assert unchanged["changed"] is False
    assert unchanged["previous_fingerprint_supplied"] is True

    changed_attention = deepcopy(attention)
    changed_attention["items"][0]["detail"] = "Meaningfully different incident evidence"
    changed = build_owner_attention_notification_envelope(
        changed_attention,
        previous_fingerprint=fingerprint,
    )
    assert changed["changed"] is True


def test_notification_envelope_never_triggers_delivery_or_governed_actions() -> None:
    envelope = build_owner_attention_notification_envelope(_attention())

    assert envelope["read_only"] is True
    assert envelope["delivery"] == {
        "provider": None,
        "delivery_triggered": False,
        "subscription_created": False,
    }
    assert envelope["governance"] == {
        "approval_gate_bypassed": False,
        "strategy_review_gate_bypassed": False,
        "execution_triggered": False,
    }


def test_notification_envelope_empty_state_is_neutral() -> None:
    attention = _attention()
    attention["summary"] = {
        "total": 0,
        "critical": 0,
        "reviews": 0,
        "approvals": 0,
        "warnings": 0,
    }
    attention["items"] = []

    envelope = build_owner_attention_notification_envelope(attention)
    assert envelope["has_attention"] is False
    assert envelope["urgency"] == "none"
    assert envelope["body"] == "No owner attention is currently required."
    assert envelope["changed"] is None


def test_owner_attention_notification_route_is_get_only(client) -> None:
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    path = "/api/v1/organizations/{organization_id}/owner-attention/notification-envelope"
    assert path in schema.json()["paths"]
    operation = schema.json()["paths"][path]
    assert set(operation) == {"get"}
    assert "304" in operation["get"]["responses"]
