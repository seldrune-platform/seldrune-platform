import pytest

from backend.app.models.secret_reference import SecretReference
from backend.app.services.secret_resolution import (
    SecretResolutionError,
    SecretResolver,
    resolve_environment_secret,
)


def _reference(
    *,
    provider: str = "env",
    locator: str = "SELDRUNE_TEST_SECRET",
    status: str = "active",
) -> SecretReference:
    return SecretReference(
        name="Test secret",
        slug="test-secret",
        provider=provider,
        locator=locator,
        status=status,
    )


def test_environment_provider_reads_value_without_mutating_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SELDRUNE_TEST_SECRET", "super-secret-value")
    reference = _reference()

    assert resolve_environment_secret(reference.locator) == "super-secret-value"
    assert reference.locator == "SELDRUNE_TEST_SECRET"


def test_resolver_supports_injected_managed_provider() -> None:
    resolver = SecretResolver(
        providers={"managed": lambda locator: "resolved" if locator == "secret/name" else None}
    )
    reference = _reference(provider="managed", locator="secret/name")

    assert resolver.resolve(reference) == "resolved"


def test_resolver_rejects_unknown_provider_without_exposing_locator() -> None:
    reference = _reference(provider="unknown", locator="sensitive/locator")

    with pytest.raises(SecretResolutionError) as exc_info:
        SecretResolver(providers={}).resolve(reference)

    assert "sensitive/locator" not in str(exc_info.value)


def test_resolver_rejects_inactive_reference() -> None:
    reference = _reference(status="disabled")

    with pytest.raises(SecretResolutionError, match="not active"):
        SecretResolver(providers={"env": lambda locator: "value"}).resolve(reference)


def test_resolver_rejects_missing_value_without_exposing_locator() -> None:
    reference = _reference(locator="SECRET_THAT_DOES_NOT_EXIST")

    with pytest.raises(SecretResolutionError) as exc_info:
        SecretResolver(providers={"env": lambda locator: None}).resolve(reference)

    assert reference.locator not in str(exc_info.value)
