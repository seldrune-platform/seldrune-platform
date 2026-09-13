from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_org_permission
from backend.app.core.rbac import Permission
from backend.app.db.session import get_db
from backend.app.models.membership import Membership
from backend.app.models.user import User
from backend.app.schemas.auth import MemberPublic

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("/{organization_id}/members", response_model=list[MemberPublic])
def list_members(
    organization_id: UUID,
    _membership: Membership = Depends(require_org_permission(Permission.MEMBERS_READ)),
    session: Session = Depends(get_db),
) -> list[MemberPublic]:
    rows = session.execute(
        select(User, Membership.role)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.organization_id == organization_id)
        .order_by(User.display_name)
    ).all()

    return [
        MemberPublic(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=role,
        )
        for user, role in rows
    ]
