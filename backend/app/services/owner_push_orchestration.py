from dataclasses import dataclass
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


def deliver_owner_attention_pushes(
    session: Session,
    organization_id: UUID,
    user_id: UUID,
    envelope: dict[str, Any],
) -> OwnerPushDeliverySummary:
    if not delivery_configured():
        return OwnerPushDeliverySummary(configured=False)

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

    for subscription in subscriptions:
        result = send_owner_attention_push(subscription, envelope)
        if result.delivered:
            delivered += 1
            continue
        failed += 1
        if result.stale:
            session.delete(subscription)
            stale_removed += 1

    if stale_removed:
        session.commit()

    return OwnerPushDeliverySummary(
        configured=True,
        attempted=len(subscriptions),
        delivered=delivered,
        failed=failed,
        stale_removed=stale_removed,
    )
