from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from backend.app.models.secret_reference import SecretReference


class SecretResolutionError(RuntimeError):
    """Raised when a configured secret reference cannot be resolved safely."""


SecretProvider = Callable[[str], str | None]


@dataclass(frozen=True)
class SecretResolver:
    """Resolve secret references without persisting or logging secret values."""

    providers: dict[str, SecretProvider]

    def resolve(self, reference: SecretReference) -> str:
        if reference.status != "active":
            raise SecretResolutionError("Secret reference is not active")

        provider_name = reference.provider.strip().lower()
        provider = self.providers.get(provider_name)
        if provider is None:
            raise SecretResolutionError("Unsupported secret provider")

        try:
            value = provider(reference.locator)
        except SecretResolutionError:
            raise
        except Exception as exc:
            raise SecretResolutionError("Secret provider is unavailable") from exc
        if value is None or value == "":
            raise SecretResolutionError("Secret value is unavailable")
        return value


def resolve_environment_secret(locator: str) -> str | None:
    key = locator.strip()
    if not key:
        return None
    return os.environ.get(key)


@lru_cache
def _aws_secrets_client():
    try:
        import boto3
    except ImportError as exc:
        raise SecretResolutionError("AWS Secrets Manager support is not installed") from exc
    return boto3.client("secretsmanager")


def resolve_aws_secrets_manager_secret(locator: str) -> str | None:
    secret_id = locator.strip()
    if not secret_id:
        return None
    response = _aws_secrets_client().get_secret_value(SecretId=secret_id)
    value = response.get("SecretString")
    if isinstance(value, str):
        return value
    return None


default_secret_resolver = SecretResolver(
    providers={
        "env": resolve_environment_secret,
        "aws-secrets-manager": resolve_aws_secrets_manager_secret,
    }
)


def resolve_secret(reference: SecretReference) -> str:
    return default_secret_resolver.resolve(reference)
