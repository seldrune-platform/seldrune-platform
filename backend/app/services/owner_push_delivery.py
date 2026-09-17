import json
from dataclasses import dataclass
from typing import Any

from pywebpush import WebPushException, webpush

from backend.app.core.config import settings
from backend.app.models.owner_push_subscription import OwnerPushSubscription


@dataclass(frozen=True)
class PushDeliveryResult:
    delivered: bool
    stale: bool = False
    status_code: int | None = None


def delivery_configured() -> bool:
    return bool(
        settings.owner_push_vapid_public_key
        and settings.owner_push_vapid_private_key
        and settings.owner_push_vapid_subject
    )


def send_owner_attention_push(
    subscription: OwnerPushSubscription,
    envelope: dict[str, Any],
) -> PushDeliveryResult:
    if not delivery_configured():
        return PushDeliveryResult(delivered=False)

    payload = {
        "contract": "owner-attention-counts-v1",
        "fingerprint": envelope.get("fingerprint"),
        "notification": envelope.get("notification", {}),
    }
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(payload, separators=(",", ":")),
            vapid_private_key=settings.owner_push_vapid_private_key,
            vapid_claims={"sub": settings.owner_push_vapid_subject},
            ttl=120,
        )
        return PushDeliveryResult(delivered=True)
    except WebPushException as exc:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        return PushDeliveryResult(
            delivered=False,
            stale=status_code in {404, 410},
            status_code=status_code,
        )
