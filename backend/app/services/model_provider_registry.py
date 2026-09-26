from os import getenv

from backend.app.core.config import Settings


def model_provider_statuses(settings: Settings) -> list[dict[str, str | bool]]:
    """Return safe configuration status; never expose credentials or probe APIs."""
    openai_configured = bool(getenv("OPENAI_API_KEY"))
    compatible_configured = bool((settings.model_compatible_base_url or "").strip())
    gemini_configured = bool((settings.gemini_api_key or "").strip())
    anthropic_configured = bool((settings.anthropic_api_key or "").strip())

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
            "configuration_hint": (
                "OPENAI_API_KEY"
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
            "configuration_hint": "" if openai_configured else "OPENAI_API_KEY",
            "text_only": False,
        },
        {
            "provider": "openai_compatible",
            "label": "OpenAI-compatible",
            "configured": compatible_configured,
            "model": settings.model_default,
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
            "configuration_hint": (
                "" if gemini_configured else "SELDRUNE_GEMINI_API_KEY"
            ),
            "text_only": True,
        },
        {
            "provider": "anthropic",
            "label": "Anthropic",
            "configured": anthropic_configured,
            "model": settings.anthropic_model,
            "configuration_hint": (
                "" if anthropic_configured else "SELDRUNE_ANTHROPIC_API_KEY"
            ),
            "text_only": True,
        },
    ]
