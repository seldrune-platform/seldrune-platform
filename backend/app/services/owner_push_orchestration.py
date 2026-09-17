from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.owner_push_subscription import OwnerPushSubscription
from backend.app.services.owner_push_delivery import (
    delivery_configured,
    send_owner_attention_push,
)


@dataclass(frozen=True)
class OwnerPushDeliverySummary:
    configured: bool
    attempted: int = 0
    delivered: int = 0
    failed: int = 0
    stale_removed: int = 0
    duplicates_suppressed: int = 0


def deliver_owner_attention_pushes(
    session: Session,
    organization_id: UUID,
    user_id: UUID,
    envelope: dict[str, Any],
) -> OwnerPushDeliverySummary:
    if not delivery_configured():
        return OwnerPushDeliverySummary(configured=False)

    fingerprint = envelope.get("fingerprint")
    subscriptions = list(
        session.scalars(
            select(OwnerPushSubscription).where(
                OwnerPushSubscription.organization_id == organization_id,
                OwnerPushSubscription.user_id == user_id,
            )
        )
    )
    delivered = 0
    failed = 0
    stale_removed = 0
    duplicates_suppressed = 0
    state_changed = False

    for subscription in subscriptions:
        if fingerprint and subscription.last_delivered_fingerprint == fingerprint:
            duplicates_suppressed += 1
            continue

        result = send_owner_attention_push(subscription, envelope)
        if result.delivered:
            delivered += 1
            if fingerprint:
                subscription.last_delivered_fingerprint = fingerprint
                subscription.last_delivered_at = datetime.now(UTC)
                state_changed = True
            continue

        failed += 1
        if result.stale:
            session.delete(subscription)
            stale_removed += 1
            state_changed = True

    if state_changed:
        session.commit()

    return OwnerPushDeliverySummary(
        configured=True,
        attempted=len(subscriptions) - duplicates_suppressed,
        delivered=delivered,
        failed=failed,
        stale_removed=stale_removed,
        duplicates_suppressed=duplicates_suppressed,
    )
