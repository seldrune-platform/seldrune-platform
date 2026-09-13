from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select

from backend.app.api.dependencies import SessionDep, require_org_permission
from backend.app.core.rbac import Permission
from backend.app.models.membership import Membership
from backend.app.models.user import User
from backend.app.schemas.auth import MemberPublic

router = APIRouter(prefix="/organizations", tags=["organizations"])
members_read_dependency = require_org_permission(Permission.MEMBERS_READ)
MembersReadDep = Annotated[Membership, Depends(members_read_dependency)]


@router.get("/{organization_id}/members", response_model=list[MemberPublic])
def list_members(
    organization_id: UUID,
    _membership: MembersReadDep,
    session: SessionDep,
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
