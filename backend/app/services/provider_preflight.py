from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.secret_reference import SecretReference
from backend.app.services.external_actions import (
    _github_app_config,
    _github_headers,
    default_external_action_catalog,
)
from backend.app.services.tool_gateway import ToolGatewayError
from backend.app.services.secret_vault import SecretVaultError, resolve_secret
from backend.app.services.tool_input_defaults import production_runtime_targets

_TIMEOUT_SECONDS = 15.0
_GITHUB_API_VERSION = "2026-03-10"


def _response_json(response: httpx.Response) -> Any:
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return None


def _result(
    provider: str,
    *,
    status: str,
    verified: bool,
    detail: str,
    identity: dict[str, Any] | None = None,
    http_status: int | None = None,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "status": status,
        "verified": verified,
        "detail": detail,
        "identity": identity or {},
        "http_status": http_status,
    }


def _gmail_preflight(credential: str) -> dict[str, Any]:
    response = httpx.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/profile",
        headers={"Authorization": f"Bearer {credential}"},
        timeout=_TIMEOUT_SECONDS,
    )
    data = _response_json(response)
    if response.status_code == 200 and isinstance(data, dict):
        return _result(
            "gmail",
            status="verified",
            verified=True,
            detail="Gmail credential can read the authenticated mailbox profile.",
            identity={"email": data.get("emailAddress")},
            http_status=200,
        )
    if response.status_code == 401:
        return _result(
            "gmail",
            status="credential_invalid",
            verified=False,
            detail="Gmail rejected the configured credential.",
            http_status=401,
        )
    if response.status_code == 403:
        return _result(
            "gmail",
            status="scope_limited",
            verified=False,
            detail=(
                "Gmail credential reached the API but cannot read mailbox profile data. "
                "A send-only OAuth scope may still allow the configured send action."
            ),
            http_status=403,
        )
    return _result(
        "gmail",
        status="provider_error",
        verified=False,
        detail=f"Gmail preflight returned HTTP {response.status_code}.",
        http_status=response.status_code,
    )


def _github_repository_result(
    *,
    headers: dict[str, str],
    identity: dict[str, Any],
    full_name: str,
    auth_label: str,
) -> dict[str, Any]:
    repository = httpx.get(
        f"https://api.github.com/repos/{full_name}",
        headers=headers,
        timeout=_TIMEOUT_SECONDS,
    )
    repository_data = _response_json(repository)
    scoped_identity = {**identity, "repository": full_name}
    if repository.status_code == 404:
        return _result(
            "github",
            status="repository_not_found",
            verified=False,
            detail=(
                f"GitHub {auth_label} is valid, but the configured repository "
                f"{full_name} was not found or is not visible."
            ),
            identity=scoped_identity,
            http_status=404,
        )
    if repository.status_code in {401, 403}:
        return _result(
            "github",
            status="repository_access_denied",
            verified=False,
            detail=(
                f"GitHub {auth_label} is valid, but access to {full_name} is denied."
            ),
            identity=scoped_identity,
            http_status=repository.status_code,
        )
    if repository.status_code != 200:
        return _result(
            "github",
            status="provider_error",
            verified=False,
            detail=(
                f"GitHub repository preflight for {full_name} returned "
                f"HTTP {repository.status_code}."
            ),
            identity=scoped_identity,
            http_status=repository.status_code,
        )
    if isinstance(repository_data, dict):
        scoped_identity["repository"] = (
            repository_data.get("full_name") or full_name
        )
        scoped_identity["default_branch"] = repository_data.get(
            "default_branch"
        )
    return _result(
        "github",
        status="verified",
        verified=True,
        detail=(
            "GitHub credential and configured production repository are accessible."
        ),
        identity=scoped_identity,
        http_status=200,
    )


def _github_preflight(credential: str) -> dict[str, Any]:
    targets = production_runtime_targets()
    full_name = str(targets.get("github_full_name") or "").strip()

    try:
        app_config = _github_app_config(credential)
        headers = _github_headers(credential)
    except ToolGatewayError as exc:
        detail = str(exc)
        configuration_error = (
            "app id and installation id are required" in detail.lower()
        )
        return _result(
            "github",
            status=(
                "configuration_error"
                if configuration_error
                else "credential_invalid"
            ),
            verified=False,
            detail=detail,
        )

    if app_config is not None:
        app_id, installation_id, _private_key = app_config
        identity = {
            "auth_type": "github_app",
            "app_id": app_id,
            "installation_id": installation_id,
        }
        if full_name:
            return _github_repository_result(
                headers=headers,
                identity=identity,
                full_name=full_name,
                auth_label="App installation",
            )

        repositories = httpx.get(
            "https://api.github.com/installation/repositories",
            headers=headers,
            timeout=_TIMEOUT_SECONDS,
        )
        repositories_data = _response_json(repositories)
        if repositories.status_code == 200:
            if isinstance(repositories_data, dict):
                identity["repository_count"] = repositories_data.get(
                    "total_count"
                )
            return _result(
                "github",
                status="verified",
                verified=True,
                detail="GitHub App installation token is valid.",
                identity=identity,
                http_status=200,
            )
        if repositories.status_code in {401, 403}:
            return _result(
                "github",
                status="credential_invalid",
                verified=False,
                detail="GitHub rejected the configured App installation credential.",
                identity=identity,
                http_status=repositories.status_code,
            )
        return _result(
            "github",
            status="provider_error",
            verified=False,
            detail=(
                "GitHub App installation preflight returned "
                f"HTTP {repositories.status_code}."
            ),
            identity=identity,
            http_status=repositories.status_code,
        )

    response = httpx.get(
        "https://api.github.com/user",
        headers=headers,
        timeout=_TIMEOUT_SECONDS,
    )
    data = _response_json(response)
    if response.status_code == 200 and isinstance(data, dict):
        identity = {
            "auth_type": "token",
            "login": data.get("login"),
            "id": data.get("id"),
        }
        if full_name:
            return _github_repository_result(
                headers=headers,
                identity=identity,
                full_name=full_name,
                auth_label="credential",
            )
        return _result(
            "github",
            status="verified",
            verified=True,
            detail="GitHub authenticated-user request succeeded.",
            identity=identity,
            http_status=200,
        )
    if response.status_code == 401:
        return _result(
            "github",
            status="credential_invalid",
            verified=False,
            detail="GitHub rejected the configured credential.",
            http_status=401,
        )
    if response.status_code == 403:
        return _result(
            "github",
            status="scope_limited",
            verified=False,
            detail=(
                "GitHub accepted the request path but denied access or rate-limited it. "
                "Check token permissions and repository access."
            ),
            http_status=403,
        )
    return _result(
        "github",
        status="provider_error",
        verified=False,
        detail=f"GitHub preflight returned HTTP {response.status_code}.",
        http_status=response.status_code,
    )


def _render_preflight(credential: str) -> dict[str, Any]:
    response = httpx.get(
        "https://api.render.com/v1/users",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {credential}",
        },
        timeout=_TIMEOUT_SECONDS,
    )
    data = _response_json(response)
    if response.status_code == 200:
        identity: dict[str, Any] = {}
        if isinstance(data, dict):
            identity = {
                key: data.get(key)
                for key in ("id", "email", "name")
                if data.get(key) is not None
            }
        return _result(
            "render",
            status="verified",
            verified=True,
            detail="Render authenticated-user request succeeded.",
            identity=identity,
            http_status=200,
        )
    if response.status_code == 401:
        return _result(
            "render",
            status="credential_invalid",
            verified=False,
            detail="Render rejected the configured API key.",
            http_status=401,
        )
    if response.status_code in {403, 406, 429}:
        return _result(
            "render",
            status="scope_limited",
            verified=False,
            detail=(
                "Render received the authenticated request but access was limited. "
                "Check API-key access and current rate limits."
            ),
            http_status=response.status_code,
        )
    return _result(
        "render",
        status="provider_error",
        verified=False,
        detail=f"Render preflight returned HTTP {response.status_code}.",
        http_status=response.status_code,
    )


_PREFLIGHT_HANDLERS = {
    "gmail": _gmail_preflight,
    "github": _github_preflight,
    "render": _render_preflight,
}


def preflight_provider_credential(
    provider: str,
    credential: str,
) -> dict[str, Any]:
    handler = _PREFLIGHT_HANDLERS.get(provider)
    if handler is None:
        return _result(
            provider,
            status="unsupported",
            verified=False,
            detail="No non-destructive preflight is registered for this provider.",
        )
    try:
        return handler(credential)
    except httpx.HTTPError:
        return _result(
            provider,
            status="network_error",
            verified=False,
            detail="Provider preflight could not reach the remote API.",
        )


def preflight_configured_providers(
    session: Session,
    *,
    organization_id: UUID,
) -> list[dict[str, Any]]:
    references = {
        item.slug: item
        for item in session.scalars(
            select(SecretReference).where(
                SecretReference.organization_id == organization_id
            )
        )
    }
    provider_catalog: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in default_external_action_catalog():
        provider_catalog[str(item["provider"])].append(item)

    results: list[dict[str, Any]] = []
    for provider, items in sorted(provider_catalog.items()):
        representative = items[0]
        credential_slug = str(representative["credential_slug"])
        reference = references.get(credential_slug)
        if reference is None:
            results.append(
                _result(
                    provider,
                    status="not_configured",
                    verified=False,
                    detail=(
                        "No credential reference exists. Configure "
                        f"{representative['credential_env_locator']} and activate providers."
                    ),
                )
            )
            continue
        try:
            credential = resolve_secret(reference)
        except SecretVaultError as exc:
            results.append(
                _result(
                    provider,
                    status="credential_unavailable",
                    verified=False,
                    detail=str(exc),
                )
            )
            continue

        results.append(preflight_provider_credential(provider, credential))
    return results
