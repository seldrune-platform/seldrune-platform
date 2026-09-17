from hashlib import sha256
from typing import Annotated, Any
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from backend.app.api.dependencies import SessionDep, require_org_permission
from backend.app.core.config import settings
from backend.app.core.rbac import Permission, Role
from backend.app.models.membership import Membership
from backend.app.models.owner_push_subscription import OwnerPushSubscription

router = APIRouter(prefix="/organizations", tags=["owner-push"])
OwnerDep = Annotated[Membership, Depends(require_org_permission(Permission.ORG_MANAGE))]


class OwnerPushKeys(BaseModel):
    p256dh: str = Field(min_length=32, max_length=512, pattern=r"^[A-Za-z0-9_-]+={0,2}$")
    auth: str = Field(min_length=8, max_length=256, pattern=r"^[A-Za-z0-9_-]+={0,2}$")


class OwnerPushSubscriptionCreate(BaseModel):
    endpoint: str = Field(min_length=16, max_length=4096)
    expiration_time: int | None = Field(default=None, ge=0)
    keys: OwnerPushKeys

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Push subscription endpoint must be HTTPS")
        if parsed.username or parsed.password or parsed.fragment:
            raise ValueError("Push subscription endpoint contains unsupported URL components")
        return value


def _require_owner(membership: Membership) -> None:
    if membership.role != Role.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner role required",
        )


def _endpoint_hash(endpoint: str) -> str:
    return sha256(endpoint.encode("utf-8")).hexdigest()


def _subscription_metadata(subscription: OwnerPushSubscription) -> dict[str, Any]:
    return {
        "id": str(subscription.id),
        "endpoint_hash": subscription.endpoint_hash,
        "expiration_time": subscription.expiration_time,
        "created_at": subscription.created_at,
        "updated_at": subscription.updated_at,
        "contains_endpoint": False,
        "contains_key_material": False,
    }


@router.get("/{organization_id}/owner-push/config", response_model=dict[str, Any])
def get_owner_push_config(
    organization_id: UUID,
    membership: OwnerDep,
) -> dict[str, Any]:
    _require_owner(membership)
    public_key = settings.owner_push_vapid_public_key
    return {
        "enabled": bool(public_key),
        "application_server_key": public_key,
        "subscription_persistence": True,
        "delivery_enabled": False,
        "notification_contract": "owner-attention-counts-v1",
        "governance": {
            "approval_gate_bypassed": False,
            "execution_triggered": False,
        },
    }


@router.get("/{organization_id}/owner-push/subscriptions", response_model=dict[str, Any])
def list_owner_push_subscriptions(
    organization_id: UUID,
    membership: OwnerDep,
    session: SessionDep,
) -> dict[str, Any]:
    _require_owner(membership)
    subscriptions = list(
        session.scalars(
            select(OwnerPushSubscription)
            .where(
                OwnerPushSubscription.organization_id == organization_id,
                OwnerPushSubscription.user_id == membership.user_id,
            )
            .order_by(OwnerPushSubscription.created_at.desc())
        )
    )
    return {
        "count": len(subscriptions),
        "subscriptions": [_subscription_metadata(item) for item in subscriptions],
        "contains_endpoint": False,
        "contains_key_material": False,
        "delivery_enabled": False,
    }


@router.post(
    "/{organization_id}/owner-push/subscriptions",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
)
def register_owner_push_subscription(
    organization_id: UUID,
    payload: OwnerPushSubscriptionCreate,
    request: Request,
    membership: OwnerDep,
    session: SessionDep,
) -> dict[str, Any]:
    _require_owner(membership)
    if not settings.owner_push_vapid_public_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Owner Web Push is not configured",
        )

    endpoint_hash = _endpoint_hash(payload.endpoint)
    subscription = session.scalar(
        select(OwnerPushSubscription).where(
            OwnerPushSubscription.organization_id == organization_id,
            OwnerPushSubscription.user_id == membership.user_id,
            OwnerPushSubscription.endpoint_hash == endpoint_hash,
        )
    )
    if subscription is None:
        subscription = OwnerPushSubscription(
            organization_id=organization_id,
            user_id=membership.user_id,
            endpoint_hash=endpoint_hash,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
            expiration_time=payload.expiration_time,
            user_agent=(request.headers.get("user-agent") or "")[:512] or None,
        )
        session.add(subscription)
    else:
        subscription.endpoint = payload.endpoint
        subscription.p256dh = payload.keys.p256dh
        subscription.auth = payload.keys.auth
        subscription.expiration_time = payload.expiration_time
        subscription.user_agent = (request.headers.get("user-agent") or "")[:512] or None

    session.commit()
    session.refresh(subscription)
    return {
        **_subscription_metadata(subscription),
        "registered": True,
        "delivery_enabled": False,
    }


@router.delete(
    "/{organization_id}/owner-push/subscriptions/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_owner_push_subscription(
    organization_id: UUID,
    subscription_id: UUID,
    membership: OwnerDep,
    session: SessionDep,
) -> Response:
    _require_owner(membership)
    subscription = session.scalar(
        select(OwnerPushSubscription).where(
            OwnerPushSubscription.id == subscription_id,
            OwnerPushSubscription.organization_id == organization_id,
            OwnerPushSubscription.user_id == membership.user_id,
        )
    )
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    session.delete(subscription)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
