from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.rbac import Permission, has_permission
from backend.app.core.security import TokenError, decode_access_token
from backend.app.db.session import get_db
from backend.app.models.membership import Membership
from backend.app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")
TokenDep = Annotated[str, Depends(oauth2_scheme)]
SessionDep = Annotated[Session, Depends(get_db)]


def get_current_user(token: TokenDep, session: SessionDep) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = decode_access_token(token)
    except TokenError as exc:
        raise credentials_error from exc

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_org_permission(
    permission: Permission,
) -> Callable[..., Membership]:
    def dependency(
        organization_id: UUID,
        current_user: CurrentUserDep,
        session: SessionDep,
    ) -> Membership:
        membership = session.scalar(
            select(Membership).where(
                Membership.organization_id == organization_id,
                Membership.user_id == current_user.id,
            )
        )
        if membership is None or not has_permission(membership.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient organization permission",
            )
        return membership

    return dependency
