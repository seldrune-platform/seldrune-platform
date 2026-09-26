from __future__ import annotations

from os import getenv
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.models.secret_reference import SecretReference
from backend.app.services.secret_vault import SecretVaultError, resolve_secret


MODEL_PROVIDER_CREDENTIALS: dict[str, dict[str, str]] = {
    "openai": {
        "slug": "model-openai-api-key",
        "name": "OpenAI API key",
        "label": "OpenAI",
    },
    "gemini": {
        "slug": "model-gemini-api-key",
        "name": "Gemini API key",
        "label": "Gemini",
    },
    "anthropic": {
        "slug": "model-anthropic-api-key",
        "name": "Anthropic API key",
        "label": "Anthropic",
    },
}


def get_model_provider_credential(
    session: Session,
    *,
    organization_id: UUID,
    provider: str,
) -> str | None:
    """Resolve one active, organization-scoped model credential without returning it in APIs."""
    definition = MODEL_PROVIDER_CREDENTIALS.get(provider)
    if definition is None:
        return None
    reference = session.scalar(
        select(SecretReference).where(
            SecretReference.organization_id == organization_id,
            SecretReference.slug == definition["slug"],
        )
    )
    if reference is None or reference.status != "active":
        return None
    return resolve_secret(reference)


def configured_model_provider_vaults(
    session: Session,
    *,
    organization_id: UUID,
) -> set[str]:
    configured: set[str] = set()
    for provider in MODEL_PROVIDER_CREDENTIALS:
        try:
            if get_model_provider_credential(
                session,
                organization_id=organization_id,
                provider=provider,
            ):
                configured.add(provider)
        except SecretVaultError:
            continue
    return configured


def model_provider_statuses(
    settings: Settings,
    *,
    vault_configured: set[str] | frozenset[str] = frozenset(),
) -> list[dict[str, str | bool]]:
    """Return safe provider readiness; never expose credentials or probe APIs."""
    openai_env_configured = bool(getenv("OPENAI_API_KEY"))
    compatible_configured = bool((settings.model_compatible_base_url or "").strip())
    gemini_env_configured = bool((settings.gemini_api_key or "").strip())
    anthropic_env_configured = bool((settings.anthropic_api_key or "").strip())

    openai_configured = openai_env_configured or "openai" in vault_configured
    gemini_configured = gemini_env_configured or "gemini" in vault_configured
    anthropic_configured = anthropic_env_configured or "anthropic" in vault_configured

    def source(provider: str, env_configured: bool) -> str:
        if provider in vault_configured:
            return "vault"
        if env_configured:
            return "server"
        return "missing"

    active_provider = settings.model_provider
    active_configured = (
        openai_configured
        if active_provider == "openai"
        else compatible_configured
        if active_provider == "openai_compatible"
        else False
    )
    active_model = (
        settings.model_economy
        if active_provider == "openai"
        else settings.model_default
        if active_provider == "openai_compatible"
        else settings.model_default
    )

    return [
        {
            "provider": "auto",
            "label": "Seldrune Auto",
            "configured": active_configured,
            "model": active_model,
            "source": (
                source(active_provider, openai_env_configured)
                if active_provider == "openai"
                else "server" if active_provider == "openai_compatible" and compatible_configured
                else "missing"
            ),
            "configuration_hint": (
                "OPENAI_API_KEY or a saved OpenAI connection"
                if active_provider == "openai" and not openai_configured
                else "SELDRUNE_MODEL_COMPATIBLE_BASE_URL"
                if active_provider == "openai_compatible" and not compatible_configured
                else ""
            ),
            "text_only": False,
        },
        {
            "provider": "openai",
            "label": "OpenAI",
            "configured": openai_configured,
            "model": settings.model_economy,
            "source": source("openai", openai_env_configured),
            "configuration_hint": (
                "" if openai_configured else "OpenAI API key"
            ),
            "text_only": False,
        },
        {
            "provider": "openai_compatible",
            "label": "OpenAI-compatible",
            "configured": compatible_configured,
            "model": settings.model_default,
            "source": "server" if compatible_configured else "missing",
            "configuration_hint": (
                "" if compatible_configured else "SELDRUNE_MODEL_COMPATIBLE_BASE_URL"
            ),
            "text_only": True,
        },
        {
            "provider": "gemini",
            "label": "Gemini",
            "configured": gemini_configured,
            "model": settings.gemini_model,
            "source": source("gemini", gemini_env_configured),
            "configuration_hint": "" if gemini_configured else "Gemini API key",
            "text_only": True,
        },
        {
            "provider": "anthropic",
            "label": "Anthropic",
            "configured": anthropic_configured,
            "model": settings.anthropic_model,
            "source": source("anthropic", anthropic_env_configured),
            "configuration_hint": "" if anthropic_configured else "Anthropic API key",
            "text_only": True,
        },
    ]
