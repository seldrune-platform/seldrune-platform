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
    app_version: str = "1.1.0"
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
    github_default_owner: str | None = None
    github_default_repo: str | None = None
    github_default_ref: str | None = None
    render_default_service_id: str | None = None
    model_provider: str = "mock"
    model_default: str = "mock-v1"
    model_timeout_seconds: float = 60.0
    model_max_output_tokens: int = 1200
    project_estimated_cost_per_step_usd: float = 0.05
    knowledge_retrieval_limit: int = 6
    knowledge_context_max_chars: int = 6000
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
        if self.model_provider not in {"mock", "openai"}:
            raise ValueError("SELDRUNE_MODEL_PROVIDER must be mock or openai")
        if self.model_timeout_seconds <= 0:
            raise ValueError("SELDRUNE_MODEL_TIMEOUT_SECONDS must be positive")
        if self.model_max_output_tokens <= 0:
            raise ValueError("SELDRUNE_MODEL_MAX_OUTPUT_TOKENS must be positive")
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
