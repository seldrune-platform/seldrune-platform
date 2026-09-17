from copy import deepcopy
from datetime import UTC, datetime, timedelta

from backend.app.api.routes.owner_attention import _etag_matches, _snapshot_headers
from backend.app.services.owner_attention_snapshot import (
    build_owner_attention_snapshot,
    owner_attention_fingerprint,
)


def _attention() -> dict:
    now = datetime.now(UTC)
    return {
        "summary": {
            "total": 2,
            "critical": 1,
            "reviews": 0,
            "approvals": 1,
            "warnings": 0,
        },
        "items": [
            {
                "kind": "critical_incident",
                "category": "incident",
                "severity": "critical",
                "attention_rank": 400,
                "title": "Critical task failure",
                "detail": "A governed task failed",
                "meta": "",
                "resource_type": "task_failed",
                "resource_id": "task-1",
                "occurred_at": now,
                "action": {
                    "kind": "navigate",
                    "label": "Open incidents",
                    "href": "#incident-title",
                },
            },
            {
                "kind": "command_approval",
                "category": "command_approval",
                "severity": "approval",
                "attention_rank": 250,
                "title": "Approve governed launch",
                "detail": "Review the governed command before execution.",
                "meta": "",
                "resource_type": "owner_command",
                "resource_id": "command-1",
                "occurred_at": now - timedelta(minutes=1),
                "action": {
                    "kind": "review_command",
                    "label": "Review command",
                    "command_id": "command-1",
                },
            },
        ],
        "read_only": True,
        "governance": {
            "approval_gate_bypassed": False,
            "strategy_review_gate_bypassed": False,
            "execution_triggered": False,
        },
    }


def test_attention_fingerprint_ignores_timestamp_only_noise() -> None:
    first = _attention()
    second = deepcopy(first)
    second["items"][0]["occurred_at"] = datetime.now(UTC) + timedelta(days=1)

    assert owner_attention_fingerprint(first) == owner_attention_fingerprint(second)


def test_attention_fingerprint_changes_on_meaningful_content() -> None:
    first = _attention()
    second = deepcopy(first)
    second["items"][0]["detail"] = "The governed task failed with new evidence"

    assert owner_attention_fingerprint(first) != owner_attention_fingerprint(second)


def test_snapshot_reports_change_and_digest_limit() -> None:
    attention = _attention()
    fingerprint = owner_attention_fingerprint(attention)

    unchanged = build_owner_attention_snapshot(
        attention,
        limit=1,
        previous_fingerprint=fingerprint.upper(),
    )
    assert unchanged["changed"] is False
    assert unchanged["previous_fingerprint_supplied"] is True
    assert unchanged["top_items_limit"] == 1
    assert len(unchanged["top_items"]) == 1
    assert unchanged["total_items"] == 2
    assert unchanged["headline"] == "Owner attention: 1 critical, 1 approval."
    assert unchanged["read_only"] is True

    changed_attention = deepcopy(attention)
    changed_attention["items"][1]["title"] = "Approve revised governed launch"
    changed = build_owner_attention_snapshot(
        changed_attention,
        previous_fingerprint=fingerprint,
    )
    assert changed["changed"] is True


def test_snapshot_without_previous_fingerprint_is_neutral() -> None:
    snapshot = build_owner_attention_snapshot(_attention())
    assert snapshot["changed"] is None
    assert snapshot["previous_fingerprint_supplied"] is False
    assert snapshot["snapshot_version"] == 1
    assert snapshot["fingerprint_algorithm"] == "sha256"
    assert snapshot["fingerprint_semantics"]["excluded_fields"] == ["occurred_at"]


def test_etag_matching_accepts_standard_validator_forms() -> None:
    fingerprint = "a" * 64
    assert _etag_matches(f'"{fingerprint}"', fingerprint) is True
    assert _etag_matches(f'W/"{fingerprint}"', fingerprint) is True
    assert _etag_matches(f'"{"b" * 64}", W/"{fingerprint.upper()}"', fingerprint) is True
    assert _etag_matches("*", fingerprint) is True
    assert _etag_matches(f'"{"b" * 64}"', fingerprint) is False
    assert _etag_matches(None, fingerprint) is False


def test_snapshot_headers_are_private_and_authorization_varying() -> None:
    fingerprint = "c" * 64
    headers = _snapshot_headers(fingerprint)
    assert headers == {
        "ETag": f'"{fingerprint}"',
        "Cache-Control": "private, no-cache",
        "Vary": "Authorization",
    }


def test_owner_attention_snapshot_route_is_get_only(client) -> None:
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    path = "/api/v1/organizations/{organization_id}/owner-attention/snapshot"
    assert path in schema.json()["paths"]
    operation = schema.json()["paths"][path]
    assert set(operation) == {"get"}
    assert "304" in operation["get"]["responses"]
