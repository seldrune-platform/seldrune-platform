from typing import Any

from backend.app.services.owner_attention_snapshot import owner_attention_fingerprint


_COUNT_LABELS = (
    ("critical", "critical"),
    ("reviews", "review"),
    ("approvals", "approval"),
    ("warnings", "warning"),
)


def _safe_summary(summary: dict[str, Any]) -> dict[str, int]:
    values = {key: max(0, int(summary.get(key) or 0)) for key, _ in _COUNT_LABELS}
    values["total"] = max(0, int(summary.get("total") or sum(values.values())))
    return values


def _notification_body(summary: dict[str, int]) -> str:
    if summary["total"] == 0:
        return "No owner attention is currently required."
    parts: list[str] = []
    for key, label in _COUNT_LABELS:
        count = summary[key]
        if count:
            suffix = "" if count == 1 else "s"
            parts.append(f"{count} {label}{suffix}")
    return "Owner attention: " + ", ".join(parts) + "."


def _urgency(summary: dict[str, int]) -> str:
    if summary["critical"]:
        return "critical"
    if summary["reviews"]:
        return "review"
    if summary["approvals"]:
        return "approval"
    if summary["warnings"]:
        return "warning"
    return "none"


def build_owner_attention_notification_envelope(
    attention: dict[str, Any],
    *,
    previous_fingerprint: str | None = None,
) -> dict[str, Any]:
    fingerprint = owner_attention_fingerprint(attention)
    summary = _safe_summary(attention.get("summary") or {})
    changed = None if previous_fingerprint is None else previous_fingerprint.lower() != fingerprint
    return {
        "notification_version": 1,
        "fingerprint": fingerprint,
        "fingerprint_algorithm": "sha256",
        "previous_fingerprint_supplied": previous_fingerprint is not None,
        "changed": changed,
        "has_attention": bool(summary["total"]),
        "urgency": _urgency(summary),
        "title": "Seldrune Owner Attention",
        "body": _notification_body(summary),
        "target": "/console#action-inbox",
        "summary": summary,
        "privacy": {
            "detail_level": "counts_only",
            "contains_resource_titles": False,
            "contains_resource_details": False,
            "contains_resource_ids": False,
            "contains_command_objectives": False,
        },
        "delivery": {
            "provider": None,
            "delivery_triggered": False,
            "subscription_created": False,
        },
        "read_only": True,
        "governance": attention.get("governance") or {},
    }
