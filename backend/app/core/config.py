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
    app_version: str = "0.3.0"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    enable_docs: bool = True
    database_url: str = "sqlite+pysqlite:///./seldrune.db"
    auth_secret_key: str = "development-only-change-this-secret"
    auth_access_token_minutes: int = 30

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        if self.environment.lower() in {"prod", "production"}:
            if self.auth_secret_key == "development-only-change-this-secret":
                raise ValueError("SELDRUNE_AUTH_SECRET_KEY must be set in production")
            if len(self.auth_secret_key) < 32:
                raise ValueError("SELDRUNE_AUTH_SECRET_KEY must be at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
