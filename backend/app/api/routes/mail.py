from __future__ import annotations

import json
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.api.dependencies import CurrentUserDep, SessionDep
from backend.app.core.rbac import Role
from backend.app.models.mailbox_access import MailboxAccess
from backend.app.models.membership import Membership
from backend.app.models.seldrune_mail import Mailbox, MailDomain, MailDraft
from backend.app.models.user import User
from backend.app.services.secret_vault import (
    SecretVaultError,
    decrypt_secret_value,
    encrypt_secret_value,
)

WEB_ROOT = Path(__file__).resolve().parents[2] / "web"
page_router = APIRouter(tags=["seldrune-mail"])
router = APIRouter(prefix="/organizations/{organization_id}/mail", tags=["seldrune-mail"])

_DOMAIN_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$",
    re.IGNORECASE,
)
_LOCAL_PART_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._+-]{0,62}[a-z0-9]$|^[a-z0-9]$|^[a-z0-9][a-z0-9._+-]{1,62}$")
_DEFAULT_MAILBOXES = (
    ("you", "Seldrune Owner"),
    ("hello", "Seldrune Hello"),
    ("business", "Seldrune Business"),
    ("careers", "Seldrune Careers"),
)


@page_router.get("/mail", include_in_schema=False)
def mail_workspace_page() -> FileResponse:
    return FileResponse(WEB_ROOT / "mail.html")


class DomainCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str = Field(min_length=3, max_length=253)

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        normalized = value.strip().rstrip(".").lower()
        if not _DOMAIN_PATTERN.fullmatch(normalized):
            raise ValueError("Enter a valid domain name, such as mail.example.com.")
        return normalized


class MailboxCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain_id: UUID
    local_part: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=2, max_length=160)

    @field_validator("local_part")
    @classmethod
    def normalize_local_part(cls, value: str) -> str:
        normalized = value.strip().lower()
        if (
            not _LOCAL_PART_PATTERN.fullmatch(normalized)
            or ".." in normalized
            or normalized.startswith(".")
            or normalized.endswith(".")
        ):
            raise ValueError("Use a valid mailbox name, such as hello or team.eu.")
        return normalized

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        return value.strip()


class AccessGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    permission: Literal["read", "write"] = "write"


class DraftCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to: list[EmailStr] = Field(min_length=1, max_length=25)
    cc: list[EmailStr] = Field(default_factory=list, max_length=25)
    bcc: list[EmailStr] = Field(default_factory=list, max_length=25)
    subject: str = Field(default="", max_length=998)
    body: str = Field(default="", max_length=100_000)

    @field_validator("subject")
    @classmethod
    def normalize_subject(cls, value: str) -> str:
        return value.strip()


def _membership(
    session: SessionDep,
    organization_id: UUID,
    current_user: User,
) -> Membership:
    membership = session.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == current_user.id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="Organization membership required")
    return membership


def _is_manager(membership: Membership) -> bool:
    return membership.role in {Role.OWNER.value, Role.ADMIN.value}


def _require_manager(membership: Membership) -> None:
    if not _is_manager(membership):
        raise HTTPException(status_code=403, detail="Mail administration access required")


def _mailbox(
    session: SessionDep,
    organization_id: UUID,
    mailbox_id: UUID,
    user: User,
    *,
    write: bool = False,
) -> Mailbox:
    membership = _membership(session, organization_id, user)
    mailbox = session.scalar(
        select(Mailbox).where(
            Mailbox.id == mailbox_id,
            Mailbox.organization_id == organization_id,
        )
    )
    if mailbox is None:
        raise HTTPException(status_code=404, detail="Mailbox not found")

    access = session.get(MailboxAccess, (mailbox.id, user.id))
    if membership.role not in {Role.OWNER.value, Role.ADMIN.value}:
        if access is None:
            raise HTTPException(status_code=403, detail="Mailbox access required")
        if write and access.permission != "write":
            raise HTTPException(status_code=403, detail="Mailbox write access required")
    return mailbox


def _workspace(
    session: SessionDep,
    organization_id: UUID,
    membership: Membership,
    user: User,
) -> dict[str, object]:
    domains = list(
        session.scalars(
            select(MailDomain)
            .where(MailDomain.organization_id == organization_id)
            .order_by(MailDomain.domain)
        )
    )
    all_mailboxes = list(
        session.scalars(
            select(Mailbox)
            .where(Mailbox.organization_id == organization_id)
            .order_by(Mailbox.email_address)
        )
    )
    shared_access = {
        access.mailbox_id: access.permission
        for access in session.scalars(
            select(MailboxAccess).where(MailboxAccess.user_id == user.id)
        )
    }
    is_manager = _is_manager(membership)
    is_owner = membership.role == Role.OWNER.value
    visible_mailboxes = [
        item
        for item in all_mailboxes
        if is_manager or item.id in shared_access
    ]
    mailbox_rows = []
    for item in visible_mailboxes:
        domain = next((entry for entry in domains if entry.id == item.domain_id), None)
        mailbox_rows.append(
            {
                "id": str(item.id),
                "email_address": item.email_address,
                "display_name": item.display_name,
                "domain_id": str(item.domain_id),
                "domain": domain.domain if domain else None,
                "access": (
                    "owner"
                    if is_owner
                    else "write"
                    if is_manager
                    else shared_access.get(item.id, "read")
                ),
            }
        )
    domain_rows = [
        {
            "id": str(item.id),
            "domain": item.domain,
            "status": "verified" if item.verified_at is not None else "pending_dns",
            "verification_record_name": f"_seldrune-mail.{item.domain}",
            "verification_record_value": (
                f"seldrune-mail-verification={item.verification_token}"
                if is_manager
                else None
            ),
        }
        for item in domains
    ]

    members = []
    if is_manager:
        pairs = session.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.organization_id == organization_id)
            .order_by(User.display_name)
        ).all()
        members = [
            {
                "user_id": str(member.user_id),
                "email": member_user.email,
                "display_name": member_user.display_name,
                "role": member.role,
            }
            for member, member_user in pairs
        ]

    return {
        "organization_id": str(organization_id),
        "setup_required": not domains,
        "domains": domain_rows,
        "mailboxes": mailbox_rows,
        "members": members,
        "delivery": {
            "ready": False,
            "status": "mail_host_required",
            "message": (
                "Connect a mail host to receive and send email. This workspace is ready "
                "for mailbox sharing and drafts; domain ownership verification alone does "
                "not activate mail delivery."
            ),
        },
    }


@router.get("/workspace")
def get_mail_workspace(
    organization_id: UUID,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, object]:
    membership = _membership(session, organization_id, current_user)
    return _workspace(session, organization_id, membership, current_user)


@router.post("/setup", status_code=status.HTTP_201_CREATED)
def initialize_mail_workspace(
    organization_id: UUID,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, object]:
    membership = _membership(session, organization_id, current_user)
    _require_manager(membership)

    domain = session.scalar(
        select(MailDomain).where(
            MailDomain.organization_id == organization_id,
            MailDomain.domain == "seldrune.in",
        )
    )
    if domain is None:
        domain = MailDomain(
            organization_id=organization_id,
            domain="seldrune.in",
            verification_token=secrets.token_hex(24),
            created_by_user_id=current_user.id,
        )
        session.add(domain)
        session.flush()

    for local_part, display_name in _DEFAULT_MAILBOXES:
        address = f"{local_part}@{domain.domain}"
        existing = session.scalar(
            select(Mailbox.id).where(
                Mailbox.organization_id == organization_id,
                Mailbox.email_address == address,
            )
        )
        if existing is None:
            session.add(
                Mailbox(
                    organization_id=organization_id,
                    domain_id=domain.id,
                    email_address=address,
                    display_name=display_name,
                    created_by_user_id=current_user.id,
                )
            )
    session.commit()
    session.refresh(domain)
    return _workspace(session, organization_id, membership, current_user)


@router.post("/domains", status_code=status.HTTP_201_CREATED)
def add_mail_domain(
    organization_id: UUID,
    payload: DomainCreate,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, object]:
    membership = _membership(session, organization_id, current_user)
    _require_manager(membership)
    if session.scalar(
        select(MailDomain.id).where(
            MailDomain.organization_id == organization_id,
            MailDomain.domain == payload.domain,
        )
    ):
        raise HTTPException(status_code=409, detail="That domain is already connected")
    domain = MailDomain(
        organization_id=organization_id,
        domain=payload.domain,
        verification_token=secrets.token_hex(24),
        created_by_user_id=current_user.id,
    )
    session.add(domain)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="That domain is already connected") from exc
    session.refresh(domain)
    return {
        "id": str(domain.id),
        "domain": domain.domain,
        "status": "pending_dns",
        "verification_record_name": f"_seldrune-mail.{domain.domain}",
        "verification_record_value": f"seldrune-mail-verification={domain.verification_token}",
    }


@router.post("/domains/{domain_id}/verify")
def verify_mail_domain(
    organization_id: UUID,
    domain_id: UUID,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, str]:
    membership = _membership(session, organization_id, current_user)
    _require_manager(membership)
    domain = session.scalar(
        select(MailDomain).where(
            MailDomain.id == domain_id,
            MailDomain.organization_id == organization_id,
        )
    )
    if domain is None:
        raise HTTPException(status_code=404, detail="Domain not found")
    record_name = f"_seldrune-mail.{domain.domain}"
    try:
        response = httpx.get(
            "https://cloudflare-dns.com/dns-query",
            params={"name": record_name, "type": "TXT"},
            headers={"accept": "application/dns-json"},
            timeout=5.0,
        )
        response.raise_for_status()
        answers = response.json().get("Answer", [])
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=503,
            detail="The DNS check is temporarily unavailable. Try again shortly.",
        ) from exc

    expected = f"seldrune-mail-verification={domain.verification_token}"
    if not any(
        str(item.get("data", "")).strip().strip('"') == expected
        for item in answers
        if isinstance(item, dict)
    ):
        raise HTTPException(status_code=409, detail="Verification TXT record was not found")

    domain.verified_at = datetime.now(UTC)
    session.commit()
    return {"domain": domain.domain, "status": "verified"}


@router.post("/mailboxes", status_code=status.HTTP_201_CREATED)
def create_mailbox(
    organization_id: UUID,
    payload: MailboxCreate,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, str]:
    membership = _membership(session, organization_id, current_user)
    _require_manager(membership)
    domain = session.scalar(
        select(MailDomain).where(
            MailDomain.id == payload.domain_id,
            MailDomain.organization_id == organization_id,
        )
    )
    if domain is None:
        raise HTTPException(status_code=404, detail="Mail domain not found")
    address = f"{payload.local_part}@{domain.domain}"
    mailbox = Mailbox(
        organization_id=organization_id,
        domain_id=domain.id,
        email_address=address,
        display_name=payload.display_name,
        created_by_user_id=current_user.id,
    )
    session.add(mailbox)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Mailbox address already exists") from exc
    session.refresh(mailbox)
    return {
        "id": str(mailbox.id),
        "email_address": mailbox.email_address,
        "display_name": mailbox.display_name,
    }


@router.post("/mailboxes/{mailbox_id}/access", status_code=status.HTTP_201_CREATED)
def grant_mailbox_access(
    organization_id: UUID,
    mailbox_id: UUID,
    payload: AccessGrant,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, str]:
    membership = _membership(session, organization_id, current_user)
    _require_manager(membership)
    mailbox = session.scalar(
        select(Mailbox).where(
            Mailbox.id == mailbox_id,
            Mailbox.organization_id == organization_id,
        )
    )
    if mailbox is None:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    user = session.scalar(select(User).where(User.email == str(payload.email).lower()))
    target_membership = (
        session.scalar(
            select(Membership).where(
                Membership.organization_id == organization_id,
                Membership.user_id == user.id,
            )
        )
        if user is not None
        else None
    )
    if user is None or target_membership is None:
        raise HTTPException(status_code=404, detail="User must be an organization member first")
    if target_membership.role == Role.OWNER.value:
        raise HTTPException(
            status_code=409,
            detail="Organization owners already have access to every mailbox",
        )
    access = session.get(MailboxAccess, (mailbox.id, user.id))
    if access is None:
        access = MailboxAccess(
            mailbox_id=mailbox.id,
            user_id=user.id,
            permission=payload.permission,
            granted_by_user_id=current_user.id,
        )
        session.add(access)
    else:
        access.permission = payload.permission
        access.granted_by_user_id = current_user.id
    session.commit()
    return {
        "mailbox_id": str(mailbox.id),
        "user_id": str(user.id),
        "email": user.email,
        "permission": access.permission,
    }


@router.delete(
    "/mailboxes/{mailbox_id}/access/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_mailbox_access(
    organization_id: UUID,
    mailbox_id: UUID,
    user_id: UUID,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> None:
    membership = _membership(session, organization_id, current_user)
    _require_manager(membership)
    mailbox = session.scalar(
        select(Mailbox).where(
            Mailbox.id == mailbox_id,
            Mailbox.organization_id == organization_id,
        )
    )
    if mailbox is None:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    access = session.get(MailboxAccess, (mailbox_id, user_id))
    if access is None:
        raise HTTPException(status_code=404, detail="Mailbox share not found")
    session.delete(access)
    session.commit()


@router.get("/mailboxes/{mailbox_id}/drafts")
def list_drafts(
    organization_id: UUID,
    mailbox_id: UUID,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> list[dict[str, object]]:
    _mailbox(session, organization_id, mailbox_id, current_user)
    drafts = session.scalars(
        select(MailDraft)
        .where(MailDraft.mailbox_id == mailbox_id)
        .order_by(MailDraft.updated_at.desc())
    )
    return [_draft_response(item) for item in drafts]


@router.post("/mailboxes/{mailbox_id}/drafts", status_code=status.HTTP_201_CREATED)
def save_draft(
    organization_id: UUID,
    mailbox_id: UUID,
    payload: DraftCreate,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict[str, object]:
    _mailbox(session, organization_id, mailbox_id, current_user, write=True)
    content = {
        "to": [str(item) for item in payload.to],
        "cc": [str(item) for item in payload.cc],
        "bcc": [str(item) for item in payload.bcc],
        "subject": payload.subject,
        "body": payload.body,
    }
    draft = MailDraft(
        mailbox_id=mailbox_id,
        created_by_user_id=current_user.id,
        encrypted_payload=encrypt_secret_value(json.dumps(content, ensure_ascii=False)),
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)
    return _draft_response(draft)


@router.delete(
    "/mailboxes/{mailbox_id}/drafts/{draft_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_draft(
    organization_id: UUID,
    mailbox_id: UUID,
    draft_id: UUID,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> None:
    _mailbox(session, organization_id, mailbox_id, current_user, write=True)
    draft = session.scalar(
        select(MailDraft).where(
            MailDraft.id == draft_id,
            MailDraft.mailbox_id == mailbox_id,
        )
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    session.delete(draft)
    session.commit()


def _draft_response(draft: MailDraft) -> dict[str, object]:
    try:
        content = json.loads(decrypt_secret_value(draft.encrypted_payload))
    except (SecretVaultError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=500, detail="Draft could not be opened") from exc
    return {
        "id": str(draft.id),
        "to": content.get("to", []),
        "cc": content.get("cc", []),
        "bcc": content.get("bcc", []),
        "subject": content.get("subject", ""),
        "body": content.get("body", ""),
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
    }
