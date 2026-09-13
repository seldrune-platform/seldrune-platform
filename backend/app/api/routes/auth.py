from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.api.dependencies import CurrentUserDep, SessionDep
from backend.app.core.config import settings
from backend.app.core.rbac import ROLE_PERMISSIONS, Role
from backend.app.core.security import create_access_token, hash_password, verify_password
from backend.app.models.membership import Membership
from backend.app.models.organization import Organization
from backend.app.models.user import User
from backend.app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    MeResponse,
    MembershipPublic,
    OrganizationPublic,
    RegisterRequest,
    UserPublic,
)
from backend.app.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_response(user: User) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(user.id),
        expires_in=settings.auth_access_token_minutes * 60,
        user=UserPublic.model_validate(user),
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, session: SessionDep) -> AuthResponse:
    email = str(payload.email).strip().lower()
    slug = payload.organization_slug.strip().lower()

    if session.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    if session.scalar(select(Organization).where(Organization.slug == slug)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization slug already exists",
        )

    user = User(
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
    )
    organization = Organization(name=payload.organization_name.strip(), slug=slug)
    session.add_all([user, organization])

    try:
        session.flush()
        membership = Membership(
            organization_id=organization.id,
            user_id=user.id,
            role=Role.OWNER.value,
        )
        session.add(membership)
        record_audit(
            session,
            action="auth.register",
            resource_type="user",
            organization_id=organization.id,
            actor_user_id=user.id,
            resource_id=str(user.id),
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registration conflicts with an existing account",
        ) from exc

    return _auth_response(user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, session: SessionDep) -> AuthResponse:
    email = str(payload.email).strip().lower()
    user = session.scalar(select(User).where(User.email == email))

    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    record_audit(
        session,
        action="auth.login",
        resource_type="user",
        actor_user_id=user.id,
        resource_id=str(user.id),
    )
    session.commit()
    return _auth_response(user)


@router.get("/me", response_model=MeResponse)
def me(current_user: CurrentUserDep, session: SessionDep) -> MeResponse:
    rows = session.execute(
        select(Membership, Organization)
        .join(Organization, Organization.id == Membership.organization_id)
        .where(Membership.user_id == current_user.id)
        .order_by(Organization.name)
    ).all()

    memberships = [
        MembershipPublic(
            organization=OrganizationPublic.model_validate(organization),
            role=membership.role,
            permissions=sorted(
                permission.value for permission in ROLE_PERMISSIONS[Role(membership.role)]
            ),
        )
        for membership, organization in rows
    ]
    return MeResponse(
        user=UserPublic.model_validate(current_user),
        memberships=memberships,
    )
