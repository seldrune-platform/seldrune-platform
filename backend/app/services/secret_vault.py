from __future__ import annotations

import base64
import hashlib
import re

from cryptography.fernet import Fernet, InvalidToken

from backend.app.core.config import settings
from backend.app.core.secrets import SecretProvider, SecretStatus
from backend.app.models.secret_reference import SecretReference
from backend.app.services.secret_resolution import (
    SecretResolutionError,
    resolve_secret as resolve_managed_secret,
)

_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{2,239}$")
_VAULT_LOCATOR = "vault://stored"


class SecretVaultError(RuntimeError):
    pass


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.auth_secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret_value(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise SecretVaultError("Secret value cannot be empty")
    return _fernet().encrypt(normalized.encode("utf-8")).decode("ascii")


def decrypt_secret_value(value: str | None) -> str:
    if not value:
        raise SecretVaultError("Encrypted secret value is unavailable")
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise SecretVaultError("Encrypted secret value could not be decrypted") from exc


def validate_secret_locator(provider: str, locator: str) -> None:
    if provider == "vault":
        if locator != _VAULT_LOCATOR:
            raise SecretVaultError("Vault secret locator is invalid")
        return
    if SecretProvider(provider) is SecretProvider.ENV and not _ENV_NAME.fullmatch(locator):
        raise SecretVaultError("Environment secret locator must be an uppercase variable name")


def resolve_secret(reference: SecretReference) -> str:
    if reference.status != SecretStatus.ACTIVE.value:
        raise SecretVaultError("Secret reference is disabled")
    if reference.provider == "vault":
        validate_secret_locator(reference.provider, reference.locator)
        return decrypt_secret_value(reference.encrypted_value)
    provider = SecretProvider(reference.provider)
    validate_secret_locator(provider.value, reference.locator)
    try:
        return resolve_managed_secret(reference)
    except SecretResolutionError as exc:
        raise SecretVaultError(str(exc)) from exc


def vault_locator() -> str:
    return _VAULT_LOCATOR
