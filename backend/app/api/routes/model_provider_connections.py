from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from backend.app.api.dependencies import CurrentUserDep, SessionDep, require_org_permission
from backend.app.core.config import settings
from backend.app.core.rbac import Permission
from backend.app.models.membership import Membership
from backend.app.models.secret_reference import SecretReference
from backend.app.services.audit import record_audit
from backend.app.services.model_provider_registry import (
    MODEL_PROVIDER_CREDENTIALS,
    configured_model_provider_vaults,
    model_provider_statuses,
)
from backend.app.services.provider_preflight import preflight_provider_credential
from backend.app.services.secret_vault import encrypt_secret_value, vault_locator

router = APIRouter(prefix="/organizations", tags=["model-provider-connections"])
manage_dependency = require_org_permission(Permission.SECRETS_MANAGE)
SecretManageDep = Annotated[Membership, Depends(manage_dependency)]


class ModelProviderCredentialUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")
    secret_value: str = Field(min_length=8, max_length=20000)


def _provider_or_404(provider: str) -> dict[str, str]:
    definition = MODEL_PROVIDER_CREDENTIALS.get(provider)
    if definition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unsupported model provider connection",
        )
    return definition


def _credential_reference(
    session: SessionDep,
    *,
    organization_id: UUID,
    slug: str,
) -> SecretReference | None:
    return session.scalar(
        select(SecretReference).where(
            SecretReference.organization_id == organization_id,
            SecretReference.slug == slug,
        )
    )


@router.get(
    "/{organization_id}/model-provider-connections",
    response_model=dict,
)
def list_model_provider_connections(
    organization_id: UUID,
    _membership: SecretManageDep,
    session: SessionDep,
) -> dict:
    vault_configured = configured_model_provider_vaults(
        session,
        organization_id=organization_id,
    )
    statuses = {
        str(item["provider"]): item
        for item in model_provider_statuses(
            settings,
            vault_configured=vault_configured,
        )
    }
    providers = []
    for provider, definition in MODEL_PROVIDER_CREDENTIALS.items():
        item = statuses[provider]
        providers.append(
            {
                "provider": provider,
                "label": definition["label"],
                "model": item["model"],
                "configured": bool(item["configured"]),
                "source": item["source"],
                "text_only": bool(item["text_only"]),
                "credential_kind": "API key",
            }
        )
    return {"providers": providers}


@router.post(
    "/{organization_id}/model-provider-connections/{provider}",
    response_model=dict,
)
def verify_and_store_model_provider_credential(
    organization_id: UUID,
    provider: str,
    payload: ModelProviderCredentialUpsert,
    _membership: SecretManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict:
    definition = _provider_or_404(provider)
    secret_value = payload.secret_value.strip()
    verification = preflight_provider_credential(provider, secret_value)
    if not verification.get("verified"):
        record_audit(
            session,
            organization_id=organization_id,
            actor_user_id=current_user.id,
            action="model_provider.credential_verification_failed",
            resource_type="organization",
            resource_id=str(organization_id),
            details={
                "provider": provider,
                "status": verification.get("status"),
                "http_status": verification.get("http_status"),
            },
        )
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": (
                    "The provider could not verify this API key, so Seldrune did not save it."
                ),
                "verification": verification,
            },
        )

    reference = _credential_reference(
        session,
        organization_id=organization_id,
        slug=definition["slug"],
    )
    encrypted = encrypt_secret_value(secret_value)
    action = "model_provider.credential_rotated"
    if reference is None:
        reference = SecretReference(
            organization_id=organization_id,
            created_by_user_id=current_user.id,
            name=definition["name"],
            slug=definition["slug"],
            provider="vault",
            locator=vault_locator(),
            encrypted_value=encrypted,
            status="active",
        )
        session.add(reference)
        session.flush()
        action = "model_provider.credential_created"
    else:
        reference.created_by_user_id = current_user.id
        reference.provider = "vault"
        reference.locator = vault_locator()
        reference.encrypted_value = encrypted
        reference.status = "active"

    record_audit(
        session,
        organization_id=organization_id,
        actor_user_id=current_user.id,
        action=action,
        resource_type="secret_reference",
        resource_id=str(reference.id),
        details={"provider": provider, "credential_slug": definition["slug"]},
    )
    session.commit()
    return {
        "provider": provider,
        "configured": True,
        "source": "vault",
        "verification": verification,
    }


@router.delete(
    "/{organization_id}/model-provider-connections/{provider}",
    response_model=dict,
)
def disconnect_model_provider_credential(
    organization_id: UUID,
    provider: str,
    _membership: SecretManageDep,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> dict:
    definition = _provider_or_404(provider)
    reference = _credential_reference(
        session,
        organization_id=organization_id,
        slug=definition["slug"],
    )
    if reference is not None:
        reference.status = "disabled"
        reference.encrypted_value = None
        record_audit(
            session,
            organization_id=organization_id,
            actor_user_id=current_user.id,
            action="model_provider.credential_disconnected",
            resource_type="secret_reference",
            resource_id=str(reference.id),
            details={"provider": provider, "credential_slug": definition["slug"]},
        )
        session.commit()

    vault_configured = configured_model_provider_vaults(
        session,
        organization_id=organization_id,
    )
    provider_status = next(
        (
            item
            for item in model_provider_statuses(
                settings,
                vault_configured=vault_configured,
            )
            if item["provider"] == provider
        ),
        {},
    )
    return {
        "provider": provider,
        "vault_removed": reference is not None,
        "configured": bool(provider_status.get("configured")),
        "source": provider_status.get("source", "missing"),
        "detail": (
            "Seldrune removed the saved credential. Revoke it at the provider to invalidate it."
            if reference is not None
            else "No Seldrune vault credential was saved."
        ),
    }
