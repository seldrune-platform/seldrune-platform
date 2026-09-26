from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SELDRUNE_",
        extra="ignore",
    )

    app_name: str = "Seldrune Platform"
    app_version: str = "1.4.0"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    enable_docs: bool = True
    release_sha: str | None = None
    database_url: str = "sqlite+pysqlite:///./seldrune.db"
    auth_secret_key: str = "development-only-change-this-secret"
    auth_access_token_minutes: int = 30
    auth_refresh_token_days: int = 30
    auth_login_failure_limit: int = 5
    auth_login_failure_window_minutes: int = 15
    public_app_url: str = "http://localhost:8000"
    email_from_address: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = True
    smtp_timeout_seconds: float = 10.0
    github_default_owner: str | None = "seldrune-platform"
    github_default_repo: str | None = "seldrune-platform"
    github_default_ref: str | None = "main"
    render_default_service_id: str | None = None
    agent_auto_grant_production_tools: bool = False
    model_provider: str = "mock"
    model_default: str = "mock-v1"
    model_compatible_base_url: str | None = None
    model_compatible_api_key: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"
    model_economy: str = "gpt-5.6-luna"
    model_balanced: str = "gpt-5.6-terra"
    model_premium: str = "gpt-5.6-sol"
    model_timeout_seconds: float = 60.0
    model_max_output_tokens: int = 900
    ai_cost_governor_enabled: bool = True
    ai_request_max_usd: float = 0.04
    ai_daily_max_usd: float = 1.0
    ai_monthly_max_usd: float = 15.0
    ai_spend_warning_ratio: float = 0.70
    ai_conservation_ratio: float = 0.80
    ai_pdf_request_max_usd: float = 0.04
    ai_pdf_max_total_usd: float = 0.10
    ai_pdf_max_attempts: int = 2
    ai_pdf_max_output_tokens: int = 2200
    pdf_brain_enabled: bool = True
    pdf_brain_min_confidence: float = 0.78
    pdf_local_ocr_enabled: bool = True
    pdf_external_fallback_enabled: bool = False
    ai_image_job_max_usd: float = 0.08
    ai_video_job_max_usd: float = 0.40
    ai_video_default_seconds: int = 4
    ai_video_max_seconds: int = 6
    ai_media_batch_preferred: bool = True
    ai_image_detail: str = "low"
    ai_pdf_detail: str = "low"
    ai_prompt_cache_enabled: bool = True
    ai_exact_token_preflight: bool = True
    project_estimated_cost_per_step_usd: float = 0.05
    knowledge_retrieval_limit: int = 6
    knowledge_context_max_chars: int = 4500
    owner_push_vapid_public_key: str | None = None
    owner_push_vapid_private_key: str | None = None
    owner_push_vapid_subject: str | None = None
    life_worker_interval_seconds: float = 30.0
    life_worker_max_commands: int = 5
    life_worker_max_steps_per_command: int = 5
    life_worker_max_retries_per_step: int = 1

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        if self.environment.lower() in {"prod", "production"}:
            if self.auth_secret_key == "development-only-change-this-secret":
                raise ValueError("SELDRUNE_AUTH_SECRET_KEY must be set in production")
            if len(self.auth_secret_key) < 32:
                raise ValueError("SELDRUNE_AUTH_SECRET_KEY must be at least 32 characters")
        if self.auth_refresh_token_days <= 0:
            raise ValueError("SELDRUNE_AUTH_REFRESH_TOKEN_DAYS must be positive")
        if self.auth_login_failure_limit <= 0:
            raise ValueError("SELDRUNE_AUTH_LOGIN_FAILURE_LIMIT must be positive")
        if self.auth_login_failure_window_minutes <= 0:
            raise ValueError("SELDRUNE_AUTH_LOGIN_FAILURE_WINDOW_MINUTES must be positive")
        if self.smtp_port <= 0:
            raise ValueError("SELDRUNE_SMTP_PORT must be positive")
        if self.smtp_timeout_seconds <= 0:
            raise ValueError("SELDRUNE_SMTP_TIMEOUT_SECONDS must be positive")
        smtp_credentials = [bool(self.smtp_username), bool(self.smtp_password)]
        if any(smtp_credentials) and not all(smtp_credentials):
            raise ValueError("SMTP username and password must be configured together")
        if self.model_provider not in {"mock", "openai", "openai_compatible"}:
            raise ValueError(
                "SELDRUNE_MODEL_PROVIDER must be mock, openai, or openai_compatible"
            )
        if self.model_timeout_seconds <= 0:
            raise ValueError("SELDRUNE_MODEL_TIMEOUT_SECONDS must be positive")
        if self.model_max_output_tokens <= 0:
            raise ValueError("SELDRUNE_MODEL_MAX_OUTPUT_TOKENS must be positive")
        if self.ai_request_max_usd <= 0:
            raise ValueError("SELDRUNE_AI_REQUEST_MAX_USD must be positive")
        if self.ai_daily_max_usd <= 0:
            raise ValueError("SELDRUNE_AI_DAILY_MAX_USD must be positive")
        if self.ai_monthly_max_usd <= 0:
            raise ValueError("SELDRUNE_AI_MONTHLY_MAX_USD must be positive")
        if self.ai_monthly_max_usd < self.ai_daily_max_usd:
            raise ValueError(
                "SELDRUNE_AI_MONTHLY_MAX_USD must be greater than or equal to the daily limit"
            )
        if not 0 < self.ai_spend_warning_ratio < 1:
            raise ValueError("SELDRUNE_AI_SPEND_WARNING_RATIO must be between 0 and 1")
        if not self.ai_spend_warning_ratio < self.ai_conservation_ratio < 1:
            raise ValueError(
                "SELDRUNE_AI_CONSERVATION_RATIO must be above the warning ratio and below 1"
            )
        if self.ai_pdf_request_max_usd <= 0:
            raise ValueError("SELDRUNE_AI_PDF_REQUEST_MAX_USD must be positive")
        if self.ai_pdf_max_total_usd <= 0:
            raise ValueError("SELDRUNE_AI_PDF_MAX_TOTAL_USD must be positive")
        if not 1 <= self.ai_pdf_max_attempts <= 5:
            raise ValueError("SELDRUNE_AI_PDF_MAX_ATTEMPTS must be between 1 and 5")
        if not 256 <= self.ai_pdf_max_output_tokens <= 12000:
            raise ValueError(
                "SELDRUNE_AI_PDF_MAX_OUTPUT_TOKENS must be between 256 and 12000"
            )
        if not 0.5 <= self.pdf_brain_min_confidence <= 0.99:
            raise ValueError(
                "SELDRUNE_PDF_BRAIN_MIN_CONFIDENCE must be between 0.5 and 0.99"
            )
        if self.ai_image_job_max_usd <= 0:
            raise ValueError("SELDRUNE_AI_IMAGE_JOB_MAX_USD must be positive")
        if self.ai_video_job_max_usd <= 0:
            raise ValueError("SELDRUNE_AI_VIDEO_JOB_MAX_USD must be positive")
        if not 1 <= self.ai_video_default_seconds <= self.ai_video_max_seconds:
            raise ValueError(
                "SELDRUNE_AI_VIDEO_DEFAULT_SECONDS must be between 1 and the video maximum"
            )
        if not 1 <= self.ai_video_max_seconds <= 30:
            raise ValueError("SELDRUNE_AI_VIDEO_MAX_SECONDS must be between 1 and 30")
        if self.ai_image_detail not in {"low", "high", "auto", "original"}:
            raise ValueError("SELDRUNE_AI_IMAGE_DETAIL is invalid")
        if self.ai_pdf_detail not in {"low", "high", "auto"}:
            raise ValueError("SELDRUNE_AI_PDF_DETAIL is invalid")
        if self.project_estimated_cost_per_step_usd < 0:
            raise ValueError("SELDRUNE_PROJECT_ESTIMATED_COST_PER_STEP_USD cannot be negative")
        if not 1 <= self.knowledge_retrieval_limit <= 25:
            raise ValueError("SELDRUNE_KNOWLEDGE_RETRIEVAL_LIMIT must be between 1 and 25")
        if self.knowledge_context_max_chars < 500:
            raise ValueError("SELDRUNE_KNOWLEDGE_CONTEXT_MAX_CHARS must be at least 500")
        if self.life_worker_interval_seconds < 1:
            raise ValueError("SELDRUNE_LIFE_WORKER_INTERVAL_SECONDS must be at least 1")
        if not 1 <= self.life_worker_max_commands <= 100:
            raise ValueError("SELDRUNE_LIFE_WORKER_MAX_COMMANDS must be between 1 and 100")
        if not 1 <= self.life_worker_max_steps_per_command <= 50:
            raise ValueError("SELDRUNE_LIFE_WORKER_MAX_STEPS_PER_COMMAND must be between 1 and 50")
        if not 0 <= self.life_worker_max_retries_per_step <= 2:
            raise ValueError("SELDRUNE_LIFE_WORKER_MAX_RETRIES_PER_STEP must be between 0 and 2")
        configured = [
            bool(self.owner_push_vapid_public_key),
            bool(self.owner_push_vapid_private_key),
            bool(self.owner_push_vapid_subject),
        ]
        if any(configured) and not all(configured):
            raise ValueError(
                "Owner Web Push VAPID public key, private key, and subject "
                "must be configured together"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
