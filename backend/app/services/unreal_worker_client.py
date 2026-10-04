from __future__ import annotations

import ipaddress
import json
import re
import socket
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from backend.app.services.tool_gateway import ToolGatewayError

_TIMEOUT_SECONDS = 20.0
_ALLOWED_ROUTES = {
    ("GET", "/v1/healthz"),
    ("GET", "/v1/engine/status"),
    ("POST", "/v1/engine/install"),
}
_ENGINE_VERSION = re.compile(r"\A\d{1,2}\.\d+(?:\.\d+)?\Z")


class UnrealWorkerError(ToolGatewayError):
    def __init__(self, message: str, *, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status


def validate_engine_version(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _ENGINE_VERSION.fullmatch(value.strip()):
        raise UnrealWorkerError("Engine version must look like 5.4 or 5.4.4.")
    return value.strip()


def _assert_public_host(hostname: str, port: int) -> None:
    normalized = hostname.rstrip(".").lower()
    if normalized in {"localhost", "metadata.google.internal"} or normalized.endswith(
        (".localhost", ".local", ".internal", ".onion")
    ):
        raise UnrealWorkerError("Worker URL must use a publicly reachable HTTPS hostname.")
    try:
        addresses = {ipaddress.ip_address(normalized)}
    except ValueError:
        try:
            resolved = socket.getaddrinfo(normalized, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise UnrealWorkerError("Worker hostname could not be resolved.") from exc
        addresses = {
            ipaddress.ip_address(item[4][0])
            for item in resolved
            if item and item[4]
        }
    if not addresses or any(not address.is_global for address in addresses):
        raise UnrealWorkerError("Worker URL must resolve only to public IP addresses.")


def parse_unreal_worker_credential(value: str | None) -> tuple[str, str]:
    if not value or len(value) > 12000:
        raise UnrealWorkerError("Unreal worker URL and bearer token are required.")
    try:
        payload = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise UnrealWorkerError(
            "Unreal worker credential must include its HTTPS URL and token."
        ) from exc
    if not isinstance(payload, dict):
        raise UnrealWorkerError(
            "Unreal worker credential must include its HTTPS URL and token."
        )
    base_url = payload.get("base_url")
    token = payload.get("token")
    if (
        not isinstance(base_url, str)
        or not isinstance(token, str)
        or not token.strip()
        or len(token) > 8192
    ):
        raise UnrealWorkerError("Unreal worker URL and bearer token are required.")
    try:
        parsed = urlsplit(base_url.strip())
        port = parsed.port or 443
    except ValueError as exc:
        raise UnrealWorkerError("Enter a valid HTTPS worker URL.") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise UnrealWorkerError(
            "Worker URL must use HTTPS and cannot contain credentials, query, or fragment."
        )
    _assert_public_host(parsed.hostname, port)
    normalized = urlunsplit(
        ("https", parsed.netloc, parsed.path.rstrip("/"), "", "")
    ).rstrip("/")
    return normalized, token.strip()


def request_unreal_worker(
    credential: str | None,
    *,
    method: str,
    path: str,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_method = method.upper()
    if (normalized_method, path) not in _ALLOWED_ROUTES:
        raise UnrealWorkerError("Requested Unreal worker operation is not supported.")
    base_url, token = parse_unreal_worker_credential(credential)
    try:
        response = httpx.request(
            normalized_method,
            base_url + path,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=json_body,
            timeout=_TIMEOUT_SECONDS,
            follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        raise UnrealWorkerError("Seldrune could not reach the Unreal worker.") from exc
    if response.status_code in {401, 403}:
        raise UnrealWorkerError(
            "The Unreal worker rejected its bearer token.",
            http_status=response.status_code,
        )
    if response.status_code < 200 or response.status_code >= 300:
        raise UnrealWorkerError(
            f"Unreal worker returned HTTP {response.status_code}.",
            http_status=response.status_code,
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise UnrealWorkerError("Unreal worker returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise UnrealWorkerError("Unreal worker response must be a JSON object.")
    return data
