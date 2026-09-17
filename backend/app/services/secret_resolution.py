from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

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

        value = provider(reference.locator)
        if value is None or value == "":
            raise SecretResolutionError("Secret value is unavailable")
        return value


def resolve_environment_secret(locator: str) -> str | None:
    key = locator.strip()
    if not key:
        return None
    return os.environ.get(key)


default_secret_resolver = SecretResolver(
    providers={
        "env": resolve_environment_secret,
    }
)


def resolve_secret(reference: SecretReference) -> str:
    return default_secret_resolver.resolve(reference)
