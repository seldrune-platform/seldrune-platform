from __future__ import annotations

import re

from backend.app.core.secrets import SecretProvider, SecretStatus
from backend.app.models.secret_reference import SecretReference
from backend.app.services.secret_resolution import (
    SecretResolutionError,
    resolve_secret as resolve_managed_secret,
)

_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{2,239}$")


class SecretVaultError(RuntimeError):
    pass


def validate_secret_locator(provider: str, locator: str) -> None:
    if SecretProvider(provider) is SecretProvider.ENV and not _ENV_NAME.fullmatch(locator):
        raise SecretVaultError("Environment secret locator must be an uppercase variable name")


def resolve_secret(reference: SecretReference) -> str:
    if reference.status != SecretStatus.ACTIVE.value:
        raise SecretVaultError("Secret reference is disabled")
    provider = SecretProvider(reference.provider)
    validate_secret_locator(provider.value, reference.locator)
    try:
        return resolve_managed_secret(reference)
    except SecretResolutionError as exc:
        raise SecretVaultError(str(exc)) from exc
