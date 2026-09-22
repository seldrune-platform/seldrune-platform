from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.api.dependencies import CurrentUserDep, SessionDep, require_org_permission
from backend.app.core.rbac import Permission
from backend.app.models.membership import Membership
from backend.app.models.research_connector import ResearchConnector
from backend.app.models.secret_reference import SecretReference
from backend.app.models.tool_definition import ToolDefinition
from backend.app.models.webhook import WebhookEndpoint
from backend.app.schemas.secret_references import (
    SecretReferenceCreate,
    SecretReferencePublic,
    SecretReferenceUpdate,
)
from backend.app.services.audit import record_audit
from backend.app.services.secret_vault import SecretVaultError, validate_secret_locator

router = APIRouter(prefix="/organizations", tags=["secret-references"])
secret_manage_dependency = require_org_permission(Permission.SECRETS_MANAGE)
SecretManageDep = Annotated[Membership, Depends(secret_manage_dependency)]


def _get_reference(
    session: SessionDep,
    organization_id: UUID,
    reference_id: UUID,
) -> SecretReference:
    reference = session.scalar(
        select(SecretReference).where(
            SecretReference.id == reference_id,
            SecretReference.organization_id == organization_id,
        )
    )
    if reference is None:
        raise HTTPException(status_code=404, detail="Secret reference not found")
    return reference


def _validate_locator(provider: str, locator: str) -> None:
    try:
        validate_secret_locator(provider, locator)
    except (SecretVaultError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _dependency_kinds(
    session: SessionDep,
    organization_id: UUID,
    reference_id: UUID,
) -> list[str]:
    kinds: list[str] = []
    connector_id = session.scalar(
        select(ResearchConnector.id)
        .where(
            ResearchConnector.organization_id == organization_id,
            ResearchConnector.secret_reference_id == reference_id,
        )
        .limit(1)
    )
    if connector_id is not None:
        kinds.append("research_connector")
    webhook_id = session.scalar(
        select(WebhookEndpoint.id)
        .where(
            WebhookEndpoint.organization_id == organization_id,
            WebhookEndpoint.secret_reference_id == reference_id,
        )
        .limit(1)
    )
    if webhook_id is not None:
        kinds.append("webhook_endpoint")
    tool_id = session.scalar(
        select(ToolDefinition.id)
        .where(
            ToolDefinition.organization_id == organization_id,
            ToolDefinition.credential_reference_id == reference_id,
        )
        .limit(1)
    )
    if tool_id is not None:
        kinds.append("tool_definition")
    return kinds


@router.post(
    "/{organization_id}/secret-references",
    response_model=SecretReferencePublic,
    status_code=status.HTTP_201_CREATED,
)
def create_secret_reference(
    organization_id: UUID,
    payload: SecretReferenceCreate,
    _membership: SecretManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> SecretReference:
    provider = payload.provider.value
    locator = payload.locator.strip()
    _validate_locator(provider, locator)
    existing = session.scalar(
        select(SecretReference.id).where(
            SecretReference.organization_id == organization_id,
            SecretReference.slug == payload.slug,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Secret reference slug already exists")

    reference = SecretReference(
        organization_id=organization_id,
        created_by_user_id=current_user.id,
        name=payload.name.strip(),
        slug=payload.slug,
        provider=provider,
        locator=locator,
    )
    session.add(reference)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Secret reference conflicts with existing data",
        ) from exc
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="secret_reference.created",
        resource_type="secret_reference",
        resource_id=str(reference.id),
        details={"slug": reference.slug, "provider": reference.provider},
    )
    session.commit()
    session.refresh(reference)
    return reference


@router.get(
    "/{organization_id}/secret-references",
    response_model=list[SecretReferencePublic],
)
def list_secret_references(
    organization_id: UUID,
    _membership: SecretManageDep,
    session: SessionDep,
) -> list[SecretReference]:
    return list(
        session.scalars(
            select(SecretReference)
            .where(SecretReference.organization_id == organization_id)
            .order_by(SecretReference.name, SecretReference.slug)
        )
    )


@router.get(
    "/{organization_id}/secret-references/{reference_id}",
    response_model=SecretReferencePublic,
)
def get_secret_reference(
    organization_id: UUID,
    reference_id: UUID,
    _membership: SecretManageDep,
    session: SessionDep,
) -> SecretReference:
    return _get_reference(session, organization_id, reference_id)


@router.patch(
    "/{organization_id}/secret-references/{reference_id}",
    response_model=SecretReferencePublic,
)
def update_secret_reference(
    organization_id: UUID,
    reference_id: UUID,
    payload: SecretReferenceUpdate,
    _membership: SecretManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> SecretReference:
    reference = _get_reference(session, organization_id, reference_id)
    changes = payload.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=400, detail="Secret reference fields cannot be null")
    if "locator" in changes:
        changes["locator"] = changes["locator"].strip()
        _validate_locator(reference.provider, changes["locator"])
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    if "status" in changes:
        changes["status"] = changes["status"].value

    changed_fields = [
        field for field, value in changes.items() if getattr(reference, field) != value
    ]
    if not changed_fields:
        return reference
    for field in changed_fields:
        setattr(reference, field, changes[field])
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="secret_reference.updated",
        resource_type="secret_reference",
        resource_id=str(reference.id),
        details={"changed_fields": sorted(changed_fields)},
    )
    session.commit()
    session.refresh(reference)
    return reference


@router.delete(
    "/{organization_id}/secret-references/{reference_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_secret_reference(
    organization_id: UUID,
    reference_id: UUID,
    _membership: SecretManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> None:
    reference = _get_reference(session, organization_id, reference_id)
    dependency_kinds = _dependency_kinds(session, organization_id, reference.id)
    if dependency_kinds:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Secret reference is still in use",
        )
    resource_id = str(reference.id)
    details = {"slug": reference.slug, "provider": reference.provider}
    session.delete(reference)
    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action="secret_reference.deleted",
        resource_type="secret_reference",
        resource_id=resource_id,
        details=details,
    )
    session.commit()
